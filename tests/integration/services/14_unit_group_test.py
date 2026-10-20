import contextlib
import uuid

import pytest

from app.configs.errors import NoAccessError, UnitGroupError, ValidationError
from app.domain.unit_group_model import UnitGroup
from app.dto.enum import IconEntityType, OrderByText, VisibilityLevel
from app.repositories.unit_group_repository import UnitGroupRepository
from app.repositories.unit_group_unit_repository import UnitGroupUnitRepository
from app.schemas.pydantic.unit import UnitCreate, UnitRead
from app.schemas.pydantic.unit_group import (
    UnitGroupCreate,
    UnitGroupFilter,
    UnitGroupMemberFilter,
    UnitGroupRead,
    UnitGroupUpdate,
)
from app.services.icon_image import IconImage
from tests.integration.helpers.instance_settings import owner_setting
from tests.integration.helpers.names import unique_name
from tests.integration.helpers.services import (
    branch_commits,
    icon_service,
    unit_group_service,
    unit_service,
)


def _groups(service, **kwargs):
    return service.list(UnitGroupFilter(**kwargs))


def _delete_groups(service, groups) -> None:
    for group in groups:
        service.delete(group.uuid)


@pytest.fixture(scope="module")
def group_source(universal_registry, regular_user_token, database):
    read, commits = branch_commits(
        database, regular_user_token, universal_registry.uuid
    )
    return universal_registry, read.branches[0], commits[0].commit


def _unit(database, cc, token, registry, branch, commit, name, visibility):
    return unit_service(database, cc, token).create(
        UnitCreate(
            repository_registry_uuid=registry.uuid,
            visibility_level=visibility,
            name=name,
            is_auto_update_unit=False,
            target_branch=branch,
            target_commit=commit,
        )
    )


@pytest.fixture(scope="module")
def group_units(group_source, regular_user_token, database, cc):
    registry, branch, commit = group_source
    token = regular_user_token
    created = [
        _unit(
            database,
            cc,
            token,
            registry,
            branch,
            commit,
            unique_name("gua"),
            VisibilityLevel.PUBLIC,
        ),
        _unit(
            database,
            cc,
            token,
            registry,
            branch,
            commit,
            unique_name("gub"),
            VisibilityLevel.PUBLIC,
        ),
        _unit(
            database,
            cc,
            token,
            registry,
            branch,
            commit,
            unique_name("gup"),
            VisibilityLevel.PRIVATE,
        ),
    ]
    yield created
    service = unit_service(database, cc, token)
    for unit in created:
        with contextlib.suppress(Exception):
            service.delete(unit.uuid)


def test_create_group_generates_icon(database, regular_user_token) -> None:
    service = unit_group_service(database, regular_user_token)
    group = service.create(UnitGroupCreate(name=unique_name("gnew")))
    try:
        expected = IconImage.generate(str(group.uuid))
        icon = icon_service(database).get(group.icon_uuid)
        assert bytes(icon.image_bin) == expected
        assert group.creator_uuid is not None
        stored = service.get(group.uuid)
        assert stored.name == group.name
        assert stored.icon_uuid == group.icon_uuid
        assert UnitGroupRead(**stored.dict()).uuid == group.uuid
    finally:
        service.delete(group.uuid)


def test_name_is_unique_for_the_creator(
    database, regular_user_token, extra_user_token
) -> None:
    name = unique_name("gdup")
    owner = unit_group_service(database, regular_user_token)
    other = unit_group_service(database, extra_user_token)
    first = owner.create(UnitGroupCreate(name=name))
    second = other.create(UnitGroupCreate(name=name))
    try:
        with pytest.raises(UnitGroupError, match="Name is not unique"):
            owner.create(UnitGroupCreate(name=name))
        assert first.creator_uuid != second.creator_uuid
    finally:
        owner.delete(first.uuid)
        other.delete(second.uuid)


def test_bad_name_is_rejected(database, regular_user_token) -> None:
    service = unit_group_service(database, regular_user_token)
    with pytest.raises(UnitGroupError, match="Name is not correct"):
        service.create(UnitGroupCreate(name="a"))
    with pytest.raises(UnitGroupError, match="Name is not correct"):
        service.create(UnitGroupCreate(name="bad name"))


