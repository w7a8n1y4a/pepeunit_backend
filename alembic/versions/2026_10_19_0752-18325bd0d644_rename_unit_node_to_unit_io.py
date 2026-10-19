"""rename unit node to unit io

Revision ID: 18325bd0d644
Revises: 9a2f8797285e
Create Date: 2026-10-19 07:52:40.446739

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "18325bd0d644"
down_revision = "9a2f8797285e"
branch_labels = None
depends_on = None

# Autogenerate sees a rename as drop + create. The operations below keep the
# rows and only change names. Edge columns node_output_uuid and
# node_input_uuid become output_uuid and input_uuid in the same step.
_JSON_KEYS = (
    ('"unit_node_edge_count"', '"unit_io_edge_count"'),
    ('"unit_node_count"', '"unit_io_count"'),
    ('"unit_node_uuid"', '"unit_io_uuid"'),
    ('"unit_nodes"', '"unit_ios"'),
    ('"node_output_uuid"', '"output_uuid"'),
    ('"node_input_uuid"', '"input_uuid"'),
    (
        '"pu_datapipe_limit_unit_node_per_one_panel"',
        '"pu_datapipe_limit_unit_io_per_one_panel"',
    ),
)


def _rename_identifiers(forward: bool) -> None:
    if forward:
        expression = """
            replace(
                replace(
                    replace(
                        replace(old_name, 'units_nodes', 'units_io'),
                        'node_output_uuid', 'output_uuid'
                    ),
                    'node_input_uuid', 'input_uuid'
                ),
                'unit_node', 'unit_io'
            )
        """
        name_filter = """
            name LIKE '%units_nodes%'
            OR name LIKE '%unit_node%'
            OR name LIKE '%node_output_uuid%'
            OR name LIKE '%node_input_uuid%'
        """
    else:
        expression = """
            replace(
                replace(
                    replace(
                        replace(old_name, 'output_uuid', 'node_output_uuid'),
                        'input_uuid', 'node_input_uuid'
                    ),
                    'units_io', 'units_nodes'
                ),
                'unit_io', 'unit_node'
            )
        """
        name_filter = """
            name LIKE '%units_io%'
            OR name LIKE '%unit_io%'
            OR name LIKE '%output_uuid%'
            OR name LIKE '%input_uuid%'
        """
    op.execute(
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
                IF new_name <> old_name THEN
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


def _replace_json_keys(table: str, column: str, pairs: tuple[tuple[str, str], ...]) -> None:
    expression = f"{column}::text"
    where = []
    for old, new in pairs:
        expression = f"replace({expression}, '{old}', '{new}')"
        where.append(f"{column}::text LIKE '%{old}%'")
    op.execute(
        f"""
        UPDATE {table}
        SET {column} = ({expression})::jsonb
        WHERE {" OR ".join(where)}
        """
    )


def _rename_schema(forward: bool) -> None:
    if forward:
        op.rename_table("units_nodes_edges", "units_io_edges")
        op.rename_table("units_nodes", "units_io")
        op.rename_table("mtm_panels_unit_nodes", "mtm_panels_unit_ios")
        op.alter_column(
            "units_io_edges",
            "node_output_uuid",
            new_column_name="output_uuid",
        )
        op.alter_column(
            "units_io_edges",
            "node_input_uuid",
            new_column_name="input_uuid",
        )
        op.alter_column(
            "mtm_panels_unit_ios",
            "unit_node_uuid",
            new_column_name="unit_io_uuid",
        )
        op.alter_column(
            "permissions",
            "resource_unit_node_uuid",
            new_column_name="resource_unit_io_uuid",
        )
        op.alter_column(
            "instance_settings",
            "pu_datapipe_limit_unit_node_per_one_panel",
            new_column_name="pu_datapipe_limit_unit_io_per_one_panel",
        )
        return

    op.alter_column(
        "instance_settings",
        "pu_datapipe_limit_unit_io_per_one_panel",
        new_column_name="pu_datapipe_limit_unit_node_per_one_panel",
    )
    op.alter_column(
        "permissions",
        "resource_unit_io_uuid",
        new_column_name="resource_unit_node_uuid",
    )
    op.alter_column(
        "mtm_panels_unit_ios",
        "unit_io_uuid",
        new_column_name="unit_node_uuid",
    )
    op.alter_column(
        "units_io_edges", "input_uuid", new_column_name="node_input_uuid"
    )
    op.alter_column(
        "units_io_edges", "output_uuid", new_column_name="node_output_uuid"
    )
    op.rename_table("mtm_panels_unit_ios", "mtm_panels_unit_nodes")
    op.rename_table("units_io", "units_nodes")
    op.rename_table("units_io_edges", "units_nodes_edges")


def upgrade() -> None:
    _rename_schema(forward=True)
    _rename_identifiers(forward=True)
    op.execute(
        """
        UPDATE permissions
        SET resource_type = 'UnitIO'
        WHERE resource_type = 'UnitNode'
        """
    )
    op.execute(
        """
        UPDATE permissions
        SET agent_type = 'UnitIO'
        WHERE agent_type = 'UnitNode'
        """
    )
    op.execute(
        """
        UPDATE permissions
        SET resource_type = 'GrafanaUnitIO'
        WHERE resource_type = 'GrafanaUnitNode'
        """
    )
    op.execute(
        """
        UPDATE permissions
        SET agent_type = 'GrafanaUnitIO'
        WHERE agent_type = 'GrafanaUnitNode'
        """
    )
    _replace_json_keys("notifications", "data", _JSON_KEYS)
    _replace_json_keys("instances", "state", _JSON_KEYS)


def downgrade() -> None:
    _replace_json_keys(
        "instances",
        "state",
        tuple((new, old) for old, new in _JSON_KEYS),
    )
    _replace_json_keys(
        "notifications",
        "data",
        tuple((new, old) for old, new in _JSON_KEYS),
    )
    op.execute(
        """
        UPDATE permissions
        SET agent_type = 'GrafanaUnitNode'
        WHERE agent_type = 'GrafanaUnitIO'
        """
    )
    op.execute(
        """
        UPDATE permissions
        SET resource_type = 'GrafanaUnitNode'
        WHERE resource_type = 'GrafanaUnitIO'
        """
    )
    op.execute(
        """
        UPDATE permissions
        SET agent_type = 'UnitNode'
        WHERE agent_type = 'UnitIO'
        """
    )
    op.execute(
        """
        UPDATE permissions
        SET resource_type = 'UnitNode'
        WHERE resource_type = 'UnitIO'
        """
    )
    _rename_identifiers(forward=False)
    _rename_schema(forward=False)
