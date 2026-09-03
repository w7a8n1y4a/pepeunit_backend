from locust import HttpUser, between, task

from app import settings


class CurrentInstanceUser(HttpUser):
    host = f"{settings.pu_http_type}://{settings.pu_domain}"
    wait_time = between(1, 1)

    @task
    def test_current_instance(self):
        self.client.get("/pepeunit/api/v1/instances/current")


class CurrentInstanceGQLUser(HttpUser):
    host = f"{settings.pu_http_type}://{settings.pu_domain}"
    wait_time = between(1, 1)

    @task
    def test_gql_query(self):
        headers = {"Content-Type": "application/json"}
        graphql_query = {
            "query": """
            {
              getCurrentInstance {
                metrics {
                  userCount
                  repoCount
                  unitCount
                  unitNodeCount
                  unitNodeEdgeCount
                }
              }
            }
            """
        }
        self.client.post(
            f"{self.host}/pepeunit/graphql", json=graphql_query, headers=headers
        )
