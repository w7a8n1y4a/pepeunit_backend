import json
import logging
from json import JSONDecodeError
from typing import Union
from uuid import UUID

from aiogram import F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.db import get_session
from app.configs.gql import get_unit_node_service, get_unit_service
from app.configs.sub_entities import InfoSubEntity
from app.dto.enum import EntityNames, LogLevel, UnitNodeTypeEnum
from app.schemas.bot.base_bot_router import BaseBotFilters, BaseBotRouter, UnitNodeStates
from app.schemas.bot.utils import make_monospace_table_with_title
from app.schemas.pydantic.unit import UnitLogFilter


class UnitLogBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.UNIT_LOG
        super().__init__(entity_name=entity_name, states_group=UnitNodeStates)
        self.router.callback_query(F.data.startswith(f"{self.entity_name}_unit_"))(self.handle_by_unit)

    async def handle_by_unit(self, callback: types.CallbackQuery, state: FSMContext):
        *_, unit_uuid = callback.data.split('_')

        await state.set_state(None)
        filters = BaseBotFilters(unit_uuid=unit_uuid)
        await state.update_data(current_filters=filters)
        await self.show_entities(callback, filters)

    async def show_entities(self, message: Union[types.Message, types.CallbackQuery], filters: BaseBotFilters):
        chat_id = message.chat.id if isinstance(message, types.Message) else message.from_user.id

        unit_logs, total_pages = await self.get_entities_page(filters, str(chat_id))

        if not unit_logs:
            text = "No unit logs found"

            if isinstance(message, types.Message):
                await message.answer(text, parse_mode='Markdown')
            else:
                await message.message.edit_text(text, parse_mode='Markdown')

            return

        keyboard = self.build_entities_keyboard(unit_logs, filters, total_pages)

        text = "*Unit Logs*"
        if filters.unit_uuid:
            db = next(get_session())
            unit = None
            try:
                unit_service = get_unit_service(
                    InfoSubEntity({'db': db, 'jwt_token': str(chat_id), 'is_bot_auth': True})
                )
                unit = unit_service.get(filters.unit_uuid)
            finally:
                text += f" - for unit `{unit.name}`"

        table = [['Time', 'Level', 'Text']]

        for unit_log in unit_logs[::-1]:
            table.append([unit_log.create_datetime.strftime("%Y-%m-%d%H:%M:%S"), unit_log.level.value, unit_log.text])

        text += f'\n```text\n'

        text += make_monospace_table_with_title(table, lengths=[10, 5, 25])

        text += '```'

        if isinstance(message, types.Message):
            await message.answer(text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await message.message.edit_text(text, reply_markup=keyboard, parse_mode='Markdown')

    async def get_entities_page(self, filters: BaseBotFilters, chat_id: str) -> tuple[list, int]:
        db = next(get_session())
        try:
            unit_service = get_unit_service(InfoSubEntity({'db': db, 'jwt_token': chat_id, 'is_bot_auth': True}))

            count, unit_logs = unit_service.log_list(
                UnitLogFilter(
                    offset=(filters.page - 1) * settings.telegram_items_per_page,
                    limit=settings.telegram_items_per_page,
                    level=filters.log_levels or None,
                    uuid=filters.unit_uuid,
                )
            )

            total_pages = (count + settings.telegram_items_per_page - 1) // settings.telegram_items_per_page

        except Exception as e:
            logging.error(f"Error getting unit_logs: {e}")
            unit_logs, total_pages = [], 0
        finally:
            db.close()

        return unit_logs, total_pages

    def build_entities_keyboard(
        self, entities: list, filters: BaseBotFilters, total_pages: int
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        filter_level_buttons = [
            InlineKeyboardButton(
                text=("🟢 " if item.value in filters.log_levels else "🔴️ ") + item.value,
                callback_data=f"{self.entity_name}_toggle_" + item.value,
            )
            for item in LogLevel
        ]
        builder.row(*filter_level_buttons)

        if total_pages > 1:
            pagination_row = []
            if filters.page > 1:
                pagination_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"{self.entity_name}_prev_page"))

            pagination_row.append(InlineKeyboardButton(text=f"{filters.page}/{total_pages}", callback_data="noop"))

            if filters.page < total_pages:
                pagination_row.append(InlineKeyboardButton(text="➡️", callback_data=f"{self.entity_name}_next_page"))
            builder.row(*pagination_row)

        builder.row(
            InlineKeyboardButton(
                text='← Back', callback_data=f'{EntityNames.UNIT}_uuid_{filters.unit_uuid}_{filters.page}'
            )
        )
        return builder.as_markup()

    async def handle_entity_click(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        await callback.answer(parse_mode='Markdown')

    async def handle_entity_decrees(self, callback: types.CallbackQuery) -> None:
        await callback.answer(parse_mode='Markdown')
