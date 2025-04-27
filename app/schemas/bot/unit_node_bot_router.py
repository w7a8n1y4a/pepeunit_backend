import json
from json import JSONDecodeError
from typing import Union
from uuid import UUID

from aiogram import F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.db import get_hand_session
from app.configs.gql import get_unit_node_service, get_unit_service
from app.configs.sub_entities import InfoSubEntity
from app.dto.enum import EntityNames, UnitNodeTypeEnum, VisibilityLevel
from app.schemas.bot.base_bot_router import BaseBotFilters, BaseBotRouter, UnitNodeStates
from app.schemas.bot.utils import make_monospace_table_with_title
from app.schemas.pydantic.unit_node import UnitNodeFilter


class UnitNodeBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.UNIT_NODE
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

        entities, total_pages = await self.get_entities_page(filters, str(chat_id))
        keyboard = self.build_entities_keyboard(entities, filters, total_pages)

        text = "*UnitNodes*"
        if filters.unit_uuid:
            with get_hand_session() as db:
                unit_service = get_unit_service(
                    InfoSubEntity({'db': db, 'jwt_token': str(chat_id), 'is_bot_auth': True})
                )
                unit = unit_service.get(filters.unit_uuid)

            text += f" - for unit `{self.header_name_limit(unit.name)}`"

        if filters.search_string:
            text += f" - `{filters.search_string}`"

        await self.telegram_response(message, text, keyboard)

    async def get_entities_page(self, filters: BaseBotFilters, chat_id: str) -> tuple[list, int]:
        with get_hand_session() as db:
            unit_node_service = get_unit_node_service(
                InfoSubEntity({'db': db, 'jwt_token': chat_id, 'is_bot_auth': True})
            )

            count, unit_nodes = unit_node_service.list(
                UnitNodeFilter(
                    offset=(filters.page - 1) * settings.telegram_items_per_page,
                    limit=settings.telegram_items_per_page,
                    visibility_level=filters.visibility_levels or [],
                    type=filters.unit_types or [],
                    search_string=filters.search_string,
                    unit_uuid=filters.unit_uuid,
                )
            )

            total_pages = (count + settings.telegram_items_per_page - 1) // settings.telegram_items_per_page

        return unit_nodes, total_pages

    def build_entities_keyboard(
        self, entities: list, filters: BaseBotFilters, total_pages: int
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        filter_buttons = [InlineKeyboardButton(text="🔍 Search", callback_data=f"{self.entity_name}_search")]
        builder.row(*filter_buttons)

        filter_unit_types_buttons = [
            InlineKeyboardButton(
                text=("🟢 " if item.value in filters.unit_types else "🔴️ ") + item.value,
                callback_data=f"{self.entity_name}_toggle_" + item.value,
            )
            for item in UnitNodeTypeEnum
        ]
        builder.row(*filter_unit_types_buttons)

        filter_visibility_buttons = [
            InlineKeyboardButton(
                text=("🟢 " if item.value in filters.visibility_levels else "🔴️ ") + item.value,
                callback_data=f"{self.entity_name}_toggle_" + item.value,
            )
            for item in VisibilityLevel
        ]
        builder.row(*filter_visibility_buttons)
        if entities:
            for unit_node in entities:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{self.header_name_limit(unit_node.topic_name)} - {unit_node.type} - {unit_node.visibility_level}",
                        callback_data=f"{self.entity_name}_uuid_{unit_node.uuid}_{filters.page}",
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

        builder.row(
            InlineKeyboardButton(
                text='← Back', callback_data=f'{EntityNames.UNIT}_uuid_{filters.unit_uuid}_{filters.page}'
            )
        )

        return builder.as_markup()

    async def handle_entity_click(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        filters: BaseBotFilters = (
            BaseBotFilters(**data.get("current_filters")) if data.get("current_filters") else BaseBotFilters()
        )

        unit_node_uuid = UUID(callback.data.split('_')[-2])
        current_page = int(callback.data.split('_')[-1])

        if not filters.previous_filters:
            filters.page = current_page
            new_filters = BaseBotFilters(previous_filters=filters)
            await state.update_data(current_filters=new_filters)

        with get_hand_session() as db:
            unit_node_service = get_unit_node_service(
                InfoSubEntity({'db': db, 'jwt_token': str(callback.from_user.id), 'is_bot_auth': True})
            )
            unit_node = unit_node_service.get(unit_node_uuid)

        text = f'*UnitNode* - `{self.header_name_limit(unit_node.topic_name)}`'

        text += f'\n```text\n'

        table = [
            ['Type', unit_node.type],
            ['Visibility', unit_node.visibility_level],
            ['Last Update', unit_node.last_update_datetime.strftime("%Y-%m-%d %H:%M:%S")],
        ]

        if unit_node.type == UnitNodeTypeEnum.INPUT:
            table.append(['Rewritable?', unit_node.is_rewritable_input])

        text += make_monospace_table_with_title(table, 'Base Info')

        if unit_node.state:
            text += '\nState:\n\n'

            try:
                unit_state = json.loads(unit_node.state)
                text += json.dumps(unit_state, indent=4)

            except JSONDecodeError:
                text += unit_node.state

        text += '```'

        keyboard = [
            [
                InlineKeyboardButton(text='← Back', callback_data=f'{self.entity_name}_back'),
                InlineKeyboardButton(
                    text='↻ Refresh', callback_data=f'{self.entity_name}_uuid_{unit_node.uuid}_{filters.page}'
                ),
                InlineKeyboardButton(text='Browser', url=f'{settings.backend_link}/unit-node/{unit_node.uuid}'),
            ],
        ]

        await callback.answer(parse_mode='Markdown')

        try:
            await self.telegram_response(callback, text, InlineKeyboardMarkup(inline_keyboard=keyboard))
        except TelegramBadRequest:
            pass

    async def handle_entity_decrees(self, callback: types.CallbackQuery) -> None:
        await callback.answer(parse_mode='Markdown')
