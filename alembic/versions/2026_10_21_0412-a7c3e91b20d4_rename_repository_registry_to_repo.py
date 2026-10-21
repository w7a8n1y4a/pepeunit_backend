"""rename repository_registry to repo

Revision ID: a7c3e91b20d4
Revises: bd9baa244ec4
Create Date: 2026-10-21 04:12:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "a7c3e91b20d4"
down_revision = "bd9baa244ec4"
branch_labels = None
depends_on = None

# ClickHouse has no table or column for this entity.
# Old name, new name. repository_registry_uuid is replaced before the table
# token, so ix_repository_registry_uuid becomes ix_repo_uuid and
# ix_units_repository_registry_uuid becomes ix_units_repo_uuid.
_NAMES = (
    ("ix_repository_registry_icon_uuid", "ix_repo_icon_uuid"),
    ("ix_repository_registry_uuid", "ix_repo_uuid"),
    ("ix_units_repository_registry_uuid", "ix_units_repo_uuid"),
    ("repository_registry_pkey", "repo_pkey"),
    ("repository_registry_repository_url_key", "repo_repository_url_key"),
    ("repository_registry_creator_uuid_fkey", "repo_creator_uuid_fkey"),
    ("repository_registry_icon_uuid_fkey", "repo_icon_uuid_fkey"),
    ("units_repository_registry_uuid_fkey", "units_repo_uuid_fkey"),
    (
        "repository_registry_create_datetime_not_null",
        "repo_create_datetime_not_null",
    ),
    ("repository_registry_icon_uuid_not_null", "repo_icon_uuid_not_null"),
    (
        "repository_registry_is_public_repository_not_null",
        "repo_is_public_repository_not_null",
    ),
    (
        "repository_registry_last_update_datetime_not_null",
        "repo_last_update_datetime_not_null",
    ),
    (
        "repository_registry_local_repository_size_not_null",
        "repo_local_repository_size_not_null",
    ),
    ("repository_registry_platform_not_null", "repo_platform_not_null"),
    (
        "repository_registry_repository_url_not_null",
        "repo_repository_url_not_null",
    ),
    ("repository_registry_uuid_not_null", "repo_uuid_not_null"),
    (
        "units_repository_registry_uuid_not_null",
        "units_repo_uuid_not_null",
    ),
    (
        "instance_settings_pu_instance_registry_max_size_not_null",
        "instance_settings_pu_instance_repo_max_size_not_null",
    ),
    (
        "instance_settings_pu_instance_registry_min_interval_sy_not_null",
        "instance_settings_pu_instance_repo_min_interval_sync_not_null",
    ),
)

_TEXT_REPLACEMENTS = (
    ("UpdateAllRegistries", "UpdateAllRepos"),
    ("UpdateRegistry", "UpdateRepo"),
    ("Update All Registries", "Update All Repos"),
    ("Update Registry", "Update Repo"),
    ("repository_registry_uuid", "repo_uuid"),
    ("repository_registry_count", "repo_count"),
    ("pu_instance_registry_min_interval_sync", "pu_instance_repo_min_interval_sync"),
    ("pu_instance_registry_max_size", "pu_instance_repo_max_size"),
)


def _rename_constraint(old: str, new: str) -> None:
    row = op.get_bind().execute(
        sa.text(
            """
            SELECT t.relname
            FROM pg_constraint AS c
            JOIN pg_class AS t ON t.oid = c.conrelid
            JOIN pg_namespace AS n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public' AND c.conname = :name
            """
        ),
        {"name": old},
    ).first()
    if row is None:
        return
    op.execute(
        sa.text(
            f'ALTER TABLE "{row.relname}" RENAME CONSTRAINT "{old}" TO "{new}"'
        )
    )


def _rename_index(old: str, new: str) -> None:
    found = op.get_bind().execute(
        sa.text(
            """
            SELECT 1
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind = 'i'
              AND c.relname = :name
            """
        ),
        {"name": old},
    ).scalar()
    if found is None:
        return
    op.execute(sa.text(f'ALTER INDEX "{old}" RENAME TO "{new}"'))


def _rename_names(forward: bool) -> None:
    pairs = _NAMES if forward else tuple((new, old) for old, new in _NAMES)
    for old, new in pairs:
        _rename_constraint(old, new)
        _rename_index(old, new)


def _pairs(forward: bool) -> tuple[tuple[str, str], ...]:
    if forward:
        return _TEXT_REPLACEMENTS
    return tuple((new, old) for old, new in reversed(_TEXT_REPLACEMENTS))


def _replace_text(column: str, forward: bool) -> str:
    expression = column
    for old, new in _pairs(forward):
        expression = f"replace({expression}, '{old}', '{new}')"
    return expression


def _matches(column: str, forward: bool) -> str:
    tokens = [old for old, _new in _pairs(forward)]
    return " OR ".join(f"{column} LIKE '%{token}%'" for token in tokens)


def _rewrite_stored_values(forward: bool) -> None:
    task_type = _replace_text("task_type", forward)
    result = _replace_text("result", forward)
    op.execute(
        sa.text(
            f"""
            UPDATE operation_tasks
            SET task_type = {task_type},
                result = {result}
            WHERE {_matches("task_type", forward)}
               OR {_matches("result", forward)}
            """
        )
    )

    notification_type = _replace_text("type", forward)
    small_text = _replace_text("small_text", forward)
    table_text = _replace_text("table_text", forward)
    big_text = _replace_text("big_text", forward)
    data = _replace_text("data::text", forward)
    op.execute(
        sa.text(
            f"""
            UPDATE notifications
            SET type = {notification_type},
                small_text = {small_text},
                table_text = {table_text},
                big_text = {big_text},
                data = ({data})::jsonb
            WHERE {_matches("type", forward)}
               OR {_matches("small_text", forward)}
               OR {_matches("table_text", forward)}
               OR {_matches("big_text", forward)}
               OR {_matches("data::text", forward)}
            """
        )
    )

    state = _replace_text("state::text", forward)
    op.execute(
        sa.text(
            f"""
            UPDATE instances
            SET state = ({state})::jsonb
            WHERE {_matches("state::text", forward)}
            """
        )
    )


def _assert_absent(fragment: str) -> None:
    found = op.get_bind().execute(
        sa.text(
            """
            SELECT c.relname
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname LIKE :fragment
            UNION
            SELECT c.conname
            FROM pg_constraint AS c
            JOIN pg_class AS t ON t.oid = c.conrelid
            JOIN pg_namespace AS n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public' AND c.conname LIKE :fragment
            """
        ),
        {"fragment": f"%{fragment}%"},
    ).fetchall()
    if found:
        names = ", ".join(row[0] for row in found)
        msg = f"names still contain {fragment}: {names}"
        raise RuntimeError(msg)


def upgrade() -> None:
    op.rename_table("repository_registry", "repo")
    op.alter_column(
        "units", "repository_registry_uuid", new_column_name="repo_uuid"
    )
    op.alter_column(
        "instance_settings",
        "pu_instance_registry_max_size",
        new_column_name="pu_instance_repo_max_size",
    )
    op.alter_column(
        "instance_settings",
        "pu_instance_registry_min_interval_sync",
        new_column_name="pu_instance_repo_min_interval_sync",
    )
    _rename_names(forward=True)
    _rewrite_stored_values(forward=True)
    _assert_absent("repository_registry")
    _assert_absent("pu_instance_registry")


def downgrade() -> None:
    _rewrite_stored_values(forward=False)
    _rename_names(forward=False)
    op.alter_column(
        "instance_settings",
        "pu_instance_repo_min_interval_sync",
        new_column_name="pu_instance_registry_min_interval_sync",
    )
    op.alter_column(
        "instance_settings",
        "pu_instance_repo_max_size",
        new_column_name="pu_instance_registry_max_size",
    )
    op.alter_column("units", "repo_uuid", new_column_name="repository_registry_uuid")
    op.rename_table("repo", "repository_registry")
