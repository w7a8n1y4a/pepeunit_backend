"""rename unit io edge to link

Revision ID: c3e8a14b70f2
Revises: b8d4f02c31e5
Create Date: 2026-10-21 05:12:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "c3e8a14b70f2"
down_revision = "b8d4f02c31e5"
branch_labels = None
depends_on = None

# ClickHouse has no table or column for this entity.
# units_io_edges columns are uuid, output_uuid, input_uuid, creator_uuid.
# A column is renamed only when its name still carries the old token,
# including a leftover unit_node_edge_uuid.
_TEXT_REPLACEMENTS = (
    ("unit_node_edge_count", "link_count"),
    ("unit_io_edge_count", "link_count"),
    ("unit_node_edge_uuid", "link_uuid"),
    ("unit_io_edge_uuid", "link_uuid"),
    ("UnitNodeEdge", "Link"),
    ("UnitIOEdge", "Link"),
)

_OLD_NAME_FILTER = """
    name LIKE '%units_nodes_edges%'
    OR name LIKE '%units_io_edges%'
    OR name LIKE '%unit_node_edge%'
    OR name LIKE '%unit_io_edge%'
"""

_NEW_NAME_FILTER = """
    name LIKE 'links%'
    OR name LIKE 'ix_links%'
    OR name LIKE '%link_count%'
    OR name LIKE '%link_uuid%'
"""


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


def _identifier_expression(forward: bool) -> str:
    if forward:
        return """
            replace(
                replace(
                    replace(
                        replace(
                            old_name,
                            'units_nodes_edges',
                            'links'
                        ),
                        'units_io_edges',
                        'links'
                    ),
                    'unit_node_edge',
                    'link'
                ),
                'unit_io_edge',
                'link'
            )
        """
    return """
        replace(
            replace(
                replace(
                    replace(
                        old_name,
                        'ix_links',
                        'ix_units_io_edges'
                    ),
                    'links_',
                    'units_io_edges_'
                ),
                'link_count',
                'unit_io_edge_count'
            ),
            'link_uuid',
            'unit_io_edge_uuid'
        )
    """


def _name_filter(forward: bool) -> str:
    return _OLD_NAME_FILTER if forward else _NEW_NAME_FILTER


def _rename_identifiers(forward: bool) -> None:
    expression = _identifier_expression(forward)
    name_filter = _name_filter(forward)
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE
                old_name text;
                new_name text;
                table_name text;
            BEGIN
                FOR old_name, table_name IN
                    SELECT con.conname, con.conrelid::regclass::text
                    FROM pg_constraint con
                    JOIN pg_namespace n ON n.oid = con.connamespace
                    WHERE n.nspname = 'public'
                      AND ({name_filter.replace("name", "con.conname")})
                LOOP
                    new_name := {expression};
                    IF new_name <> old_name THEN
                        EXECUTE format(
                            'ALTER TABLE %s RENAME CONSTRAINT %I TO %I',
                            table_name,
                            old_name,
                            new_name
                        );
                    END IF;
                END LOOP;

                FOR old_name IN
                    SELECT c.relname
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relkind = 'i'
                      AND ({name_filter.replace("name", "c.relname")})
                LOOP
                    new_name := {expression};
                    IF new_name <> old_name AND NOT EXISTS (
                        SELECT 1
                        FROM pg_class existing
                        JOIN pg_namespace ns
                          ON ns.oid = existing.relnamespace
                        WHERE ns.nspname = 'public'
                          AND existing.relname = new_name
                    ) THEN
                        EXECUTE format(
                            'ALTER INDEX %I RENAME TO %I',
                            old_name,
                            new_name
                        );
                    END IF;
                END LOOP;
            END $$;
            """
        )
    )


def _rename_columns(forward: bool) -> None:
    expression = _identifier_expression(forward)
    name_filter = _name_filter(forward)
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE
                old_name text;
                new_name text;
                table_name text;
            BEGIN
                FOR table_name, old_name IN
                    SELECT c.relname, a.attname
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid = a.attrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relkind = 'r'
                      AND a.attnum > 0
                      AND NOT a.attisdropped
                      AND ({name_filter.replace("name", "a.attname")})
                LOOP
                    new_name := {expression};
                    IF new_name <> old_name THEN
                        EXECUTE format(
                            'ALTER TABLE %I RENAME COLUMN %I TO %I',
                            table_name,
                            old_name,
                            new_name
                        );
                    END IF;
                END LOOP;
            END $$;
            """
        )
    )


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
            UPDATE peers
            SET state = ({state})::jsonb
            WHERE {_matches("state::text", forward)}
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
            UNION
            SELECT a.attname
            FROM pg_attribute AS a
            JOIN pg_class AS c ON c.oid = a.attrelid
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind = 'r'
              AND a.attnum > 0
              AND NOT a.attisdropped
              AND a.attname LIKE :fragment
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
    _rename_columns(forward=True)
    op.rename_table("units_io_edges", "links")
    _rename_identifiers(forward=True)
    _rewrite_stored_values(forward=True)
    _assert_absent("units_nodes_edges")
    _assert_absent("units_io_edges")
    _assert_absent("unit_node_edge")
    _assert_absent("unit_io_edge")


def downgrade() -> None:
    _rewrite_stored_values(forward=False)
    _rename_identifiers(forward=False)
    op.rename_table("links", "units_io_edges")
    _rename_columns(forward=False)
