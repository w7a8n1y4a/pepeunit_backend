import random

from locust import HttpUser, between, task

from app import runtime, settings
from app.dto.enum import InstanceTrustStatus

REST_INSTANCES = f"{settings.pu_app_prefix}{settings.pu_api_v1_prefix}/instances"

TRUST_STATUS_REST = [item.value for item in InstanceTrustStatus]


def _random_pagination() -> dict:
    filters = {}
    if random.choice((True, False)):
        filters["offset"] = random.randint(0, 30)
    if random.choice((True, False)):
        filters["limit"] = random.randint(
            1, min(100, runtime.get().pu_instance_max_pagination_size)
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


class InstanceCatalogUser(InstanceBaseUser):
    @task
    def urls(self):
        self.client.get(
            f"{REST_INSTANCES}/urls",
            params=random_rest_filters(),
            name=f"{REST_INSTANCES}/urls",
        )

    @task
    def registries(self):
        self.client.get(
            f"{REST_INSTANCES}/registries",
            params=random_rest_filters(),
            name=f"{REST_INSTANCES}/registries",
        )
