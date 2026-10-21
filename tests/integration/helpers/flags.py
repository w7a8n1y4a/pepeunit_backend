from collections.abc import Callable

import pytest

from app import runtime, settings
from tests.integration.helpers.private_repos import load_private_repo_specs

MARKER_ENABLED: dict[str, Callable[[], bool]] = {
    "telegram": lambda: runtime.get().pu_ff_telegram_bot_enable,
    "grafana": lambda: runtime.get().pu_ff_grafana_integration_enable,
    "datapipe": lambda: runtime.get().pu_ff_datapipe_enable,
    "last_value": lambda: (
        runtime.get().pu_ff_datapipe_enable
        and runtime.get().pu_datapipe_default_last_value_enable
    ),
    "prometheus": lambda: runtime.get().pu_ff_prometheus_enable,
    "federation": lambda: runtime.get().pu_ff_federation_enable,
    "notification": lambda: runtime.get().pu_ff_notification_enable,
    "private_repo": lambda: (
        settings.pu_test_integration_private_repo_enable
        and bool(load_private_repo_specs())
    ),
}

FIXTURE_MARKERS = {
    "grafana_dashboards": "grafana",
    "grafana_panels": "grafana",
    "piped_units": "datapipe",
    "own_peer": "federation",
    "trusted_peers": "federation",
    "unreachable_peer": "federation",
    "private_repo_enabled": "private_repo",
    "private_repos": "private_repo",
    "private_repo": "private_repo",
}


def _disabled_markers() -> set[str]:
    return {name for name, enabled in MARKER_ENABLED.items() if not enabled()}


def _item_gate_markers(item: pytest.Item) -> set[str]:
    names = {
        marker.name
        for marker in item.iter_markers()
        if marker.name in MARKER_ENABLED
    }
    for fixture in getattr(item, "fixturenames", ()):
        marker = FIXTURE_MARKERS.get(fixture)
        if marker:
            names.add(marker)
    return names


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    disabled = _disabled_markers()
    if not disabled:
        return

    remaining: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if _item_gate_markers(item) & disabled:
            deselected.append(item)
        else:
            remaining.append(item)

    if not deselected:
        return

    config.hook.pytest_deselected(items=deselected)
    items[:] = remaining


@pytest.fixture(scope="session")
def private_repo_enabled() -> list[dict]:
    return load_private_repo_specs()
