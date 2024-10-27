select
    units,
    (
        select json_agg(un) as test
        from units_nodes as un
            join units_nodes_edges as une on un.uuid = une.node_output_uuid
        where
            une.node_input_uuid = '8d303112-f270-4ab6-894e-eff6e1e35b8b'
            and un.unit_uuid = units.uuid
    ) as edges
from units
    join units_nodes on units.uuid = units_nodes.unit_uuid
    join units_nodes_edges on units_nodes.uuid = units_nodes_edges.node_output_uuid
where
    units_nodes_edges.node_input_uuid = '8d303112-f270-4ab6-894e-eff6e1e35b8b';