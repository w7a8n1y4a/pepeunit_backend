import asyncio
import json
import logging

import httpx

from app.dto.enum import GitPlatform, ProcessingPolicyType
from tests.load.src.dto.config import LoadTestConfig


class RestClient:
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        user = {
            "login": f"test_{self.config.test_hash}",
            "password": self.config.test_hash + "/",
        }

        create_user_link = f"{self.config.url}/pepeunit/api/v1/users"
        httpx.post(create_user_link, json=user, headers=self.headers)

        user["credentials"] = user.pop("login")

        auth_link = f"{self.config.url}/pepeunit/api/v1/users/auth"
        self.token = httpx.post(auth_link, json=user, headers=self.headers).json()[
            "token"
        ]
        self.headers["x-auth-token"] = self.token

    def get_repo(self):
        target_registry_link = (
            "https://git.pepemoss.com/pepe/pepeunit/units/universal_load_unit.git"
        )

        registry_link = f"{self.config.url}/pepeunit/api/v1/repository_registry?search_string={target_registry_link}"
        target_registry = httpx.get(registry_link, headers=self.headers)

        target_registry = target_registry.json()

        if target_registry["count"] == 0:
            registry_create_link = (
                f"{self.config.url}/pepeunit/api/v1/repository_registry"
            )

            registry = {
                "platform": GitPlatform.GITLAB,
                "repository_url": target_registry_link,
                "is_public_repository": True,
            }

            target_registry = httpx.post(
                registry_create_link, json=registry, headers=self.headers
            ).json()
        else:
            target_registry = target_registry["repositories_registry"][0]

        repo = {
            "repository_registry_uuid": target_registry["uuid"],
            "default_branch": target_registry["branches"][0],
            "visibility_level": "Public",
            "name": f"test_{self.config.test_hash}",
            "is_compilable_repo": False,
        }

        repo_link = f"{self.config.url}/pepeunit/api/v1/repos"

        response = httpx.post(repo_link, json=repo, headers=self.headers)

        if response.status_code == 422:
            repo_link += f"?search_string={repo['name']}"
            response = httpx.get(repo_link, headers=self.headers)

        response = response.json()
        target_repo = response["repos"][0] if "repos" in response else response

        update_repo_link = (
            f"{self.config.url}/pepeunit/api/v1/repos/{target_repo['uuid']}"
        )
        httpx.patch(
            update_repo_link,
            json={"default_branch": target_registry["branches"][0]},
            headers=self.headers,
        )

        return target_repo

    async def del_units(self):
        logging.warning("Run del old Units")
        get_units = f"{self.config.url}/pepeunit/api/v1/units?search_string={self.config.test_hash}"
        units = httpx.get(get_units, headers=self.headers).json()

        if units["count"] > 0:
            async with httpx.AsyncClient() as client:
                unit_uuids = [unit["uuid"] for unit in units["units"]]
                await self.run_tasks_with_semaphore(
                    client, unit_uuids, self.delete_unit
                )
                logging.warning(f"Deleted {len(unit_uuids)} Units")

    async def create_units(self, target_repo: dict):
        logging.warning("Run create new Units")

        unit_create_link = f"{self.config.url}/pepeunit/api/v1/units"
        responses = []

        async with httpx.AsyncClient() as client:
            units = [
                {
                    "repo_uuid": target_repo["uuid"],
                    "visibility_level": "Public",
                    "name": f"test_{i}_{self.config.test_hash}",
                    "is_auto_update_from_repo_unit": True,
                }
                for i in range(self.config.unit_count)
            ]

            await self.run_tasks_with_semaphore(
                client, units, self.post_request, unit_create_link, responses
            )

        logging.warning(f"Created {len(responses)} Units")

        return responses

    def get_units(self):
        logging.warning("Fetch all Units")
        get_units = f"{self.config.url}/pepeunit/api/v1/units?is_include_output_unit_nodes=true&search_string={self.config.test_hash}"
        return httpx.get(get_units, headers=self.headers).json()["units"]

    async def create_units_env(self, target_units: list[dict]):
        logging.warning("Run create env Units")

        async with httpx.AsyncClient() as client:
            await self.run_tasks_with_semaphore(
                client, target_units, self.patch_unit_env
            )

        logging.warning(f"Created {len(target_units)} env Units")

    async def set_data_pipe(self, target_units: list[dict]):
        logging.warning("Run set data pipe")

        target_unit_nodes = []
        for unit in target_units:
            for node in unit["unit_nodes"]:
                if node["type"] == "Output" and node["topic_name"] == "output/pepeunit":
                    target_unit_nodes.append(node)

        async with httpx.AsyncClient() as client:
            await self.run_tasks_with_semaphore(
                client, target_unit_nodes, self.patch_unit_data_pipe
            )

        logging.warning(f"Set {len(target_unit_nodes)} data pipe")

    async def get_units_env(self, target_units: list[dict]):
        logging.warning("Fetch env Units")

        async with httpx.AsyncClient() as client:
            updated_units = await self.run_tasks_with_semaphore(
                client, target_units, self.get_unit_env
            )

        logging.warning(f"Fetched env for {len(target_units)} Units")
        return updated_units

    async def generation_units(self, target_repo: dict):
        await self.del_units()
        await self.create_units(target_repo)
        created_units = self.get_units()
        await self.create_units_env(created_units)
        await self.set_data_pipe(created_units)
        return await self.get_units_env(created_units)

    async def run_tasks_with_semaphore(self, client, items, func, *args):
        semaphore = asyncio.Semaphore(10)
        tasks = [
            self.run_with_semaphore(semaphore, func, client, item, *args)
            for item in items
        ]
        return await asyncio.gather(*tasks)

    async def run_with_semaphore(self, semaphore, func, client, item, *args):
        async with semaphore:
            return await func(client, item, *args)

    async def delete_unit(self, client, unit_id):
        delete_url = f"{self.config.url}/pepeunit/api/v1/units/{unit_id}"
        await client.delete(delete_url, headers=self.headers)

    async def post_request(self, client, unit, url, responses):
        response = await client.post(url, json=unit, headers=self.headers)
        responses.append(response.json())

    async def patch_unit_env(self, client, unit):
        unit_env_link = f"{self.config.url}/pepeunit/api/v1/units/env/{unit['uuid']}"
        payload = {"env_json_string": '{"PING_INTERVAL": 30}'}
        return await client.patch(unit_env_link, json=payload, headers=self.headers)

    async def patch_unit_data_pipe(self, client, unit_node):
        unit_nodes_update_link = (
            f"{self.config.url}/pepeunit/api/v1/unit_nodes/{unit_node['uuid']}"
        )
        payload = {"is_data_pipe_active": True}

        await client.patch(unit_nodes_update_link, json=payload, headers=self.headers)

        set_data_pipe_config = f"{self.config.url}/pepeunit/api/v1/unit_nodes/set_data_pipe_config?uuid={unit_node['uuid']}&is_bot_auth=false"

        data_pipe_policy = {
            ProcessingPolicyType.AGGREGATION.value: "tests/data/yaml/load/data_pipe_aggregation.yaml",
            ProcessingPolicyType.LAST_VALUE.value: "tests/data/yaml/load/data_pipe_last_value.yaml",
            ProcessingPolicyType.N_RECORDS.value: "tests/data/yaml/load/data_pipe_n_records.yaml",
            ProcessingPolicyType.TIME_WINDOW.value: "tests/data/yaml/load/data_pipe_time_window.yaml",
        }

        file_path = data_pipe_policy[self.config.policy_type]
        with open(file_path, "rb") as f:
            files = {"data": (file_path.split("/")[-1], f, "application/yaml")}
            header = {"x-auth-token": self.token}
            return await client.post(set_data_pipe_config, files=files, headers=header)

    async def get_unit_env(self, client, unit: dict):
        unit_env_link = f"{self.config.url}/pepeunit/api/v1/units/env/{unit['uuid']}"
        response = await client.get(unit_env_link, headers=self.headers)
        if response.status_code == 200:
            unit["env"] = json.loads(json.loads(response.text))
        else:
            unit["env"] = None
        return unit