def test_list_search_and_pagination(database, regular_user_token) -> None:
    service = unit_group_service(database, regular_user_token)
    token = uuid.uuid4().hex[:6]
    created = [
        service.create(UnitGroupCreate(name=f"a{token}aa")),
        service.create(UnitGroupCreate(name=f"b{token}bb")),
        service.create(UnitGroupCreate(name=f"c{token}cc")),
    ]
    try:
        count, page = _groups(
            service,
            search_string=token,
            order_by_create_date=None,
            order_by_group_name=OrderByText.asc,
            limit=1,
        )
        assert count == 3
        assert page[0].name == created[0].name

        _, second_page = _groups(
            service,
            search_string=token,
            order_by_create_date=None,
            order_by_group_name=OrderByText.asc,
            offset=1,
            limit=1,
        )
        assert second_page[0].name == created[1].name

        narrowed, found = _groups(service, search_string=f"c{token}")
        assert narrowed == 1
        assert found[0].uuid == created[2].uuid
    finally:
        _delete_groups(service, created)


def test_groups_belong_to_their_creator(
    database, regular_user_token, extra_user_token, group_units
) -> None:
    public_unit = group_units[0]
    owner = unit_group_service(database, regular_user_token)
    other = unit_group_service(database, extra_user_token)
    own = owner.create(UnitGroupCreate(name=unique_name("gown")))
    foreign = other.create(UnitGroupCreate(name=unique_name("goth")))
    other.link_unit(foreign.uuid, public_unit.uuid)
    try:
        with pytest.raises(NoAccessError):
            owner.get(foreign.uuid)
        with pytest.raises(NoAccessError):
            other.update(own.uuid, UnitGroupUpdate(name=unique_name("gren")))
        with pytest.raises(NoAccessError):
            other.delete(own.uuid)
        with pytest.raises(NoAccessError):
            other.link_unit(own.uuid, public_unit.uuid)
        with pytest.raises(NoAccessError):
            unit_group_service(database, None).create(
                UnitGroupCreate(name=unique_name("gno"))
            )

        _, visible = _groups(owner, uuids=[own.uuid, foreign.uuid])
        assert [group.uuid for group in visible] == [own.uuid]
        _, foreign_visible = _groups(other, unit_uuid=public_unit.uuid)
        assert [group.uuid for group in foreign_visible] == [foreign.uuid]
        _, owner_for_unit = _groups(owner, unit_uuid=public_unit.uuid)
        assert foreign.uuid not in {group.uuid for group in owner_for_unit}
    finally:
        other.delete(foreign.uuid)
        owner.delete(own.uuid)


def test_unit_membership(
    database, regular_user_token, extra_user_token, group_units
) -> None:
    public_unit, second_unit, private_unit = group_units
    service = unit_group_service(database, regular_user_token)
    first = service.create(UnitGroupCreate(name=unique_name("gone")))
    second = service.create(UnitGroupCreate(name=unique_name("gtwo")))
    try:
        service.link_unit(first.uuid, public_unit.uuid)
        service.link_unit(first.uuid, second_unit.uuid)
        service.link_unit(second.uuid, public_unit.uuid)

        with pytest.raises(UnitGroupError, match="already in this group"):
            service.link_unit(first.uuid, public_unit.uuid)
        service.link_unit(second.uuid, private_unit.uuid)
        outsider = unit_group_service(database, extra_user_token)
        foreign = outsider.create(UnitGroupCreate(name=unique_name("gprv")))
        try:
            with pytest.raises(NoAccessError):
                outsider.link_unit(foreign.uuid, private_unit.uuid)
            outsider.link_unit(foreign.uuid, public_unit.uuid)
        finally:
            outsider.delete(foreign.uuid)

        count, groups = _groups(
            service,
            unit_uuid=public_unit.uuid,
            uuids=[first.uuid, second.uuid],
        )
        assert count == 2
        assert {group.uuid for group in groups} == {first.uuid, second.uuid}

        _, only_first = _groups(
            service,
            unit_uuid=second_unit.uuid,
            uuids=[first.uuid, second.uuid],
        )
        assert [group.uuid for group in only_first] == [first.uuid]

        member_count, members = service.list_units(
            first.uuid,
            UnitGroupMemberFilter(
                order_by_unit_name=OrderByText.asc, limit=10
            ),
        )
        assert member_count == 2
        assert {unit.uuid for unit in members} == {
            public_unit.uuid,
            second_unit.uuid,
        }
        UnitRead(**members[0].to_dict())
        _, found = service.list_units(
            first.uuid,
            UnitGroupMemberFilter(search_string=second_unit.name),
        )
        assert [unit.uuid for unit in found] == [second_unit.uuid]

        service.unlink_unit(first.uuid, second_unit.uuid)
        left, remaining = service.list_units(
            first.uuid, UnitGroupMemberFilter()
        )
        assert left == 1
        assert remaining[0].uuid == public_unit.uuid
        with pytest.raises(ValidationError):
            service.unlink_unit(first.uuid, second_unit.uuid)
    finally:
        _delete_groups(service, [first, second])


