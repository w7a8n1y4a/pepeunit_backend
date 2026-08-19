from app import settings
from app.configs.errors import CustomJSONDecodeError
from app.services.validators import is_valid_json


def load_private_repo_specs() -> list[dict]:
    raw = settings.pu_test_integration_private_repo_json
    if not raw or not str(raw).strip():
        return []

    try:
        data = is_valid_json(raw, "Private Repo")
        if isinstance(data, str):
            data = is_valid_json(data, "Private Repo")
    except (CustomJSONDecodeError, TypeError, ValueError):
        return []

    if not isinstance(data, dict):
        return []

    items = data.get("data")
    if not isinstance(items, list) or not items:
        return []

    return items


def all_known_repo_urls() -> list[str]:
    urls = [
        settings.pu_test_integration_github_public_repo_url,
        settings.pu_test_integration_gitlab_public_repo_url,
        settings.pu_test_integration_universal_repo_url,
    ]
    for spec in load_private_repo_specs():
        link = spec.get("link")
        if link:
            urls.append(link)
    return urls
