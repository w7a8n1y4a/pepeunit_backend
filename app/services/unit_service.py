import base64
import copy
import itertools
import json
import os
import shutil
import zlib
from typing import Union

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status as http_status

from app import settings
from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.repositories.enum import UserRole, UnitNodeType, SchemaStructName
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.gql.inputs.unit import UnitCreateInput, UnitUpdateInput, UnitFilterInput
from app.schemas.mqtt.topic import mqtt
from app.schemas.pydantic.unit import UnitCreate, UnitUpdate, UnitFilter
from app.services.access_service import AccessService
from app.services.utils import creator_check, merge_two_dict_first_priority
from app.services.validators import is_valid_object, is_valid_json
from app.utils.utils import aes_decode, aes_encode


class UnitService:
    unit_repository = UnitRepository()
    repo_repository = RepoRepository()
    git_repo_repository = GitRepoRepository()
    unit_node_repository = UnitNodeRepository()
    access_service = AccessService()

    def __init__(
        self,
        unit_repository: UnitRepository = Depends(),
        repo_repository: RepoRepository = Depends(),
        unit_node_repository: UnitNodeRepository = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.unit_repository = unit_repository
        self.repo_repository = repo_repository
        self.unit_node_repository = unit_node_repository
        self.access_service = access_service

    def create(self, data: Union[UnitCreate, UnitCreateInput]) -> Unit:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        self.unit_repository.is_valid_name(data.name)

        repo = self.repo_repository.get(Repo(uuid=data.repo_uuid))

        is_valid_object(repo)

        self.is_valid_no_updated_unit(repo, data)

        self.git_repo_repository.is_valid_schema_file(repo, data.repo_commit)
        self.git_repo_repository.get_env_dict(repo, data.repo_commit)

        unit = Unit(creator_uuid=self.access_service.current_agent.uuid, **data.dict())
        unit = self.unit_repository.create(unit)
        unit_deepcopy = copy.deepcopy(unit)

        schema_dict = self.git_repo_repository.get_schema_dict(repo, data.repo_commit)

        unit_nodes_list = []
        for assignment, topic_list in schema_dict.items():
            for topic in topic_list:
                if assignment in [SchemaStructName.INPUT_TOPIC, SchemaStructName.OUTPUT_TOPIC]:
                    unit_nodes_list.append(
                        UnitNode(
                            type=UnitNodeType.INPUT
                            if assignment == SchemaStructName.INPUT_TOPIC
                            else UnitNodeType.OUTPUT,
                            visibility_level=unit.visibility_level,
                            topic_name=topic,
                            unit_uuid=unit.uuid,
                        )
                    )

        self.unit_node_repository.bulk_save(unit_nodes_list)

        return unit_deepcopy

    def get(self, uuid: str) -> Unit:
        # todo refactor unit доступ
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN], is_unit_available=True)
        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit)
        return unit

    def generate_token(self, uuid: str) -> str:
        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit)

        return self.access_service.generate_unit_token(unit)

    def update(self, uuid: str, data: Union[UnitUpdate, UnitUpdateInput]) -> Unit:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        unit = self.unit_repository.get(Unit(uuid=uuid))

        is_valid_object(unit)
        creator_check(self.access_service.current_agent, unit)

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        self.is_valid_no_updated_unit(repo, data)

        self.git_repo_repository.is_valid_schema_file(repo, data.repo_commit)
        self.git_repo_repository.get_env_dict(repo, data.repo_commit)

        self.unit_repository.is_valid_name(data.name, uuid)

        all_exist_unit_nodes = self.unit_node_repository.get_unit_nodes(unit)

        input_node_dict = {
            unit_node.topic_name: unit_node.uuid
            for unit_node in all_exist_unit_nodes
            if unit_node.type == UnitNodeType.INPUT
        }

        output_node_dict = {
            unit_node.topic_name: unit_node.uuid
            for unit_node in all_exist_unit_nodes
            if unit_node.type == UnitNodeType.OUTPUT
        }

        schema_dict = self.git_repo_repository.get_schema_dict(repo, data.repo_commit)

        # создаёт ноды отсутствующие у юнита
        unit_nodes_list = []
        for assignment, topic_list in schema_dict.items():
            for topic in topic_list:
                if (assignment == SchemaStructName.INPUT_TOPIC and topic not in input_node_dict.keys()) or (
                    assignment == SchemaStructName.OUTPUT_TOPIC and topic not in output_node_dict.keys()
                ):
                    unit_nodes_list.append(
                        UnitNode(
                            type=UnitNodeType.INPUT
                            if assignment == SchemaStructName.INPUT_TOPIC
                            else UnitNodeType.OUTPUT,
                            visibility_level=unit.visibility_level,
                            topic_name=topic,
                            unit_uuid=unit.uuid,
                        )
                    )

        self.unit_node_repository.bulk_save(unit_nodes_list)

        # удаляет ноды которых нет у юнита на данной версии
        unit_node_uuid_delete = []
        for assignment, topic_list in schema_dict.items():
            if assignment == SchemaStructName.INPUT_TOPIC:
                unit_node_uuid_delete.extend([input_node_dict[topic] for topic in input_node_dict.keys() - set(topic_list)])
            elif assignment == SchemaStructName.OUTPUT_TOPIC:
                unit_node_uuid_delete.extend(
                    [output_node_dict[topic] for topic in output_node_dict.keys() - set(topic_list)])

        self.unit_node_repository.delete(unit_node_uuid_delete)

        if 'update' in schema_dict['input_base_topic']:
            mqtt.publish(f"input_base/{unit.uuid}/update", "You need to upgrade")

        return self.unit_repository.update(uuid, unit)

    def get_env(self, uuid: str) -> dict:
        self.access_service.access_check([UserRole.USER], is_unit_available=True)

        unit = self.unit_repository.get(Unit(uuid=uuid))

        if not unit.cipher_env_dict:
            repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
            env_dict = self.git_repo_repository.get_env_example(repo, unit.repo_commit)
        else:
            env_dict = json.loads(aes_decode(unit.cipher_env_dict))

        return env_dict

    def set_env(self, uuid: str, env_json_str: str) -> None:
        self.access_service.access_check([UserRole.USER])

        env_dict = is_valid_json(env_json_str)
        unit = self.unit_repository.get(Unit(uuid=uuid))
        gen_env_dict = self.gen_env_dict(unit.uuid)
        merged_env_dict = merge_two_dict_first_priority(env_dict, gen_env_dict)

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        self.git_repo_repository.is_valid_env_file(repo, unit.repo_commit, merged_env_dict)

        print(merged_env_dict)

        unit.cipher_env_dict = aes_encode(json.dumps(merged_env_dict))

        self.unit_repository.update(unit.uuid, unit)

        return None

    def get_unit_firmware(self, uuid: str) -> str:
        unit = self.unit_repository.get(Unit(uuid=uuid))
        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))

        env_dict = self.get_env(unit.uuid)

        self.git_repo_repository.is_valid_env_file(repo, unit.repo_commit, env_dict)

        # todo refactor мб упаковать в git_repo_repository
        tmp_git_repo = self.git_repo_repository.get_tmp_repo(repo)
        tmp_git_repo.git.checkout(unit.repo_commit)

        tmp_git_repo_path = tmp_git_repo.working_tree_dir

        with open(f'{tmp_git_repo_path}/env.json', 'w') as f:
            f.write(json.dumps(env_dict, indent=4))

        del_path_list = [
            '.gitignore',
            'env_example.json',
            '.git',
            'docs',
            'model'
            'readme.md',
            'README.md'
        ]

        for path in del_path_list:
            merge_path = f'{tmp_git_repo_path}/{path}'

            if os.path.isfile(merge_path):
                os.remove(merge_path)
            else:
                shutil.rmtree(merge_path, ignore_errors=True)

        return tmp_git_repo_path

    def get_unit_firmware_zip(self, uuid: str) -> str:
        self.access_service.access_check([UserRole.USER], is_unit_available=True)

        firmware_path = self.get_unit_firmware(uuid)
        firmware_zip_path = f"tmp/{uuid}"

        shutil.make_archive(firmware_zip_path, 'zip', firmware_path)
        shutil.rmtree(firmware_path, ignore_errors=True)

        return f'{firmware_zip_path}.zip'

    def get_unit_firmware_tar(self, uuid: str) -> str:
        self.access_service.access_check([UserRole.USER], is_unit_available=True)

        firmware_path = self.get_unit_firmware(uuid)
        firmware_tar_path = f"tmp/{uuid}"

        shutil.make_archive(firmware_tar_path, 'tar', firmware_path)
        shutil.rmtree(firmware_path, ignore_errors=True)

        return f'{firmware_tar_path}.tar'

    def get_unit_firmware_tgz(self, uuid: str) -> str:
        self.access_service.access_check([UserRole.USER], is_unit_available=True)

        firmware_path = self.get_unit_firmware(uuid)
        firmware_tar_path = f"tmp/{uuid}"

        shutil.make_archive(firmware_tar_path, 'tar', firmware_path)
        shutil.rmtree(firmware_path, ignore_errors=True)

        with open(firmware_tar_path + '.tar', 'rb') as tar_file:
            producer = zlib.compressobj(wbits=9, level=9)
            tar_data = producer.compress(tar_file.read()) + producer.flush()

            with open(f'{firmware_tar_path}.tgz', 'wb') as tgz:
                tgz.write(tar_data)

        os.remove(firmware_tar_path + '.tar')

        return f'{firmware_tar_path}.tgz'

    def delete(self, uuid: str) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        unit = self.unit_repository.get(Unit(uuid=uuid))
        creator_check(self.access_service.current_agent, unit)

        return self.unit_repository.delete(unit)

    def list(self, filters: Union[UnitFilter, UnitFilterInput]) -> list[Unit]:
        self.access_service.access_check([UserRole.ADMIN])
        return self.unit_repository.list(filters)

    def gen_env_dict(self, uuid: str) -> dict:
        return {
            'PEPEUNIT_URL': settings.backend_domain,
            'MQTT_URL': settings.mqtt_host,
            'PEPEUNIT_TOKEN': self.generate_token(uuid),
            'SYNC_ENCRYPT_KEY': base64.b64encode(os.urandom(16)).decode('utf-8'),
            'SECRET_KEY': base64.b64encode(os.urandom(16)).decode('utf-8'),
            'PING_INTERVAL': 30,
            'STATE_SEND_INTERVAL': 30,  # todo на 300
        }

    def is_valid_no_updated_unit(self, repo: Repo, data: UnitCreate):
        if not data.is_auto_update_from_repo_unit and (not data.repo_branch or not data.repo_commit):
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid no auto updated unit")

        # проверка чтобы ветка и коммит существовали у репозитория
        if not data.is_auto_update_from_repo_unit:
            self.git_repo_repository.is_valid_branch(repo, data.repo_branch)
            self.git_repo_repository.is_valid_commit(repo, data.repo_branch, data.repo_commit)
