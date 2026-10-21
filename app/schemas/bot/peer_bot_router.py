import contextlib
from urllib.parse import urlparse
from uuid import UUID

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import runtime
from app.configs.db import get_hand_session
from app.configs.errors import CustomException
from app.configs.rest import get_bot_peer_service
from app.domain.peer_model import Peer
from app.dto.enum import CommandNames, DecreesNames, EntityNames
from app.schemas.bot.base_bot_router import (
    BaseBotFilters,
    BaseBotRouter,
    PeerStates,
)
from app.schemas.bot.utils import (
    format_datetime,
    make_monospace_table_with_title,
)
from app.schemas.pydantic.instance import CurrentInstanceSchemaV1
from app.schemas.pydantic.peer import PeerFilter


class PeerBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.PEER.value
        super().__init__(entity_name=entity_name, states_group=PeerStates)
        self.router.message(Command(CommandNames.PEERS.value))(
            self.peer_resolver
        )

    async def peer_resolver(self, message: types.Message, state: FSMContext):
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

        text = "*Peers*"

        await self.telegram_response(message, text, keyboard)

    async def get_entities_page(
        self, filters: BaseBotFilters, chat_id: str
    ) -> tuple[list, int]:
        with get_hand_session() as db:
            peer_service = get_bot_peer_service(db, chat_id)
            count, peers = peer_service.list(
                PeerFilter(
                    offset=(filters.page - 1)
                    * runtime.get().pu_telegram_items_per_page,
                    limit=runtime.get().pu_telegram_items_per_page,
                )
            )

            total_pages = (
                count + runtime.get().pu_telegram_items_per_page - 1
            ) // runtime.get().pu_telegram_items_per_page

        return peers, total_pages

    def build_entities_keyboard(
        self, entities: list, filters: BaseBotFilters, total_pages: int
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        if entities:
            for peer in entities:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{peer.trust_status} - {self._peer_domain(peer.url)}",
                        callback_data=f"{self.entity_name}_uuid_{peer.uuid}_{filters.page}",
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

        peer_uuid = UUID(callback.data.split("_")[-2])
        current_page = int(callback.data.split("_")[-1])

        if not filters.previous_filters:
            filters.page = current_page
            new_filters = BaseBotFilters(previous_filters=filters)
            await state.update_data(current_filters=new_filters)

        with get_hand_session() as db:
            peer_service = get_bot_peer_service(db, str(callback.from_user.id))
            peer = peer_service.get(peer_uuid)

        text = f"*Peer* - `{self._peer_domain(peer.url)}`"
        text += "\n```text\n"
        text += make_monospace_table_with_title(
            self._get_base_info_table(peer),
            "Base Info",
            lengths=[15, 30],
        )
        text += "```"

        keyboard = []
        if runtime.get().pu_ff_federation_enable:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text="🫀 Scan Peer",
                        callback_data=f"{self.entity_name}_decres_{DecreesNames.SCAN.value}_{peer.uuid}",
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
                    callback_data=f"{self.entity_name}_uuid_{peer.uuid}_{filters.page}",
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
        *_, decrees_type, peer_uuid = callback.data.split("_")
        peer_uuid = UUID(peer_uuid)

        try:
            with get_hand_session() as db:
                peer_service = get_bot_peer_service(
                    db, str(callback.from_user.id)
                )
                match decrees_type:
                    case DecreesNames.SCAN:
                        peer_service.scan_one(peer_uuid)
        except CustomException as e:
            await callback.answer()
            await self.telegram_response(
                callback, e.message, is_editable=False
            )
            return

        await callback.answer(parse_mode="Markdown")

    @staticmethod
    def _peer_domain(url: str) -> str:
        return urlparse(url).netloc

    def _get_base_info_table(self, peer: Peer) -> list[list]:
        table = [
            ["Domain", self._peer_domain(peer.url)],
            ["Trust", peer.trust_status],
            ["Collection", peer.last_collection_status],
            [
                "Last ping",
                round(peer.last_ping) if peer.last_ping else None,
            ],
            ["Last success", format_datetime(peer.last_success_datetime)],
        ]

        if peer.last_collection_error:
            table.append(["Error", peer.last_collection_error])
            return table

        if not peer.state:
            return table

        current = CurrentInstanceSchemaV1.model_validate(peer.state)
        table.append(["Version", current.version])
        table.append(["Units", current.metrics.unit_count])

        if current.contacts.email:
            table.append(["Email", current.contacts.email])
        if current.contacts.telegram:
            table.append(["Telegram", current.contacts.telegram])

        return table
