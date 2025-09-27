from locust import HttpUser, between, task

from app import settings


class MetricsUser(HttpUser):
    host = f"{settings.backend_http_type}://{settings.backend_domain}"
    wait_time = between(1, 1)

    @task
    def test_endpoint(self):
        self.client.get("/pepeunit/api/v1/metrics/")


class MetricsGQLUser(HttpUser):
    host = f"{settings.backend_http_type}://{settings.backend_domain}"
    wait_time = between(1, 1)

    @task
    def test_gql_query(self):
        headers = {"Content-Type": "application/json"}
        graphql_query = {
            "query": """
            {
              getBaseMetrics {
                userCount
                repoCount
                unitCount
                unitNodeCount
                unitNodeEdgeCount
              }
            }
            """
        }
        self.client.post(
            f"{self.host}/pepeunit/graphql", json=graphql_query, headers=headers
        )


class RootUser(HttpUser):
    host = f"{settings.backend_http_type}://{settings.backend_domain}"
    wait_time = between(1, 1)

    @task
    def test_pepeunit(self):
        self.client.get("/pepeunit")