def test_rename_group(database, regular_user_token) -> None:
    service = unit_group_service(database, regular_user_token)
    kept = unique_name("gkeep")
    group = service.create(UnitGroupCreate(name=unique_name("gold")))
    other = service.create(UnitGroupCreate(name=kept))
    try:
        renamed = unique_name("gnew")
        updated = service.update(group.uuid, UnitGroupUpdate(name=renamed))
        assert updated.name == renamed
        assert updated.icon_uuid == group.icon_uuid
        with pytest.raises(UnitGroupError, match="Name is not unique"):
            service.update(group.uuid, UnitGroupUpdate(name=kept))
    finally:
        _delete_groups(service, [group, other])


def test_deleted_group_drops_icon_and_membership(
    database, regular_user_token, group_units
) -> None:
    public_unit = group_units[0]
    service = unit_group_service(database, regular_user_token)
    group = service.create(UnitGroupCreate(name=unique_name("gdel")))
    service.link_unit(group.uuid, public_unit.uuid)
    icon_uuid = group.icon_uuid
    service.delete(group.uuid)
    database.expire_all()
    with pytest.raises(ValidationError):
        service.get(group.uuid)
    with pytest.raises(ValidationError):
        icon_service(database).get(icon_uuid)
    assert (
        UnitGroupUnitRepository(database).get_link(
            group.uuid, public_unit.uuid
        )
        is None
    )


def test_deleted_unit_leaves_the_group(
    database, cc, regular_user_token, group_source
) -> None:
    registry, branch, commit = group_source
    token = regular_user_token
    unit = _unit(
        database,
        cc,
        token,
        registry,
        branch,
        commit,
        unique_name("gux"),
        VisibilityLevel.PUBLIC,
    )
    service = unit_group_service(database, token)
    group = service.create(UnitGroupCreate(name=unique_name("gunt")))
    try:
        service.link_unit(group.uuid, unit.uuid)
        unit_service(database, cc, token).delete(unit.uuid)
        database.expire_all()
        count, units = service.list_units(group.uuid, UnitGroupMemberFilter())
        assert count == 0
        assert units == []
        assert service.get(group.uuid).uuid == group.uuid
    finally:
        UnitGroupRepository(database).delete(UnitGroup(uuid=group.uuid))


def test_owner_replaces_group_icon(
    database, regular_user_token, extra_user_token
) -> None:
    service = unit_group_service(database, regular_user_token)
    group = service.create(UnitGroupCreate(name=unique_name("gico")))
    try:
        old_uuid = group.icon_uuid
        replacement = IconImage.generate("group-replacement")
        with pytest.raises(NoAccessError):
            icon_service(database, extra_user_token).upload(
                group.uuid, IconEntityType.UNIT_GROUP, replacement
            )
        updated = icon_service(database, regular_user_token).upload(
            group.uuid, IconEntityType.UNIT_GROUP, replacement
        )
        database.expire_all()
        stored = service.get(group.uuid)
        assert stored.icon_uuid == updated.uuid
        assert stored.icon_uuid != old_uuid
        assert (
            bytes(icon_service(database).get(updated.uuid).image_bin)
            == replacement
        )
        with pytest.raises(ValidationError):
            icon_service(database).get(old_uuid)
    finally:
        service.delete(group.uuid)


def test_group_count_limit(database, extra_user, extra_user_token) -> None:
    service = unit_group_service(database, extra_user_token)
    before, _ = _groups(service, limit=1)
    created = []
    with owner_setting(
        database,
        extra_user,
        extra_user_token,
        "pu_instance_user_max_group",
        8,
    ):
        try:
            created.extend(
                service.create(UnitGroupCreate(name=unique_name("glim")))
                for _ in range(max(8 - before, 0))
            )
            with pytest.raises(UnitGroupError, match="the limit is 8"):
                service.create(UnitGroupCreate(name=unique_name("glim")))
        finally:
            _delete_groups(service, created)
