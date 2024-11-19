import base64
import copy
import datetime
import itertools
import json
import logging
import os
import shutil
import uuid as uuid_pkg
import zlib
from typing import List, Optional, Union

from fastapi import Depends, HTTPException
from fastapi import status as http_status

from app import settings
from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.repositories.enum import (
    DestinationTopicType,
    GlobalPrefixTopic,
    PermissionEntities,
    ReservedInputBaseTopic,
    UnitNodeTypeEnum,
    UserRole,
)
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.gql.inputs.unit import UnitCreateInput, UnitFilterInput, UnitUpdateInput
from app.schemas.gql.types.shared import UnitNodeType
from app.schemas.gql.types.unit import UnitType
from app.schemas.mqtt.utils import get_topic_split
from app.schemas.pydantic.shared import UnitNodeRead
from app.schemas.pydantic.unit import UnitCreate, UnitFilter, UnitRead, UnitUpdate
from app.schemas.pydantic.unit_node import UnitNodeFilter
from app.services.access_service import AccessService
from app.services.unit_node_service import UnitNodeService
from app.services.utils import get_topic_name, merge_two_dict_first_priority, remove_none_value_dict
from app.services.validators import is_valid_json, is_valid_object, is_valid_uuid
from app.utils.utils import aes_decode, aes_encode


