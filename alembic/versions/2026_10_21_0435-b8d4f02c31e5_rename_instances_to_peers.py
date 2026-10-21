"""rename instances to peers

Revision ID: b8d4f02c31e5
Revises: a7c3e91b20d4
Create Date: 2026-10-21 04:35:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "b8d4f02c31e5"
down_revision = "a7c3e91b20d4"
branch_labels = None
depends_on = None

# ClickHouse has no table or column for this entity.
# Longer tokens first, so ScanAllInstances is not touched by ScanInstance.
_TEXT_REPLACEMENTS = (
    ("ScanAllInstances", "ScanAllPeers"),
    ("Scan All Instances", "Scan All Peers"),
    ("ScanInstance", "ScanPeer"),
    ("Scan Instance", "Scan Peer"),
)

_NAMES = (
    ("ix_instances_uuid", "ix_peers_uuid"),
    ("instances_pkey", "peers_pkey"),
    ("instances_url_key", "peers_url_key"),
    (
        "instances_consecutive_success_count_not_null",
        "peers_consecutive_success_count_not_null",
    ),
    ("instances_create_datetime_not_null", "peers_create_datetime_not_null"),
    ("instances_trust_status_not_null", "peers_trust_status_not_null"),
    ("instances_url_not_null", "peers_url_not_null"),
    ("instances_uuid_not_null", "peers_uuid_not_null"),
)


def _rename_constraint(old: str, new: str) -> None:
    row = (
        op.get_bind()
        .execute(
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
        )
        .first()
    )
    if row is None:
        return
    op.execute(
        sa.text(
            f'ALTER TABLE "{row.relname}" RENAME CONSTRAINT "{old}" TO "{new}"'
        )
    )


def _rename_index(old: str, new: str) -> None:
    found = (
        op.get_bind()
        .execute(
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
        )
        .scalar()
    )
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


def _assert_absent(fragment: str) -> None:
    found = (
        op.get_bind()
        .execute(
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
        )
        .fetchall()
    )
    if found:
        names = ", ".join(row[0] for row in found)
        msg = f"names still contain {fragment}: {names}"
        raise RuntimeError(msg)


def upgrade() -> None:
    op.rename_table("instances", "peers")
    _rename_names(forward=True)
    # Collected state is a remote current-instance card from before the rename.
    op.execute(sa.text("UPDATE peers SET state = NULL"))
    _rewrite_stored_values(forward=True)
    _assert_absent("instances")


def downgrade() -> None:
    _rewrite_stored_values(forward=False)
    _rename_names(forward=False)
    op.rename_table("peers", "instances")
