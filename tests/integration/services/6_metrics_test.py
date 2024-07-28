import pytest

from app.configs.gql import get_metrics_service
from app.configs.sub_entities import InfoSubEntity


@pytest.mark.run(order=0)
def test_get_metrics(database) -> None:

    current_user = pytest.users[0]
    unit_metrics_service = get_metrics_service(InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    metrics = unit_metrics_service.get_instance_metrics()

    assert metrics.user_count >= 2
    assert metrics.unit_count >= 7
    assert metrics.repo_count >= 6
    assert metrics.unit_node_count >= 14
    assert metrics.unit_node_edge_count >= 1
