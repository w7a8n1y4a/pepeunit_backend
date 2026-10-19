"""icons

Revision ID: c8f0a1b24e57
Revises: 7be9eda96c45
Create Date: 2026-10-19 01:00:00.000000

"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app import settings
from app.services.icon_image import IconImage

revision = "c8f0a1b24e57"
down_revision = "7be9eda96c45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "icons",
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("image_bin", sa.LargeBinary(), nullable=False),
        sa.Column("create_datetime", sa.DateTime(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("image_hash", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index("ix_icons_uuid", "icons", ["uuid"], unique=False)
    op.create_index("ix_icons_image_hash", "icons", ["image_hash"], unique=False)

    op.add_column("users", sa.Column("icon_uuid", sa.Uuid(), nullable=True))
    op.add_column("units", sa.Column("icon_uuid", sa.Uuid(), nullable=True))
    op.add_column(
        "repository_registry",
        sa.Column("icon_uuid", sa.Uuid(), nullable=True),
    )

    # icon_uuid is about to become required, so every existing row needs a PNG.
    conn = op.get_bind()
    # Same public key draws the same default icon on every instance.
    for row in conn.execute(
        sa.text("SELECT uuid, public_key FROM users WHERE icon_uuid IS NULL")
    ).all():
        _link_generated_icon(conn, "users", row.uuid, row.public_key)
    # Unit picture is a function of its uuid.
    for row in conn.execute(
        sa.text("SELECT uuid FROM units WHERE icon_uuid IS NULL")
    ).all():
        _link_generated_icon(conn, "units", row.uuid, str(row.uuid))
    # The single instance row is pictured from the domain.
    for row in conn.execute(
        sa.text("SELECT uuid FROM instance_settings WHERE icon_uuid IS NULL")
    ).all():
        _link_generated_icon(
            conn, "instance_settings", row.uuid, settings.pu_domain
        )
    # Registry picture is a function of repository_url.
    for row in conn.execute(
        sa.text(
            "SELECT uuid, repository_url FROM repository_registry "
            "WHERE icon_uuid IS NULL"
        )
    ).all():
        _link_generated_icon(
            conn, "repository_registry", row.uuid, row.repository_url
        )

    op.alter_column("users", "icon_uuid", nullable=False)
    op.alter_column("units", "icon_uuid", nullable=False)
    op.alter_column("instance_settings", "icon_uuid", nullable=False)
    op.alter_column("repository_registry", "icon_uuid", nullable=False)
    op.create_index("ix_users_icon_uuid", "users", ["icon_uuid"], unique=False)
    op.create_index("ix_units_icon_uuid", "units", ["icon_uuid"], unique=False)
    op.create_index(
        "ix_instance_settings_icon_uuid",
        "instance_settings",
        ["icon_uuid"],
        unique=False,
    )
    op.create_index(
        "ix_repository_registry_icon_uuid",
        "repository_registry",
        ["icon_uuid"],
        unique=False,
    )
    op.create_foreign_key(
        "users_icon_uuid_fkey",
        "users",
        "icons",
        ["icon_uuid"],
        ["uuid"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "units_icon_uuid_fkey",
        "units",
        "icons",
        ["icon_uuid"],
        ["uuid"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "instance_settings_icon_uuid_fkey",
        "instance_settings",
        "icons",
        ["icon_uuid"],
        ["uuid"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "repository_registry_icon_uuid_fkey",
        "repository_registry",
        "icons",
        ["icon_uuid"],
        ["uuid"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        CREATE FUNCTION icons_delete_linked() RETURNS trigger AS $$
        BEGIN
            IF OLD.icon_uuid IS NOT NULL THEN
                DELETE FROM icons WHERE uuid = OLD.icon_uuid;
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in ("users", "units", "instance_settings", "repository_registry"):
        op.execute(
            f"CREATE TRIGGER {table}_icon_delete AFTER DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION icons_delete_linked()"
        )


def downgrade() -> None:
    for table in ("users", "units", "instance_settings", "repository_registry"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_icon_delete ON {table}")
    op.execute("DROP FUNCTION IF EXISTS icons_delete_linked()")
    op.drop_constraint(
        "repository_registry_icon_uuid_fkey",
        "repository_registry",
        type_="foreignkey",
    )
    op.drop_constraint(
        "instance_settings_icon_uuid_fkey", "instance_settings", type_="foreignkey"
    )
    op.drop_constraint("units_icon_uuid_fkey", "units", type_="foreignkey")
    op.drop_constraint("users_icon_uuid_fkey", "users", type_="foreignkey")
    op.drop_index(
        "ix_repository_registry_icon_uuid", table_name="repository_registry"
    )
    op.drop_index("ix_instance_settings_icon_uuid", table_name="instance_settings")
    op.drop_index("ix_units_icon_uuid", table_name="units")
    op.drop_index("ix_users_icon_uuid", table_name="users")
    op.drop_column("repository_registry", "icon_uuid")
    op.drop_column("units", "icon_uuid")
    op.drop_column("users", "icon_uuid")
    op.alter_column("instance_settings", "icon_uuid", nullable=True)
    op.execute("UPDATE instance_settings SET icon_uuid = NULL")
    op.drop_index("ix_icons_image_hash", table_name="icons")
    op.drop_index("ix_icons_uuid", table_name="icons")
    op.drop_table("icons")


def _link_generated_icon(conn, table: str, entity_uuid, seed: str) -> None:
    image = IconImage.generate(seed)
    icon_uuid = uuid.uuid4()
    conn.execute(
        sa.text(
            "INSERT INTO icons "
            "(uuid, image_bin, create_datetime, size, image_hash) "
            "VALUES (:uuid, :image_bin, :create_datetime, :size, :image_hash)"
        ),
        {
            "uuid": icon_uuid,
            "image_bin": image,
            "create_datetime": datetime.now(UTC),
            "size": len(image),
            "image_hash": IconImage.md5(image),
        },
    )
    conn.execute(
        sa.text(f"UPDATE {table} SET icon_uuid = :icon_uuid WHERE uuid = :uuid"),
        {"icon_uuid": icon_uuid, "uuid": entity_uuid},
    )
