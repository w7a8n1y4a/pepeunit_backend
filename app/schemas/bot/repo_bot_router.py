import contextlib
from uuid import UUID

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import runtime, settings
from app.configs.db import get_hand_session
from app.configs.errors import NoAccessError
from app.configs.rest import get_bot_repo_service
from app.dto.enum import (
    CommandNames,
    DecreesNames,
    EntityNames,
    RepoType,
)
from app.schemas.bot.base_bot_router import (
    BaseBotFilters,
    BaseBotRouter,
    RepoStates,
)
from app.schemas.bot.utils import (
    byte_converter,
    make_monospace_table_with_title,
)
from app.schemas.pydantic.repo import RepoFilter


class RepoBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.REPO.value
        super().__init__(entity_name=entity_name, states_group=RepoStates)
        self.router.message(Command(CommandNames.REPO.value))(
            self.repo_resolver
        )

    async def repo_resolver(self, message: types.Message, state: FSMContext):
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

        text = "*Repo*"
        if filters.search_string:
            text += f" - `{filters.search_string}`"

        await self.telegram_response(message, text, keyboard)

    async def get_entities_page(
        self, filters: BaseBotFilters, chat_id: str
    ) -> tuple[list, int]:
        with get_hand_session() as db:
            repo_service = get_bot_repo_service(db, chat_id)

            count, repos = repo_service.list(
                RepoFilter(
                    offset=(filters.page - 1)
                    * runtime.get().pu_telegram_items_per_page,
                    limit=runtime.get().pu_telegram_items_per_page,
                    is_public_repository=self.repo_type_to_bool(
                        filters.repository_types
                    ),
                    creator_uuid=(
                        repo_service.access_service.current_agent.uuid
                        if filters.is_only_my_entity
                        else None
                    ),
                    search_string=filters.search_string,
                )
            )

            total_pages = (
                count + runtime.get().pu_telegram_items_per_page - 1
            ) // runtime.get().pu_telegram_items_per_page

        return repos, total_pages

    def build_entities_keyboard(
        self, entities: list, filters: BaseBotFilters, total_pages: int
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        filter_buttons = [
            InlineKeyboardButton(
                text="🔍 Search", callback_data=f"{self.entity_name}_search"
            ),
            InlineKeyboardButton(
                text=("🟢 " if filters.is_only_my_entity else "🔴 ")
                + "My repo",
                callback_data=f"{self.entity_name}_toggle_mine",
            ),
        ]
        builder.row(*filter_buttons)

        filter_visibility_buttons = [
            InlineKeyboardButton(
                text=(
                    "🟢 " if item.value in filters.repository_types else "🔴️ "
                )
                + item.value,
                callback_data=f"{self.entity_name}_toggle_" + item.value,
            )
            for item in RepoType
        ]
        builder.row(*filter_visibility_buttons)

        if entities:
            for repo in entities:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{repo.platform} - {self.repo_name_limit(self.repo_url_small(repo.repository_url), 2)}",
                        callback_data=f"{self.entity_name}_uuid_{repo.uuid}_{filters.page}",
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
        data = await state.get_data()
        filters: BaseBotFilters = (
            BaseBotFilters(**data.get("current_filters"))
            if data.get("current_filters")
            else BaseBotFilters()
        )

        repo_uuid = UUID(callback.data.split("_")[-2])
        current_page = int(callback.data.split("_")[-1])

        if not filters.previous_filters:
            filters.page = current_page
            new_filters = BaseBotFilters(previous_filters=filters)
            await state.update_data(current_filters=new_filters)

        with get_hand_session() as db:
            repo_service = get_bot_repo_service(db, str(callback.from_user.id))
            repo = repo_service.get(repo_uuid)

            is_available = True
            try:
                repo_service.access_service.authorization.check_repo_access(
                    repo
                )
            except NoAccessError:
                is_available = False

        text = f"*Repo* - `{self.repo_name_limit(self.repo_url_small(repo.repository_url), 1.25)}`"

        text += "\n```text\n"

        table = [
            ["Platform", repo.platform],
            ["Sync status", repo.sync_status],
            [
                "Sync last time",
                (
                    repo.sync_last_datetime.strftime("%Y-%m-%d %H:%M:%S")
                    if repo.sync_last_datetime
                    else None
                ),
            ],
            ["Sync error", repo.sync_error],
            [
                "Local size",
                byte_converter(repo.local_repository_size),
            ],
        ]

        if not repo.is_public_repository:
            credentials = repo_service.get_credentials(repo.uuid)
            if credentials:
                table.append(
                    ["Creds status", credentials.status.value.capitalize()]
                )

        text += make_monospace_table_with_title(
            table, "Base Info", lengths=[15, 30]
        )

        text += "```"

        keyboard = []
        if is_available:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text="🫀 Update Local Repo",
                        callback_data=f"{self.entity_name}_decres_{DecreesNames.LOCAL_UPDATE.value}_{repo.uuid}",
                    ),
                ],
            )

        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        text="← Back", callback_data=f"{self.entity_name}_back"
                    ),
                    InlineKeyboardButton(
                        text="↻ Refresh",
                        callback_data=f"{self.entity_name}_uuid_{repo.uuid}_{filters.page}",
                    ),
                    InlineKeyboardButton(
                        text="Browser",
                        url=f"{settings.pu_link}/repo/{repo.uuid}",
                    ),
                ],
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
        *_, decrees_type, repo_uuid = callback.data.split("_")
        repo_uuid = UUID(repo_uuid)

        with get_hand_session() as db:
            repo_service = get_bot_repo_service(db, str(callback.from_user.id))

            match decrees_type:
                case DecreesNames.LOCAL_UPDATE:
                    repo_service.schedule_update(repo_uuid)

        await callback.answer(parse_mode="Markdown")
