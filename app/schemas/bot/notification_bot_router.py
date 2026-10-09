import contextlib
from uuid import UUID

from aiogram import F, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.db import get_hand_session
from app.configs.rest import get_bot_notification_service
from app.domain.notification_model import Notification
from app.dto.enum import CommandNames, EntityNames, NotificationType
from app.schemas.bot.base_bot_router import BaseBotFilters, BaseBotRouter
from app.schemas.pydantic.notification import NotificationFilter
from app.services.notification_delivery import TelegramAlertQueue


class NotificationStates(StatesGroup):
    pass


class NotificationBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.NOTIFICATION.value
        super().__init__(
            entity_name=entity_name, states_group=NotificationStates
        )
        self.router.message(Command(CommandNames.ALERTS.value))(
            self.alerts_resolver
        )
        self.router.callback_query(
            F.data.startswith(f"{self.entity_name}_log_")
        )(self.handle_log_click)

    async def alerts_resolver(self, message: types.Message, state: FSMContext):
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
        await self.telegram_response(message, "*Alerts*", keyboard)

    async def get_entities_page(
        self, filters: BaseBotFilters, chat_id: str
    ) -> tuple[list, int]:
        with get_hand_session() as db:
            notification_service = get_bot_notification_service(db, chat_id)
            count, notifications = notification_service.list(
                NotificationFilter(
                    offset=(filters.page - 1)
                    * settings.pu_telegram_items_per_page,
                    limit=settings.pu_telegram_items_per_page,
                    type=filters.notification_types,
                )
            )
            total_pages = (
                count + settings.pu_telegram_items_per_page - 1
            ) // settings.pu_telegram_items_per_page
        return notifications, total_pages

    def build_entities_keyboard(
        self, entities: list, filters: BaseBotFilters, total_pages: int
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        type_buttons = [
            InlineKeyboardButton(
                text=(
                    "🟢 "
                    if item.value in filters.notification_types
                    else "🔴️ "
                )
                + item.value,
                callback_data=f"{self.entity_name}_toggle_" + item.value,
            )
            for item in NotificationType
        ]
        for offset in range(0, len(type_buttons), 3):
            builder.row(*type_buttons[offset : offset + 3])

        if entities:
            for notification in entities:
                builder.row(
                    InlineKeyboardButton(
                        text=self._button_text(notification),
                        callback_data=f"{self.entity_name}_uuid_{notification.uuid}_{filters.page}",
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
                        text="⬅️",
                        callback_data=f"{self.entity_name}_prev_page",
                    )
                )
            pagination_row.append(
                InlineKeyboardButton(
                    text=f"{filters.page}/{total_pages}",
                    callback_data="noop",
                )
            )
            if filters.page < total_pages:
                pagination_row.append(
                    InlineKeyboardButton(
                        text="➡️",
                        callback_data=f"{self.entity_name}_next_page",
                    )
                )
            builder.row(*pagination_row)

        return builder.as_markup()

    async def handle_entity_click(
        self, callback: types.CallbackQuery, state: FSMContext
    ) -> None:
        data = await state.get_data()
        filters: BaseBotFilters = (
            BaseBotFilters(**data.get("current_filters"))
            if data.get("current_filters")
            else BaseBotFilters()
        )

        notification_uuid = UUID(callback.data.split("_")[-2])
        current_page = int(callback.data.split("_")[-1])

        if not filters.previous_filters:
            filters.page = current_page
            new_filters = BaseBotFilters(previous_filters=filters)
            await state.update_data(current_filters=new_filters)

        with get_hand_session() as db:
            notification_service = get_bot_notification_service(
                db, str(callback.from_user.id)
            )
            notification = notification_service.mark_read(notification_uuid)

        rendered = TelegramAlertQueue.text(notification.table_text)
        limit = settings.pu_notification_telegram_alert_text_limit
        text = f"*Alert* - `{notification.type}`{rendered[:limit]}"

        keyboard = []
        if notification.big_text:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text="Full log",
                        callback_data=(
                            f"{self.entity_name}_log_"
                            f"{notification.uuid}_{current_page}"
                        ),
                    )
                ]
            )
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="← Back", callback_data=f"{self.entity_name}_back"
                ),
            ]
        )

        await callback.answer(parse_mode="Markdown")
        with contextlib.suppress(TelegramBadRequest):
            await self.telegram_response(
                callback, text, InlineKeyboardMarkup(inline_keyboard=keyboard)
            )

    async def handle_log_click(
        self, callback: types.CallbackQuery, _state: FSMContext
    ) -> None:
        notification_uuid = UUID(callback.data.split("_")[-2])
        current_page = callback.data.split("_")[-1]

        with get_hand_session() as db:
            notification_service = get_bot_notification_service(
                db, str(callback.from_user.id)
            )
            notification = notification_service.mark_read(notification_uuid)

        if not notification.big_text:
            await callback.answer()
            return

        rendered = TelegramAlertQueue.text(notification.big_text)
        limit = settings.pu_notification_telegram_alert_text_limit
        text = f"*Alert log* - `{notification.type}`{rendered[:limit]}"
        keyboard = [
            [
                InlineKeyboardButton(
                    text="← Back",
                    callback_data=(
                        f"{self.entity_name}_uuid_"
                        f"{notification.uuid}_{current_page}"
                    ),
                )
            ]
        ]
        await callback.answer(parse_mode="Markdown")
        with contextlib.suppress(TelegramBadRequest):
            await self.telegram_response(
                callback, text, InlineKeyboardMarkup(inline_keyboard=keyboard)
            )

    async def handle_entity_decrees(
        self, callback: types.CallbackQuery
    ) -> None:
        await callback.answer()

    @staticmethod
    def _button_text(notification: Notification) -> str:
        label = notification.small_text or notification.type
        if not notification.is_read:
            label = f"• {label}"
        return label[:64]
