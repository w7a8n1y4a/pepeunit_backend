import contextlib
from urllib.parse import urlparse
from uuid import UUID

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.db import get_hand_session
from app.configs.errors import CustomException
from app.configs.rest import get_app_instance_cache, get_bot_instance_service
from app.domain.instance_model import Instance
from app.dto.enum import CommandNames, DecreesNames, EntityNames
from app.schemas.bot.base_bot_router import (
    BaseBotFilters,
    BaseBotRouter,
    InstanceStates,
)
from app.schemas.bot.utils import make_monospace_table_with_title
from app.schemas.pydantic.instance import (
    CurrentInstanceSchemaV1,
    InstanceFilter,
)


class InstanceBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.INSTANCE.value
        super().__init__(entity_name=entity_name, states_group=InstanceStates)
        self.router.message(Command(CommandNames.INSTANCES.value))(
            self.instance_resolver
        )

    async def instance_resolver(
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

        text = "*Instances*"

        await self.telegram_response(message, text, keyboard)

    async def get_entities_page(
        self, filters: BaseBotFilters, chat_id: str
    ) -> tuple[list, int]:
        with get_hand_session() as db:
            instance_service = get_bot_instance_service(db, chat_id)
            count, instances = instance_service.list(
                InstanceFilter(
                    offset=(filters.page - 1)
                    * settings.pu_telegram_items_per_page,
                    limit=settings.pu_telegram_items_per_page,
                )
            )

            total_pages = (
                count + settings.pu_telegram_items_per_page - 1
            ) // settings.pu_telegram_items_per_page

        return instances, total_pages

    def build_entities_keyboard(
        self, entities: list, filters: BaseBotFilters, total_pages: int
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        if entities:
            for instance in entities:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{instance.trust_status} - {self._instance_domain(instance.url)}",
                        callback_data=f"{self.entity_name}_uuid_{instance.uuid}_{filters.page}",
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

        instance_uuid = UUID(callback.data.split("_")[-2])
        current_page = int(callback.data.split("_")[-1])

        if not filters.previous_filters:
            filters.page = current_page
            new_filters = BaseBotFilters(previous_filters=filters)
            await state.update_data(current_filters=new_filters)

        with get_hand_session() as db:
            instance_service = get_bot_instance_service(
                db, str(callback.from_user.id)
            )
            instance = instance_service.get(instance_uuid)

        text = f"*Instance* - `{self._instance_domain(instance.url)}`"
        text += "\n```text\n"
        text += make_monospace_table_with_title(
            self._instance_card_rows(instance),
            "Base Info",
            lengths=[15, 30],
        )
        text += "```"

        keyboard = []
        if settings.pu_ff_federation_enable:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text="🫀 Scan Instance",
                        callback_data=f"{self.entity_name}_decres_{DecreesNames.SCAN.value}_{instance.uuid}",
                    )
                ]
            )
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="← Back", callback_data=f"{self.entity_name}_back"
                ),
                InlineKeyboardButton(
                    text="↻ Refresh",
                    callback_data=f"{self.entity_name}_uuid_{instance.uuid}_{filters.page}",
                ),
            ]
        )

        await callback.answer(parse_mode="Markdown")
        with contextlib.suppress(TelegramBadRequest):
            await self.telegram_response(
                callback, text, InlineKeyboardMarkup(inline_keyboard=keyboard)
            )

    async def handle_entity_decrees(
        self, callback: types.CallbackQuery
    ) -> None:
        *_, decrees_type, instance_uuid = callback.data.split("_")
        instance_uuid = UUID(instance_uuid)

        try:
            with get_hand_session() as db:
                instance_service = get_bot_instance_service(
                    db, str(callback.from_user.id)
                )
                text = ""
                match decrees_type:
                    case DecreesNames.SCAN:
                        instance_service.scan_one(
                            instance_uuid, get_app_instance_cache()
                        )
                        text = "Started Instance scan"
        except CustomException as e:
            await callback.answer()
            await self.telegram_response(
                callback, e.message, is_editable=False
            )
            return

        await callback.answer(parse_mode="Markdown")
        await self.telegram_response(callback, text, is_editable=False)

    @staticmethod
    def _instance_domain(url: str) -> str:
        return urlparse(url).netloc

    def _instance_card_rows(self, instance: Instance) -> list[list]:
        rows = [
            ["Domain", self._instance_domain(instance.url)],
            ["Trust", instance.trust_status],
            ["Collection", instance.last_collection_status],
            ["Last ping", instance.last_ping],
            [
                "Last success",
                (
                    instance.last_success_datetime.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if instance.last_success_datetime
                    else None
                ),
            ],
        ]
        if instance.last_collection_error:
            rows.append(["Error", instance.last_collection_error])
            return rows

        if not instance.state:
            return rows

        current = CurrentInstanceSchemaV1.model_validate(instance.state)
        rows.append(["Version", current.version])
        rows.append(["Units", current.metrics.unit_count])
        if current.contacts.email:
            rows.append(["Email", current.contacts.email])
        if current.contacts.telegram:
            rows.append(["Telegram", current.contacts.telegram])
        return rows