class UnitService:
    def __init__(
        self,
        unit_repository: UnitRepository = Depends(),
        repo_repository: RepoRepository = Depends(),
        unit_node_repository: UnitNodeRepository = Depends(),
        access_service: AccessService = Depends(),
        unit_node_service: UnitNodeService = Depends(),
    ) -> None:
        self.unit_repository = unit_repository
        self.repo_repository = repo_repository
        self.git_repo_repository = GitRepoRepository()
        self.unit_node_repository = unit_node_repository
        self.access_service = access_service
        self.unit_node_service = unit_node_service

    def create(self, data: Union[UnitCreate, UnitCreateInput]) -> Unit:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])
        self.unit_repository.is_valid_name(data.name)

        repo = self.repo_repository.get(Repo(uuid=data.repo_uuid))
        is_valid_object(repo)
        self.repo_repository.is_valid_auto_updated_repo(repo)
        self.is_valid_no_auto_updated_unit(repo, data)

        if data.is_auto_update_from_repo_unit:
            self.git_repo_repository.is_valid_branch(repo, repo.default_branch)
        else:
            self.git_repo_repository.is_valid_branch(repo, data.repo_branch)
            self.git_repo_repository.is_valid_schema_file(repo, data.repo_commit)
            self.git_repo_repository.get_env_dict(repo, data.repo_commit)

        unit = Unit(creator_uuid=self.access_service.current_agent.uuid, **data.dict())
        target_commit = self.get_unit_target_version(repo, unit)

        schema_dict = self.git_repo_repository.get_schema_dict(repo, target_commit)

        unit = self.unit_repository.create(unit)
        unit_deepcopy = copy.deepcopy(unit)

        self.access_service.create_permission(self.access_service.current_agent, unit)
        self.access_service.create_permission(unit, unit)

        self.unit_node_service.bulk_create(schema_dict, unit, False)

        return unit_deepcopy

    def get(self, uuid: uuid_pkg.UUID) -> Unit:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN], is_unit_available=True)
        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit)
        self.access_service.visibility_check(unit)
        return unit

    def update(self, uuid: uuid_pkg.UUID, data: Union[UnitUpdate, UnitUpdateInput]) -> Unit:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        unit = self.unit_repository.get(Unit(uuid=uuid))

        is_valid_object(unit)
        self.access_service.access_creator_check(unit)

        unit_update = Unit(**merge_two_dict_first_priority(remove_none_value_dict(data.dict()), unit.dict()))

        self.unit_repository.is_valid_name(unit_update.name, uuid)

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        self.is_valid_no_auto_updated_unit(repo, unit_update)

        if not unit_update.is_auto_update_from_repo_unit and unit.current_commit_version != unit_update.repo_commit:

            self.git_repo_repository.is_valid_schema_file(repo, unit_update.repo_commit)
            env_dict = self.git_repo_repository.get_env_dict(repo, unit_update.repo_commit)

            if unit.cipher_env_dict:
                self.git_repo_repository.is_valid_env_file(
                    repo, unit_update.repo_commit, json.loads(aes_decode(unit.cipher_env_dict))
                )

                self.is_valid_cipher_env(unit_update, env_dict)

                self.update_firmware(unit, unit_update.repo_commit)

        return self.unit_repository.update(uuid, unit_update)

    def update_firmware(self, unit: Unit, target_version: str) -> Unit:
        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))

        count, all_exist_unit_nodes = self.unit_node_repository.list(UnitNodeFilter(unit_uuid=unit.uuid))

        input_node_dict = {
            unit_node.topic_name: unit_node.uuid
            for unit_node in all_exist_unit_nodes
            if unit_node.type == UnitNodeTypeEnum.INPUT
        }

        output_node_dict = {
            unit_node.topic_name: unit_node.uuid
            for unit_node in all_exist_unit_nodes
            if unit_node.type == UnitNodeTypeEnum.OUTPUT
        }

        schema_dict = self.git_repo_repository.get_schema_dict(repo, target_version)

        self.unit_node_service.bulk_update(schema_dict, unit, input_node_dict, output_node_dict)

        if ReservedInputBaseTopic.UPDATE + GlobalPrefixTopic.BACKEND_SUB_PREFIX in schema_dict['input_base_topic']:

            try:
                from app.schemas.mqtt.topic import mqtt
            except ImportError:
                # this UnitNodeService entity imported in mqtt schema layer
                pass

            try:
                mqtt.publish(
                    f"{settings.backend_domain}/{DestinationTopicType.INPUT_BASE_TOPIC}/{unit.uuid}/{ReservedInputBaseTopic.UPDATE}{GlobalPrefixTopic.BACKEND_SUB_PREFIX}",
                    json.dumps({"NEW_COMMIT_VERSION": target_version}),
                )
            except AttributeError:
                logging.info('MQTT session is invalid')

        unit.last_update_datetime = datetime.datetime.utcnow()
        return self.unit_repository.update(unit.uuid, unit)

    def get_env(self, uuid: uuid_pkg.UUID) -> dict:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN], is_unit_available=True)

        unit = self.unit_repository.get(Unit(uuid=uuid))

        self.access_service.access_only_creator_and_target_unit(unit)

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        target_version = self.get_unit_target_version(repo, unit)
        env_dict = self.git_repo_repository.get_env_example(repo, target_version)

        if unit.cipher_env_dict:
            current_unit_env_dict = json.loads(aes_decode(unit.cipher_env_dict))
            env_dict = merge_two_dict_first_priority(current_unit_env_dict, env_dict)

        return env_dict

    def set_env(self, uuid: uuid_pkg.UUID, env_json_str: str) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        env_dict = is_valid_json(env_json_str)
        unit = self.unit_repository.get(Unit(uuid=uuid))

        self.access_service.access_creator_check(unit)

        gen_env_dict = self.gen_env_dict(unit.uuid)
        merged_env_dict = merge_two_dict_first_priority(env_dict, gen_env_dict)

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        target_version = self.get_unit_target_version(repo, unit)

        self.git_repo_repository.is_valid_env_file(repo, target_version, merged_env_dict)

        unit.cipher_env_dict = aes_encode(json.dumps(merged_env_dict))
        self.unit_repository.update(unit.uuid, unit)

        return None

    def update_schema(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN], is_unit_available=True)
        unit = self.unit_repository.get(Unit(uuid=uuid))

        is_valid_object(unit)

        self.access_service.access_only_creator_and_target_unit(unit)

        try:
            from app.schemas.mqtt.topic import mqtt
        except ImportError:
            # this UnitNodeService entity imported in mqtt schema layer
            pass

        try:
            mqtt.publish(
                f"{settings.backend_domain}/{DestinationTopicType.INPUT_BASE_TOPIC}/{unit.uuid}/{ReservedInputBaseTopic.SCHEMA_UPDATE}{GlobalPrefixTopic.BACKEND_SUB_PREFIX}",
                '{"": ""}',
            )
        except AttributeError:
            logging.info('MQTT session is invalid')

    def get_current_schema(self, uuid: uuid_pkg.UUID) -> dict:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN], is_unit_available=True)
        unit = self.unit_repository.get(Unit(uuid=uuid))

        is_valid_object(unit)

        self.access_service.access_only_creator_and_target_unit(unit)

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        target_version = self.get_unit_target_version(repo, unit)

        return self.generate_current_schema(unit, repo, target_version)

    def get_unit_firmware(self, uuid: uuid_pkg.UUID) -> str:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN], is_unit_available=True)

        unit = self.unit_repository.get(Unit(uuid=uuid))

        self.access_service.access_only_creator_and_target_unit(unit)

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        target_version = self.get_unit_target_version(repo, unit)

        env_dict = self.get_env(unit.uuid)
        self.git_repo_repository.is_valid_env_file(repo, target_version, env_dict)

        gen_uuid = uuid_pkg.uuid4()
        tmp_git_repo_path = self.git_repo_repository.generate_tmp_git_repo(repo, target_version, gen_uuid)

        env_dict['COMMIT_VERSION'] = target_version

        with open(f'{tmp_git_repo_path}/env.json', 'w') as f:
            f.write(json.dumps(env_dict, indent=4))

        new_schema_dict = self.generate_current_schema(unit, repo, target_version)

        with open(f'{tmp_git_repo_path}/schema.json', 'w') as f:
            f.write(json.dumps(new_schema_dict, indent=4))

        return tmp_git_repo_path

    def get_unit_firmware_zip(self, uuid: uuid_pkg.UUID) -> str:
        firmware_path = self.get_unit_firmware(uuid)
        firmware_zip_path = f"tmp/{uuid}"

        shutil.make_archive(firmware_zip_path, 'zip', firmware_path)
        shutil.rmtree(firmware_path, ignore_errors=True)

        return f'{firmware_zip_path}.zip'

    def get_unit_firmware_tar(self, uuid: uuid_pkg.UUID) -> str:
        firmware_path = self.get_unit_firmware(uuid)
        firmware_tar_path = f"tmp/{uuid}"

        shutil.make_archive(firmware_tar_path, 'tar', firmware_path)
        shutil.rmtree(firmware_path, ignore_errors=True)

        return f'{firmware_tar_path}.tar'

    def get_unit_firmware_tgz(self, uuid: uuid_pkg.UUID, wbits: int, level: int) -> str:
        self.is_valid_wbits(wbits)
        self.is_valid_level(level)

        firmware_path = self.get_unit_firmware(uuid)
        firmware_tar_path = f"tmp/{uuid}"

        shutil.make_archive(firmware_tar_path, 'tar', firmware_path)
        shutil.rmtree(firmware_path, ignore_errors=True)

        with open(firmware_tar_path + '.tar', 'rb') as tar_file:
            producer = zlib.compressobj(wbits=wbits, level=level)

            tar_data = producer.compress(tar_file.read()) + producer.flush()

            with open(f'{firmware_tar_path}.tgz', 'wb') as tgz:
                tgz.write(tar_data)

        os.remove(firmware_tar_path + '.tar')

        return f'{firmware_tar_path}.tgz'

    def get_mqtt_auth(self, topic: str) -> None:
        self.access_service.access_check([], is_unit_available=True)

        if isinstance(self.access_service.current_agent, Unit):

            struct_topic = get_topic_split(topic)

            len_struct = len(struct_topic)
            if len_struct == 5:
                backend_domain, destination, unit_uuid, topic_name, *_ = struct_topic
                unit_uuid = is_valid_uuid(unit_uuid)

                if destination in [DestinationTopicType.INPUT_BASE_TOPIC, DestinationTopicType.OUTPUT_BASE_TOPIC]:
                    if self.access_service.current_agent.uuid != unit_uuid:
                        raise HTTPException(
                            status_code=http_status.HTTP_403_FORBIDDEN, detail=f"Available only for a docked Unit"
                        )
                else:
                    raise HTTPException(
                        status_code=http_status.HTTP_403_FORBIDDEN, detail=f"Topic destination is invalid"
                    )

            elif len_struct in [2, 3]:
                backend_domain, unit_node_uuid, *_ = struct_topic
                unit_node_uuid = is_valid_uuid(unit_node_uuid)

                unit_node = self.unit_node_repository.get(UnitNode(uuid=unit_node_uuid))
                is_valid_object(unit_node)

                self.access_service.visibility_check(unit_node)
            else:
                raise HTTPException(
                    status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Topic struct is invalid"
                )
        else:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Not Unit - unavailable topic communication",
            )

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit)

        self.access_service.access_creator_check(unit)

        return self.unit_repository.delete(unit)

    def list(
        self, filters: Union[UnitFilter, UnitFilterInput], is_include_output_unit_nodes: bool = False
    ) -> tuple[int, list[tuple[Unit, list[dict]]]]:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN])
        restriction = self.access_service.access_restriction(resource_type=PermissionEntities.UNIT)

        filters.visibility_level = self.access_service.get_available_visibility_levels(
            filters.visibility_level, restriction
        )
        return self.unit_repository.list(
            filters, restriction=restriction, is_include_output_unit_nodes=is_include_output_unit_nodes
        )

    def get_unit_target_version(self, repo: Repo, unit: Unit):
        """
        Get target version - only repo and unit context, without current in physical Unit
        """
        return (
            self.git_repo_repository.get_target_version(repo)
            if unit.is_auto_update_from_repo_unit
            else unit.repo_commit
        )

    def generate_current_schema(self, unit: Unit, repo: Repo, target_version: str) -> dict:

        nodes_with_edges = self.unit_node_repository.get_nodes_with_edges(unit.uuid)

        output_dict = {}
        input_dict = {}
        for node_uuid, topic_name, topic_type, edges in nodes_with_edges:

            edge_topic_list = []
            if edges is not None:
                for output_node_uuid, output_topic_name in edges:
                    edge_topic_list.append(get_topic_name(output_node_uuid, output_topic_name))

            topics = [get_topic_name(node_uuid, topic_name)] + edge_topic_list

            if topic_type == UnitNodeTypeEnum.INPUT:
                input_dict[topic_name] = topics
            else:
                output_dict[topic_name] = topics

        schema_dict = self.git_repo_repository.get_schema_dict(repo, target_version)

        new_schema_dict = {}
        for destination, topics in schema_dict.items():

            new_schema_dict[destination] = {}

            for topic in topics:
                if destination in [DestinationTopicType.INPUT_BASE_TOPIC, DestinationTopicType.OUTPUT_BASE_TOPIC]:
                    new_schema_dict[destination][topic] = [
                        f'{settings.backend_domain}/{destination}/{unit.uuid}/{topic}'
                    ]
                elif destination == DestinationTopicType.INPUT_TOPIC:
                    new_schema_dict[destination][topic] = input_dict[topic]
                elif destination == DestinationTopicType.OUTPUT_TOPIC:
                    new_schema_dict[destination][topic] = output_dict[topic]

        return new_schema_dict

    def generate_token(self, uuid: uuid_pkg.UUID) -> str:
        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit)

        return self.access_service.generate_unit_token(unit)

    def gen_env_dict(self, uuid: uuid_pkg.UUID) -> dict:
        return {
            'PEPEUNIT_URL': settings.backend_domain,
            'HTTP_TYPE': settings.http_type,
            'MQTT_URL': settings.mqtt_host,
            'PEPEUNIT_TOKEN': self.generate_token(uuid),
            'SYNC_ENCRYPT_KEY': base64.b64encode(os.urandom(16)).decode('utf-8'),
            'SECRET_KEY': base64.b64encode(os.urandom(16)).decode('utf-8'),
            'PING_INTERVAL': 30,
            'STATE_SEND_INTERVAL': settings.state_send_interval,
        }

    def is_valid_no_auto_updated_unit(self, repo: Repo, data: Union[Unit, UnitCreate]):
        if not data.is_auto_update_from_repo_unit and (not data.repo_branch or not data.repo_commit):
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid hand updated unit")

        # check commit and branch for not auto updated unit
        if not data.is_auto_update_from_repo_unit:
            self.git_repo_repository.is_valid_branch(repo, data.repo_branch)
            self.git_repo_repository.is_valid_commit(repo, data.repo_branch, data.repo_commit)

    @staticmethod
    def mapper_unit_to_unit_read(unit: tuple[Unit, List[dict]]) -> UnitRead:
        return UnitRead(**unit[0].dict(), unit_nodes=[UnitNodeRead(**item) for item in unit[1]])

    @staticmethod
    def mapper_unit_to_unit_type(unit: tuple[Unit, List[dict]]) -> UnitType:
        return UnitType(**unit[0].dict(), unit_nodes=[UnitNodeType(**UnitNodeRead(**item).dict()) for item in unit[1]])

    @staticmethod
    def is_valid_cipher_env(unit: Unit, env_dict: dict):
        current_env_dict = json.loads(aes_decode(unit.cipher_env_dict))
        if env_dict.keys() - current_env_dict.keys() != set():
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"Dict in env.json is bad")

    @staticmethod
    def is_valid_wbits(wbits: int):
        available_values_list = list(itertools.chain(range(-15, -8), range(9, 16), range(25, 32)))
        if wbits not in available_values_list:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"Wbits is not valid")

    @staticmethod
    def is_valid_level(level: int):
        available_values_list = list(range(-1, 10))
        if level not in available_values_list:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"Level is not valid")
