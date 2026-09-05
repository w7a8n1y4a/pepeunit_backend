import pytest

from app import settings
from app.configs.errors import NoAccessError
from app.dto.agent.abc import AgentBackend
from app.dto.enum import CacheKey
from app.services.metrics_service import MetricsService
from tests.integration.helpers.services import metrics_service


def test_get_metrics(live_units, chain_edges, regular_user_token, database) -> None:
    unit_metrics_service = metrics_service(database, regular_user_token)
    metrics = unit_metrics_service.get_instance_metrics()

    assert metrics.user_count >= 2
    assert metrics.unit_count >= 9
    assert metrics.repository_registry_count >= 3
    assert metrics.repo_count >= 4
    assert metrics.unit_node_count >= 18
    assert metrics.unit_node_edge_count >= 1


def test_get_metrics_anonymous(live_units, database) -> None:
    metrics = metrics_service(database, None).get_instance_metrics()
    assert metrics.user_count >= 2


def test_get_metrics_backend_agent(database) -> None:
    backend_token = AgentBackend(name=settings.pu_domain).generate_agent_token()
    with pytest.raises(NoAccessError):
        metrics_service(database, backend_token).get_instance_metrics()


def test_get_public_metrics(
    live_units, chain_edges, regular_user_token, database
) -> None:
    service = metrics_service(database, regular_user_token)
    MetricsService._cache.clear()

    all_metrics = service.get_instance_metrics()
    public_metrics = service.get_instance_metrics(
        is_api=False, public_only=True
    )

    assert public_metrics.user_count == all_metrics.user_count
    assert 0 < public_metrics.repo_count <= all_metrics.repo_count
    assert 0 < public_metrics.unit_count <= all_metrics.unit_count
    assert 0 < public_metrics.unit_node_count <= all_metrics.unit_node_count
    assert (
        public_metrics.repository_registry_count
        <= all_metrics.repository_registry_count
    )
    assert (
        public_metrics.unit_node_edge_count
        <= all_metrics.unit_node_edge_count
    )


def test_get_public_metrics_without_token(live_units, database) -> None:
    metrics = metrics_service(database, None).get_instance_metrics(
        is_api=False,
        public_only=True,
    )
    assert metrics.user_count >= 2


def test_get_metrics_cache(live_units, regular_user_token, database) -> None:
    service = metrics_service(database, regular_user_token)
    MetricsService._cache.clear()

    metrics = service.get_instance_metrics()
    assert service.get_instance_metrics() is metrics
    assert CacheKey.INSTANCE_METRICS in MetricsService._cache

    public_metrics = service.get_instance_metrics(
        is_api=False, public_only=True
    )
    assert public_metrics is not metrics
    assert CacheKey.INSTANCE_METRICS_PUBLIC in MetricsService._cache
