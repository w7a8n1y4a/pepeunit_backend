from app.configs.rest import get_metrics_service


def test_get_metrics(live_units, chain_edges, regular_user_token, database) -> None:
    unit_metrics_service = get_metrics_service(database, regular_user_token)
    metrics = unit_metrics_service.get_instance_metrics()

    assert metrics.user_count >= 2
    assert metrics.unit_count >= 9
    assert metrics.repository_registry_count >= 3
    assert metrics.repo_count >= 4
    assert metrics.unit_node_count >= 18
    assert metrics.unit_node_edge_count >= 1
