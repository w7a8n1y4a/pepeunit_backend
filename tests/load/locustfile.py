import random

from locust import HttpUser, between, task

from app import settings
from app.dto.enum import InstanceTrustStatus

REST_INSTANCES = f"{settings.pu_app_prefix}{settings.pu_api_v1_prefix}/instances"
GQL_PATH = f"{settings.pu_app_prefix}/graphql"
GQL_HEADERS = {"Content-Type": "application/json"}

TRUST_STATUS_REST = [item.value for item in InstanceTrustStatus]
TRUST_STATUS_GQL = [item.name for item in InstanceTrustStatus]

GET_INSTANCES_URLS_QUERY = """
query GetInstancesUrls($filters: InstanceFilterInput!) {
  getInstancesUrls(filters: $filters) {
    totalCount
    urls
  }
}
"""

GET_INSTANCES_REGISTRIES_QUERY = """
query GetInstancesRegistries($filters: InstanceFilterInput!) {
  getInstancesRegistries(filters: $filters) {
    totalCount
    registries {
      url
      platform
    }
  }
}
"""


def _random_pagination() -> dict:
    filters = {}
    if random.choice((True, False)):
        filters["offset"] = random.randint(0, 30)
    if random.choice((True, False)):
        filters["limit"] = random.randint(
            1, min(100, settings.pu_max_pagination_size)
        )
    return filters


def random_rest_filters() -> dict:
    params = _random_pagination()
    if random.choice((True, False)):
        params["trust_status"] = random.sample(
            TRUST_STATUS_REST,
            k=random.randint(1, len(TRUST_STATUS_REST)),
        )
    return params


def random_gql_filters() -> dict:
    filters = _random_pagination()
    if random.choice((True, False)):
        filters["trustStatus"] = random.sample(
            TRUST_STATUS_GQL,
            k=random.randint(1, len(TRUST_STATUS_GQL)),
        )
    return filters


def post_gql(client, query: str, variables: dict, name: str) -> None:
    with client.post(
        GQL_PATH,
        json={"query": query, "variables": variables},
        headers=GQL_HEADERS,
        name=name,
        catch_response=True,
    ) as response:
        if response.status_code != 200:
            response.failure(f"HTTP {response.status_code}")
            return
        body = response.json()
        if body.get("errors"):
            response.failure(str(body["errors"]))
            return
        response.success()


class InstanceBaseUser(HttpUser):
    abstract = True
    host = f"{settings.pu_http_type}://{settings.pu_domain}"
    wait_time = between(1, 1)


class InstanceRestUser(InstanceBaseUser):
    @task
    def current(self):
        self.client.get(f"{REST_INSTANCES}/current")

    @task
    def instances(self):
        self.client.get(
            REST_INSTANCES,
            params=random_rest_filters(),
            name=REST_INSTANCES,
        )


class InstanceGqlUser(InstanceBaseUser):
    @task
    def urls(self):
        post_gql(
            self.client,
            GET_INSTANCES_URLS_QUERY,
            {"filters": random_gql_filters()},
            "gql:getInstancesUrls",
        )

    @task
    def registries(self):
        post_gql(
            self.client,
            GET_INSTANCES_REGISTRIES_QUERY,
            {"filters": random_gql_filters()},
            "gql:getInstancesRegistries",
        )
