import json
import logging
import math
from typing import Union
from uuid import UUID

from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.db import get_session
from app.configs.gql import get_repo_service, get_unit_node_service, get_unit_service
from app.configs.sub_entities import InfoSubEntity
from app.dto.enum import (
    BackendTopicCommand,
    CommandNames,
    DecreesNames,
    EntityNames,
    GlobalPrefixTopic,
    ReservedInputBaseTopic,
    VisibilityLevel,
)
from app.schemas.bot.base_bot_router import BaseBotFilters, BaseBotRouter, UnitStates
from app.schemas.bot.utils import (
    byte_converter,
    calculate_flash_mem,
    format_millis,
    make_monospace_table_with_title,
    reformat_table,
)
from app.schemas.pydantic.unit import UnitFilter


class UnitBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.UNIT

        super().__init__(entity_name=entity_name, states_group=UnitStates)
        self.router.message(Command(CommandNames.UNIT))(self.unit_resolver)

    async def unit_resolver(self, message: types.Message, state: FSMContext):
        await state.set_state(None)
        filters = BaseBotFilters()
        await state.update_data(current_filters=filters)
        await self.show_entities(message, filters)

    async def show_entities(self, message: Union[types.Message, types.CallbackQuery], filters: BaseBotFilters):
        chat_id = message.chat.id if isinstance(message, types.Message) else message.from_user.id

        units, total_pages = await self.get_entities_page(filters, str(chat_id))

        if not units:
            text = "No units found"

            if isinstance(message, types.Message):
                await message.answer(text, parse_mode='Markdown')
            else:
                await message.message.edit_text(text, parse_mode='Markdown')

            return

        keyboard = self.build_entities_keyboard(units, filters, total_pages)

        text = "*Units*"
        if filters.search_string:
            text += f" - `{filters.search_string}`"

        if isinstance(message, types.Message):
            await message.answer(text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await message.message.edit_text(text, reply_markup=keyboard, parse_mode='Markdown')

    async def get_entities_page(self, filters: BaseBotFilters, chat_id: str) -> tuple[list, int]:
        db = next(get_session())
        try:
            unit_service = get_unit_service(InfoSubEntity({'db': db, 'jwt_token': chat_id, 'is_bot_auth': True}))

            count, units = unit_service.list(
                UnitFilter(
                    offset=(filters.page - 1) * settings.telegram_items_per_page,
                    limit=settings.telegram_items_per_page,
                    visibility_level=filters.visibility_levels or None,
                    creator_uuid=unit_service.access_service.current_agent.uuid if filters.is_only_my_entity else None,
                    search_string=filters.search_string,
                )
            )

            total_pages = (count + settings.telegram_items_per_page - 1) // settings.telegram_items_per_page

        except Exception as e:
            logging.error(f"Error getting units: {e}")
            units, total_pages = [], 0
        finally:
            db.close()

        return units, total_pages

    def build_entities_keyboard(
        self, entities: list, filters: BaseBotFilters, total_pages: int
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

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

        for unit, nodes in entities:
            builder.row(
                InlineKeyboardButton(
                    text=f"{unit.name} - {unit.visibility_level}",
                    callback_data=f"{self.entity_name}_uuid_{unit.uuid}_{filters.page}",
                )
            )

        if total_pages > 1:
            pagination_row = []
            if filters.page > 1:
                pagination_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"{self.entity_name}_prev_page"))

            pagination_row.append(InlineKeyboardButton(text=f"{filters.page}/{total_pages}", callback_data="noop"))

            if filters.page < total_pages:
                pagination_row.append(InlineKeyboardButton(text="➡️", callback_data=f"{self.entity_name}_next_page"))
            builder.row(*pagination_row)

        return builder.as_markup()

    async def handle_entity_click(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        filters: BaseBotFilters = data.get("current_filters", BaseBotFilters())

        try:
            unit_uuid = UUID(callback.data.split('_')[-2])
            current_page = int(callback.data.split('_')[-1])
        except Exception as e:
            await callback.answer(parse_mode='Markdown')
            return

        filters.page = current_page
        new_filters = BaseBotFilters(previous_filters=filters)
        await state.update_data(current_filters=new_filters)

        db = next(get_session())
        try:
            unit_service = get_unit_service(
                InfoSubEntity({'db': db, 'jwt_token': str(callback.from_user.id), 'is_bot_auth': True})
            )
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

        finally:
            db.close()

        text = f'Unit - *{unit.name}* - {unit.visibility_level}'

        if target_version:

            current_version = unit.current_commit_version[:8] if unit.current_commit_version else None
            target_version = target_version.commit[:8] if target_version.commit else None

            table = [['Update', 'Current', 'Target'], [unit.firmware_update_status, current_version, target_version]]

            text += f'\n```text\n'
            text += make_monospace_table_with_title(table, 'Version')
            text += '```'

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

                while len(table) % 4 != 0:
                    table.append([None, None])

            if len(unit.unit_state.statvfs) == 10:
                total, free, used = calculate_flash_mem(unit.unit_state.statvfs)

                table.extend(
                    [
                        ['Total', byte_converter(round(total, 0))],
                        ['Free', byte_converter(round(free, 0))],
                        ['Used', byte_converter(round(used, 0))],
                        [None, None],
                    ]
                )

            new_table = reformat_table(table)

            text += f'\n```text\n'
            text += make_monospace_table_with_title(new_table, 'Unit State')
            text += '```'

        keyboard = []

        if is_creator:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text='Get Env',
                        callback_data=f'{self.entity_name}_decrees_{DecreesNames.GET_ENV}_{unit.uuid}',
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
                            callback_data=f'{self.entity_name}_decrees_{command_mqtt_dict[command]}_{unit.uuid}',
                        )
                        for command in list(commands)
                    ]
                )

        keyboard.append(
            [
                InlineKeyboardButton(text='← Back', callback_data=f'{self.entity_name}_back'),
                InlineKeyboardButton(text='Browser', url=f'{settings.backend_link}/unit/{unit.uuid}'),
            ],
        )

        await callback.message.edit_text(
            text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode='Markdown'
        )
        await callback.answer(parse_mode='Markdown')

    async def handle_entity_decrees(self, callback: types.CallbackQuery) -> None:

        *_, decrees_type, unit_uuid = callback.data.split('_')
        unit_uuid = UUID(unit_uuid)

        db = next(get_session())
        try:
            unit_service = get_unit_service(
                InfoSubEntity({'db': db, 'jwt_token': str(callback.from_user.id), 'is_bot_auth': True})
            )

            unit_node_service = get_unit_node_service(
                InfoSubEntity({'db': db, 'jwt_token': str(callback.from_user.id), 'is_bot_auth': True})
            )

            text = ''
            match decrees_type:
                case DecreesNames.GET_ENV:
                    text += f'\n```json\n'
                    text += json.dumps(unit_service.get_env(unit_uuid), indent=4)
                    text += '```'
                case _ if decrees_type in (
                    BackendTopicCommand.UPDATE,
                    BackendTopicCommand.SCHEMA_UPDATE,
                    BackendTopicCommand.ENV_UPDATE,
                    BackendTopicCommand.LOG_SYNC,
                ):
                    unit_node_service.command_to_input_base_topic(unit_uuid, BackendTopicCommand(decrees_type))
                    text = f'Success send command {decrees_type}'

        except Exception as e:
            await callback.answer(parse_mode='Markdown')
            await callback.message.answer(e.message, parse_mode='Markdown')
            return
        finally:
            db.close()

        await callback.answer(parse_mode='Markdown')
        await callback.message.answer(text, parse_mode='Markdown')
