import asyncio
import base64
import hashlib
import json
import logging

import httpx
from cryptography.hazmat.primitives.asymmetric.mldsa import (
    MLDSA87PrivateKey,
)

from app import runtime
from app.dto.enum import GitPlatform, ProcessingPolicyType
from tests.load.src.dto.config import LoadTestConfig


class RestClient:
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        private_key = MLDSA87PrivateKey.generate()
        raw_public_key = private_key.public_key().public_bytes_raw()
        public_key = base64.b64encode(raw_public_key).decode("ascii")
        hash_public_key = hashlib.sha256(raw_public_key).hexdigest()

        create_user_link = f"{self.config.url}/pepeunit/api/v1/users"
        httpx.post(
            create_user_link,
            json={"public_key": public_key},
            headers=self.headers,
            timeout=runtime.get().http_timeout(),
        )

        challenge_link = (
            f"{self.config.url}/pepeunit/api/v1/users/auth/challenge"
        )
        challenge = httpx.post(
            challenge_link,
            json={"hash_public_key": hash_public_key},
            headers=self.headers,
            timeout=runtime.get().http_timeout(),
        ).json()["challenge"]
        signature = base64.b64encode(
            private_key.sign(challenge.encode("utf-8"))
        ).decode("ascii")

        auth_link = f"{self.config.url}/pepeunit/api/v1/users/auth"
        self.token = httpx.post(
            auth_link,
            json={"challenge": challenge, "signature": signature},
            headers=self.headers,
            timeout=runtime.get().http_timeout(),
        ).json()["token"]
        self.headers["x-auth-token"] = self.token

    def get_repo(self):
        target_registry_link = (
            "https://git.pepemoss.com/pepe/pepeunit/units/universal_load_unit.git"
        )

        registry_link = f"{self.config.url}/pepeunit/api/v1/repository_registry?search_string={target_registry_link}"
        target_registry = httpx.get(
            registry_link,
            headers=self.headers,
            timeout=runtime.get().http_timeout(),
        )

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
                registry_create_link,
                json=registry,
                headers=self.headers,
                timeout=runtime.get().http_timeout(),
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

        response = httpx.post(
            repo_link,
            json=repo,
            headers=self.headers,
            timeout=runtime.get().http_timeout(),
        )

        if response.status_code == 422:
            repo_link += f"?search_string={repo['name']}"
            response = httpx.get(
                repo_link,
                headers=self.headers,
                timeout=runtime.get().http_timeout(),
            )

        response = response.json()
        target_repo = response["repos"][0] if "repos" in response else response

        update_repo_link = (
            f"{self.config.url}/pepeunit/api/v1/repos/{target_repo['uuid']}"
        )
        httpx.patch(
            update_repo_link,
            json={
                "default_branch": target_registry["branches"][0],
                "is_auto_update_repo": True,
                "is_only_tag_update": False,
            },
            headers=self.headers,
            timeout=runtime.get().http_timeout(),
        )

        return target_repo

    async def del_units(self):
        logging.warning("Run del old Units")
        units = self.get_units()

        if units:
            async with httpx.AsyncClient(
                timeout=runtime.get().http_timeout()
            ) as client:
                unit_uuids = [unit["uuid"] for unit in units]
                await self.run_tasks_with_semaphore(
                    client, unit_uuids, self.delete_unit
                )
                logging.warning(f"Deleted {len(unit_uuids)} Units")

    async def create_units(self, target_repo: dict):
        logging.warning("Run create new Units")

        unit_create_link = f"{self.config.url}/pepeunit/api/v1/units"
        responses = []

        async with httpx.AsyncClient(
            timeout=runtime.get().http_timeout()
        ) as client:
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
        get_units = f"{self.config.url}/pepeunit/api/v1/units?is_include_output_unit_ios=true&search_string={self.config.test_hash}"

        limit = runtime.get().pu_instance_max_pagination_size

        units = []
        while True:
            page = httpx.get(
                f"{get_units}&offset={len(units)}&limit={limit}",
                headers=self.headers,
                timeout=runtime.get().http_timeout(),
            ).json()
            units.extend(page["units"])

            if len(units) >= page["count"] or not page["units"]:
                return units

    async def create_units_env(self, target_units: list[dict]):
        logging.warning("Run create env Units")

        async with httpx.AsyncClient(
            timeout=runtime.get().http_timeout()
        ) as client:
            await self.run_tasks_with_semaphore(
                client, target_units, self.patch_unit_env
            )

        logging.warning(f"Created {len(target_units)} env Units")

    async def set_data_pipe(self, target_units: list[dict]):
        logging.warning("Run set data pipe")

        target_unit_ios = []
        for unit in target_units:
            for node in unit["unit_ios"]:
                if node["type"] == "Output" and node["topic_name"] == "output/pepeunit":
                    target_unit_ios.append(node)

        async with httpx.AsyncClient(
            timeout=runtime.get().http_timeout()
        ) as client:
            await self.run_tasks_with_semaphore(
                client, target_unit_ios, self.patch_unit_data_pipe
            )

        logging.warning(f"Set {len(target_unit_ios)} data pipe")

    async def get_units_env(self, target_units: list[dict]):
        logging.warning("Fetch env Units")

        async with httpx.AsyncClient(
            timeout=runtime.get().http_timeout()
        ) as client:
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
        payload = {"env_json_string": '{"PU_MQTT_PING_INTERVAL": 30}'}
        return await client.patch(unit_env_link, json=payload, headers=self.headers)

    async def patch_unit_data_pipe(self, client, unit_io):
        unit_ios_update_link = (
            f"{self.config.url}/pepeunit/api/v1/unit_ios/{unit_io['uuid']}"
        )
        payload = {"is_data_pipe_active": True}

        await client.patch(unit_ios_update_link, json=payload, headers=self.headers)

        set_data_pipe_config = f"{self.config.url}/pepeunit/api/v1/unit_ios/set_data_pipe_config?uuid={unit_io['uuid']}&is_bot_auth=false"

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
            unit["env"] = json.loads(response.text)
        else:
            unit["env"] = None
        return unit
