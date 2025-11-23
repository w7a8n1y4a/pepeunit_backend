from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.clickhouse import get_hand_clickhouse_client
from app.configs.db import get_hand_session
from app.configs.rest import get_bot_grafana_service
from app.dto.enum import CommandNames, EntityNames
from app.schemas.bot.base_bot_router import (
    BaseBotFilters,
    BaseBotRouter,
    DashboardStates,
)
from app.schemas.pydantic.grafana import DashboardFilter


class DashboardBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.DASHBOARD.value
        super().__init__(entity_name=entity_name, states_group=DashboardStates)
        self.router.message(Command(CommandNames.DASHBOARD))(
            self.dashboard_resolver
        )

    async def dashboard_resolver(
        self, message: types.Message, state: FSMContext
    ):
        await state.set_state(None)
        filters = BaseBotFilters()
        await state.update_data(current_filters=filters)
        await self.show_entities(message, filters)

    async def show_entities(
        self,
        message: types.Message | types.CallbackQuery,
        filters: BaseBotFilters,
    ):
        chat_id = (
            message.chat.id
            if isinstance(message, types.Message)
            else message.from_user.id
        )

        entities, total_pages = await self.get_entities_page(
            filters, str(chat_id)
        )
        keyboard = self.build_entities_keyboard(entities, filters, total_pages)

        text = "*Dashboards*"
        if filters.search_string:
            text += f" - `{filters.search_string}`"

        await self.telegram_response(message, text, keyboard)

    async def get_entities_page(
        self, filters: BaseBotFilters, chat_id: str
    ) -> tuple[list, int]:
        with get_hand_session() as db, get_hand_clickhouse_client() as cc:
            grafana_service = get_bot_grafana_service(db, cc, str(chat_id))

            count, dashboards = grafana_service.list_dashboards(
                DashboardFilter(
                    offset=(filters.page - 1)
                    * settings.pu_telegram_items_per_page,
                    limit=settings.pu_telegram_items_per_page,
                    search_string=filters.search_string,
                )
            )

            total_pages = (
                count + settings.pu_telegram_items_per_page - 1
            ) // settings.pu_telegram_items_per_page

        return dashboards, total_pages

    def build_entities_keyboard(
        self, entities: list, filters: BaseBotFilters, total_pages: int
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        filter_buttons = [
            InlineKeyboardButton(
                text="🔍 Search", callback_data=f"{self.entity_name}_search"
            ),
        ]
        builder.row(*filter_buttons)

        if entities:
            for dashboard in entities:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{self.registry_name_limit(dashboard.name, 2)}",
                        url=f"{settings.pu_link}/dashboard/{dashboard.uuid}",
                    )
                )
        else:
            builder.row(
                InlineKeyboardButton(text="No Data", callback_data="noop")
            )

        if total_pages > 1:
            pagination_row = []
            if filters.page > 1:
                pagination_row.append(
                    InlineKeyboardButton(
                        text="⬅️", callback_data=f"{self.entity_name}_prev_page"
                    )
                )

            pagination_row.append(
                InlineKeyboardButton(
                    text=f"{filters.page}/{total_pages}", callback_data="noop"
                )
            )

            if filters.page < total_pages:
                pagination_row.append(
                    InlineKeyboardButton(
                        text="➡️", callback_data=f"{self.entity_name}_next_page"
                    )
                )
            builder.row(*pagination_row)

        return builder.as_markup()

    async def handle_entity_click(
        self, callback: types.CallbackQuery, state: FSMContext
    ) -> None:
        pass

    async def handle_entity_decrees(
        self, callback: types.CallbackQuery
    ) -> None:
        pass
