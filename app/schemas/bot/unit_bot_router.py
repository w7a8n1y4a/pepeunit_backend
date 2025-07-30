import json
import os
from typing import Union
from uuid import UUID

from aiogram import F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.clickhouse import get_hand_clickhouse_client
from app.configs.db import get_hand_session
from app.configs.rest import get_repo_service, get_unit_node_service, get_unit_service
from app.dto.enum import (
    BackendTopicCommand,
    CommandNames,
    DecreesNames,
    EntityNames,
    GlobalPrefixTopic,
    ReservedInputBaseTopic,
    UnitFirmwareUpdateStatus,
    VisibilityLevel,
)
from app.schemas.bot.base_bot_router import BaseBotFilters, BaseBotRouter, UnitStates
from app.schemas.bot.utils import (
    byte_converter,
    calculate_flash_mem,
    format_millis,
    make_monospace_table_with_title,
)
from app.schemas.pydantic.unit import UnitFilter


class UnitBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.UNIT

        super().__init__(entity_name=entity_name, states_group=UnitStates)
        self.router.message(Command(CommandNames.UNIT))(self.unit_resolver)
        self.router.callback_query(F.data.startswith(f"{self.entity_name}_repo_"))(self.handle_by_repo)

    async def unit_resolver(self, message: types.Message, state: FSMContext):
        await state.set_state(None)
        filters = BaseBotFilters()
        await state.update_data(current_filters=filters)
        await self.show_entities(message, filters)

    async def handle_by_repo(self, callback: types.CallbackQuery, state: FSMContext):
        *_, repo_uuid = callback.data.split('_')

        await state.set_state(None)
        filters = BaseBotFilters(repo_uuid=repo_uuid)
        await state.update_data(current_filters=filters)
        await self.show_entities(callback, filters)

    async def show_entities(self, message: Union[types.Message, types.CallbackQuery], filters: BaseBotFilters):
        chat_id = message.chat.id if isinstance(message, types.Message) else message.from_user.id

        entities, total_pages = await self.get_entities_page(filters, str(chat_id))
        keyboard = self.build_entities_keyboard(entities, filters, total_pages)

        text = "*Units*"
        if filters.search_string:
            text += f" - `{filters.search_string}`"

        if filters.repo_uuid:
            with get_hand_session() as db:
                with get_hand_clickhouse_client() as cc:
                    repo_service = get_repo_service(db, cc, str(chat_id), True)
                    repo = repo_service.get(filters.repo_uuid)

            text += f" - for repo `{repo.name}`"

        await self.telegram_response(message, text, keyboard)

    async def get_entities_page(self, filters: BaseBotFilters, chat_id: str) -> tuple[list, int]:
        with get_hand_session() as db:
            with get_hand_clickhouse_client() as cc:
                unit_service = get_unit_service(db, cc, chat_id, True)

                count, units = unit_service.list(
                    UnitFilter(
                        offset=(filters.page - 1) * settings.telegram_items_per_page,
                        limit=settings.telegram_items_per_page,
                        visibility_level=filters.visibility_levels or [],
                        creator_uuid=(
                            unit_service.access_service.current_agent.uuid if filters.is_only_my_entity else None
                        ),
                        search_string=filters.search_string,
                        repo_uuid=filters.repo_uuid,
                    )
                )

                total_pages = (count + settings.telegram_items_per_page - 1) // settings.telegram_items_per_page

        return units, total_pages

    def build_entities_keyboard(
        self, entities: list, filters: BaseBotFilters, total_pages: int
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        if not filters.repo_uuid:
            filter_buttons = [
                InlineKeyboardButton(text="🔍 Search", callback_data=f"{self.entity_name}_search"),
                InlineKeyboardButton(
                    text=("🟢 " if filters.is_only_my_entity else "🔴 ") + 'My units',
                    callback_data=f"{self.entity_name}_toggle_mine",
                ),
            ]
            builder.row(*filter_buttons)

        filter_visibility_buttons = [
            InlineKeyboardButton(
                text=("🟢 " if item.value in filters.visibility_levels else "🔴️ ") + item.value,
                callback_data=f"{self.entity_name}_toggle_" + item.value,
            )
            for item in VisibilityLevel
        ]
        builder.row(*filter_visibility_buttons)

        if entities:
            for unit, nodes in entities:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{self.header_name_limit(unit.name)} - {unit.visibility_level}",
                        callback_data=f"{self.entity_name}_uuid_{unit.uuid}_{filters.page}",
                    )
                )
        else:
            builder.row(InlineKeyboardButton(text="No Data", callback_data="noop"))

        if total_pages > 1:
            pagination_row = []
            if filters.page > 1:
                pagination_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"{self.entity_name}_prev_page"))

            pagination_row.append(InlineKeyboardButton(text=f"{filters.page}/{total_pages}", callback_data="noop"))

            if filters.page < total_pages:
                pagination_row.append(InlineKeyboardButton(text="➡️", callback_data=f"{self.entity_name}_next_page"))
            builder.row(*pagination_row)

        if filters.repo_uuid:
            builder.row(
                InlineKeyboardButton(
                    text='← Back', callback_data=f'{EntityNames.REPO}_uuid_{filters.repo_uuid}_{filters.page}'
                )
            )

        return builder.as_markup()

    async def handle_entity_click(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        filters: BaseBotFilters = (
            BaseBotFilters(**data.get("current_filters")) if data.get("current_filters") else BaseBotFilters()
        )

        unit_uuid = UUID(callback.data.split('_')[-2])
        current_page = int(callback.data.split('_')[-1])

        if not filters.previous_filters:
            filters.page = current_page
            new_filters = BaseBotFilters(previous_filters=filters)
            await state.update_data(current_filters=new_filters)

        with get_hand_session() as db:
            with get_hand_clickhouse_client() as cc:
                unit_service = get_unit_service(db, cc, str(callback.from_user.id), True)
                unit = unit_service.mapper_unit_to_unit_type((unit_service.get(unit_uuid), []))

                try:
                    target_version = unit_service.get_target_version(unit_uuid)
                except Exception:
                    target_version = None

                try:
                    current_schema = unit_service.get_current_schema(unit_uuid)
                except Exception:
                    current_schema = None

                is_creator = unit_service.access_service.current_agent.uuid == unit.creator_uuid

        text = f'*Unit* - `{self.header_name_limit(unit.name)}` - *{unit.visibility_level}*'

        if target_version or unit.unit_state:
            text += f'\n```text\n'

        if target_version:

            current_version = self.git_hash_limit(unit.current_commit_version) if unit.current_commit_version else None
            target_version = self.git_hash_limit(target_version.commit) if target_version.commit else None

            if not unit.firmware_update_status and current_version == target_version:
                status = UnitFirmwareUpdateStatus.SUCCESS
            elif not unit.firmware_update_status and current_version != target_version:
                status = 'Need'
            elif not target_version and not current_version:
                status = 'No Data'
            else:
                status = unit.firmware_update_status

            table = [['Update', 'Current', 'Target'], [status, current_version, target_version]]

            text += make_monospace_table_with_title(table, 'Version')

            if unit.firmware_update_status == UnitFirmwareUpdateStatus.REQUEST_SENT:
                table = [[unit.last_firmware_update_datetime.strftime("%Y-%m-%d %H:%M:%S")]]

                text += '\n'
                text += make_monospace_table_with_title(table, 'Request Time')

            if unit.firmware_update_status == UnitFirmwareUpdateStatus.ERROR and unit.firmware_update_error:
                text += '\n'
                text += make_monospace_table_with_title([[unit.firmware_update_error]], 'Update Error')

        if unit.unit_state:
            table = []
            if len(unit.unit_state.ifconfig) == 4:

                table.extend(
                    [
                        ['IP', unit.unit_state.ifconfig[0]],
                        ['Sub', unit.unit_state.ifconfig[1]],
                        ['Gate', unit.unit_state.ifconfig[2]],
                        ['DNS', unit.unit_state.ifconfig[3]],
                    ]
                )

            if unit.unit_state.mem_alloc or unit.unit_state.mem_free or unit.unit_state.freq or unit.unit_state.millis:
                if unit.unit_state.freq:
                    table.append(['Freq', round(unit.unit_state.freq, 1)])

                if unit.unit_state.millis:
                    table.append(['Up', format_millis(unit.unit_state.millis)])

                if unit.unit_state.mem_alloc:
                    table.append(['Alloc RAM', byte_converter(unit.unit_state.mem_alloc)])

                if unit.unit_state.mem_free:
                    table.append(['Free RAM', byte_converter(unit.unit_state.mem_free)])

            if len(unit.unit_state.statvfs) == 10:
                total, free, used = calculate_flash_mem(unit.unit_state.statvfs)

                table.extend(
                    [
                        ['Total', byte_converter(round(total, 0))],
                        ['Free', byte_converter(round(free, 0))],
                        ['Used', byte_converter(round(used, 0))],
                    ]
                )

            text += '\n'
            text += make_monospace_table_with_title(table, 'Unit State')

        if target_version or unit.unit_state:

            text += '```'

        keyboard = []

        if is_creator:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text='💰 Get Env',
                        callback_data=f'{self.entity_name}_decres_{DecreesNames.GET_ENV}_{unit.uuid}',
                    ),
                ]
            )

            if current_schema:
                commands = current_schema['input_base_topic'].keys()

                command_mqtt_dict = {
                    f'{ReservedInputBaseTopic.UPDATE}{GlobalPrefixTopic.BACKEND_SUB_PREFIX}': BackendTopicCommand.UPDATE,
                    f'{ReservedInputBaseTopic.SCHEMA_UPDATE}{GlobalPrefixTopic.BACKEND_SUB_PREFIX}': BackendTopicCommand.SCHEMA_UPDATE,
                    f'{ReservedInputBaseTopic.ENV_UPDATE}{GlobalPrefixTopic.BACKEND_SUB_PREFIX}': BackendTopicCommand.ENV_UPDATE,
                    f'{ReservedInputBaseTopic.LOG_SYNC}{GlobalPrefixTopic.BACKEND_SUB_PREFIX}': BackendTopicCommand.LOG_SYNC,
                }

                keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=command_mqtt_dict[command],
                            callback_data=f'{self.entity_name}_decres_{command_mqtt_dict[command]}_{unit.uuid}',
                        )
                        for command in list(commands)
                    ]
                )
            if target_version:
                commands = [DecreesNames.TGZ, DecreesNames.TAR, DecreesNames.ZIP]

                keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=f'💾 {command}',
                            callback_data=f'{self.entity_name}_decres_{command}_{unit.uuid}',
                        )
                        for command in commands
                    ]
                )

        buttons = [
            InlineKeyboardButton(text='🎯 Unit Nodes', callback_data=f'{EntityNames.UNIT_NODE}_unit_{unit.uuid}'),
        ]

        if is_creator:
            buttons.append(
                InlineKeyboardButton(text='📝 Unit Logs', callback_data=f'{EntityNames.UNIT_LOG}_unit_{unit.uuid}')
            )

        keyboard.append(buttons)

        keyboard.append(
            [
                InlineKeyboardButton(text='← Back', callback_data=f'{self.entity_name}_back'),
                InlineKeyboardButton(
                    text='↻ Refresh', callback_data=f'{self.entity_name}_uuid_{unit.uuid}_{filters.page}'
                ),
                InlineKeyboardButton(text='Browser', url=f'{settings.backend_link}/unit/{unit.uuid}'),
            ],
        )

        await callback.answer(parse_mode='Markdown')
        try:
            await self.telegram_response(callback, text, InlineKeyboardMarkup(inline_keyboard=keyboard))
        except TelegramBadRequest:
            pass

    async def handle_entity_decrees(self, callback: types.CallbackQuery) -> None:

        *_, decrees_type, unit_uuid = callback.data.split('_')
        unit_uuid = UUID(unit_uuid)
        with get_hand_session() as db:
            with get_hand_clickhouse_client() as cc:
                unit_service = get_unit_service(db, cc, str(callback.from_user.id), True)
                unit_node_service = get_unit_node_service(db, cc, str(callback.from_user.id), True)

                text = ''
                match decrees_type:
                    case DecreesNames.GET_ENV:
                        text += f'\n```json\n'
                        text += json.dumps(unit_service.get_env(unit_uuid), indent=4)
                        text += '```'

                    case _ if decrees_type in (
                        DecreesNames.TGZ,
                        DecreesNames.TAR,
                        DecreesNames.ZIP,
                    ):
                        decrees_to_func = {
                            DecreesNames.TGZ: unit_service.get_unit_firmware_tgz,
                            DecreesNames.TAR: unit_service.get_unit_firmware_tar,
                            DecreesNames.ZIP: unit_service.get_unit_firmware_zip,
                        }

                        unit = unit_service.get(unit_uuid)
                        file_name = decrees_to_func[DecreesNames(decrees_type)](unit_uuid)
                        await callback.message.answer_document(
                            FSInputFile(file_name, filename=f'{unit.name}.{decrees_type.lower()}')
                        )

                        os.remove(file_name)
                        await callback.answer(parse_mode='Markdown')

                        return

                    case _ if decrees_type in (
                        BackendTopicCommand.UPDATE,
                        BackendTopicCommand.SCHEMA_UPDATE,
                        BackendTopicCommand.ENV_UPDATE,
                        BackendTopicCommand.LOG_SYNC,
                    ):
                        unit_node_service.command_to_input_base_topic(unit_uuid, BackendTopicCommand(decrees_type))
                        text = f'Success send command {decrees_type}'

        await callback.answer(parse_mode='Markdown')
        await self.telegram_response(callback, text, is_editable=False)
