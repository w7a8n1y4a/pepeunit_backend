import uuid
from io import BytesIO

import pytest
from PIL import Image

from app.configs.errors import NoAccessError, ValidationError
from app.domain.instance_settings_model import InstanceSettings
from app.domain.user_model import User
from app.dto.enum import IconEntityType, UserRole
from app.repositories.instance_settings_repository import (
    InstanceSettingsRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.user import UserCreate
from app.services.icon_image import IconImage
from tests.integration.helpers.keys import fresh_key
from tests.integration.helpers.services import (
    icon_service,
    unit_service,
    user_service,
)


def _jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (192, 192), "red").save(buffer, format="JPEG")
    return buffer.getvalue()


def _as_owner(database, user: User):
    repository = UserRepository(db=database)
    previous = repository.get_owner()
    repository.set_single_owner(user.uuid)
    return repository, previous


def _restore_owner(database, repository, user: User, previous: User | None):
    database.expire_all()
    user.role = UserRole.USER
    repository.update(user.uuid, user)
    if previous and previous.uuid != user.uuid:
        repository.set_single_owner(previous.uuid)


def test_user_icon_is_generated_from_public_key(database, cc) -> None:
    created = user_service(database, cc, None).create(
        UserCreate(public_key=fresh_key().public_key)
    )
    try:
        expected = IconImage.generate(created.public_key)
        icon = icon_service(database).get(created.icon_uuid)
        assert bytes(icon.image_bin) == expected
        assert icon.size == len(expected)
        assert icon.image_hash == IconImage.md5(expected)
    finally:
        UserRepository(db=database).delete(User(uuid=created.uuid))


def test_deleted_user_drops_icon(database, cc) -> None:
    created = user_service(database, cc, None).create(
        UserCreate(public_key=fresh_key().public_key)
    )
    icon_uuid = created.icon_uuid
    UserRepository(db=database).delete(User(uuid=created.uuid))
    database.expire_all()
    with pytest.raises(ValidationError):
        icon_service(database).get(icon_uuid)


def test_unknown_icon_is_missing(database) -> None:
    with pytest.raises(ValidationError):
        icon_service(database).get(uuid.uuid4())


def test_user_replaces_own_icon(database, extra_user, extra_user_token) -> None:
    old_uuid = extra_user.icon_uuid
    replacement = IconImage.generate("user-replacement")
    updated = icon_service(database, extra_user_token).upload(
        extra_user.uuid, IconEntityType.USER, replacement
    )
    database.expire_all()
    stored = UserRepository(db=database).get(User(uuid=extra_user.uuid))
    icon = icon_service(database).get(stored.icon_uuid)
    assert stored.icon_uuid == updated.uuid
    assert stored.icon_uuid != old_uuid
    assert bytes(icon.image_bin) == replacement
    assert icon.image_hash == IconImage.md5(replacement)
    with pytest.raises(ValidationError):
        icon_service(database).get(old_uuid)


def test_other_user_cannot_change_icon(
    database, extra_user, regular_user_token
) -> None:
    with pytest.raises(NoAccessError):
        icon_service(database, regular_user_token).upload(
            extra_user.uuid,
            IconEntityType.USER,
            IconImage.generate("someone-else"),
        )


def test_upload_requires_a_user(database, extra_user) -> None:
    with pytest.raises(NoAccessError):
        icon_service(database, None).upload(
            extra_user.uuid, IconEntityType.USER, IconImage.generate("no-token")
        )


def test_invalid_image_keeps_the_current_icon(
    database, extra_user, extra_user_token
) -> None:
    old_uuid = extra_user.icon_uuid
    with pytest.raises(ValidationError):
        icon_service(database, extra_user_token).upload(
            extra_user.uuid, IconEntityType.USER, _jpeg()
        )
    database.expire_all()
    stored = UserRepository(db=database).get(User(uuid=extra_user.uuid))
    assert stored.icon_uuid == old_uuid
    assert icon_service(database).get(old_uuid)


def test_unit_icon_lifecycle(
    database, cc, regular_user_token, extra_user_token, crud_unit
) -> None:
    icons = icon_service(database)
    generated = icons.get(crud_unit.icon_uuid)
    assert bytes(generated.image_bin) == IconImage.generate(str(crud_unit.uuid))

    replacement = IconImage.generate("unit-replacement")
    with pytest.raises(NoAccessError):
        icon_service(database, extra_user_token).upload(
            crud_unit.uuid, IconEntityType.UNIT, replacement
        )

    updated = icon_service(database, regular_user_token).upload(
        crud_unit.uuid, IconEntityType.UNIT, replacement
    )
    database.expire_all()
    with pytest.raises(ValidationError):
        icons.get(crud_unit.icon_uuid)
    updated_uuid = updated.uuid
    assert bytes(icons.get(updated_uuid).image_bin) == replacement

    unit_service(database, cc, regular_user_token).delete(crud_unit.uuid)
    database.expire_all()
    with pytest.raises(ValidationError):
        icons.get(updated_uuid)


def test_instance_keeps_its_stored_icon(database) -> None:
    """The instance icon is a snapshot. A later generator does not redraw it."""
    row = InstanceSettingsRepository(database).get(
        InstanceSettings(uuid=InstanceSettings.ROW_UUID)
    )
    icon = icon_service(database).get(row.icon_uuid)
    image = bytes(icon.image_bin)
    IconImage.validate(image)
    assert icon.size == len(image)
    assert icon.image_hash == IconImage.md5(image)


def test_instance_icon_is_owner_only(
    database, extra_user, extra_user_token, admin_user_token
) -> None:
    icons = icon_service(database)
    row = InstanceSettingsRepository(database).get(
        InstanceSettings(uuid=InstanceSettings.ROW_UUID)
    )
    original_uuid = row.icon_uuid
    original = bytes(icons.get(original_uuid).image_bin)
    replacement = IconImage.generate("instance-replacement")
    with pytest.raises(NoAccessError):
        icon_service(database, admin_user_token).upload(
            InstanceSettings.ROW_UUID, IconEntityType.INSTANCE, replacement
        )

    repository, previous = _as_owner(database, extra_user)
    try:
        with pytest.raises(ValidationError):
            icon_service(database, extra_user_token).upload(
                uuid.uuid4(), IconEntityType.INSTANCE, replacement
            )
        updated = icon_service(database, extra_user_token).upload(
            InstanceSettings.ROW_UUID, IconEntityType.INSTANCE, replacement
        )
        database.expire_all()
        with pytest.raises(ValidationError):
            icons.get(original_uuid)
        assert bytes(icons.get(updated.uuid).image_bin) == replacement
    finally:
        database.expire_all()
        current = InstanceSettingsRepository(database).get(
            InstanceSettings(uuid=InstanceSettings.ROW_UUID)
        )
        if current.icon_uuid != original_uuid:
            icon_service(database, extra_user_token).upload(
                InstanceSettings.ROW_UUID, IconEntityType.INSTANCE, original
            )
        _restore_owner(database, repository, extra_user, previous)
