import contextlib
from uuid import UUID

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.clickhouse import get_hand_clickhouse_client
from app.configs.db import get_hand_session
from app.configs.rest import get_bot_repo_service
from app.dto.enum import (
    CommandNames,
    DecreesNames,
    EntityNames,
    VisibilityLevel,
)
from app.schemas.bot.base_bot_router import (
    BaseBotFilters,
    BaseBotRouter,
    RepoStates,
)
from app.schemas.bot.utils import make_monospace_table_with_title
from app.schemas.pydantic.repo import RepoFilter


class RepoBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.REPO.value
        super().__init__(entity_name=entity_name, states_group=RepoStates)
        self.router.message(Command(CommandNames.REPO))(self.repo_resolver)

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

        text = "*Repos*"
        if filters.search_string:
            text += f" - `{filters.search_string}`"

        await self.telegram_response(message, text, keyboard)

    async def get_entities_page(
        self, filters: BaseBotFilters, chat_id: str
    ) -> tuple[list, int]:
        with get_hand_session() as db, get_hand_clickhouse_client() as cc:
            repo_service = get_bot_repo_service(db, cc, chat_id)

            count, repos = repo_service.list(
                RepoFilter(
                    offset=(filters.page - 1)
                    * settings.pu_telegram_items_per_page,
                    limit=settings.pu_telegram_items_per_page,
                    visibility_level=filters.visibility_levels or [],
                    creator_uuid=(
                        repo_service.access_service.current_agent.uuid
                        if filters.is_only_my_entity
                        else None
                    ),
                    search_string=filters.search_string,
                )
            )

            total_pages = (
                count + settings.pu_telegram_items_per_page - 1
            ) // settings.pu_telegram_items_per_page

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
                + "My repos",
                callback_data=f"{self.entity_name}_toggle_mine",
            ),
        ]
        builder.row(*filter_buttons)

        filter_visibility_buttons = [
            InlineKeyboardButton(
                text=(
                    "🟢 " if item.value in filters.visibility_levels else "🔴️ "
                )
                + item.value,
                callback_data=f"{self.entity_name}_toggle_" + item.value,
            )
            for item in VisibilityLevel
        ]
        builder.row(*filter_visibility_buttons)

        if entities:
            for repo in entities:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{self.header_name_limit(repo.name)} - {repo.visibility_level}",
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

        with get_hand_session() as db, get_hand_clickhouse_client() as cc:
            repo_service = get_bot_repo_service(
                db, cc, str(callback.from_user.id)
            )
            repo = repo_service.get(repo_uuid)

            is_creator = (
                repo_service.access_service.current_agent.uuid
                == repo.creator_uuid
            )

            try:
                versions = repo_service.get_versions(repo_uuid)
            except Exception:
                versions = None

        text = f"*Repo* - `{self.header_name_limit(repo.name)}` - *{repo.visibility_level}*"

        text += "\n```text\n"

        table = [
            [
                "Default Branch",
                self.header_name_limit(repo.default_branch)
                if repo.default_branch
                else None,
            ],
            ["Compilable ?", repo.is_compilable_repo],
            ["Auto-update ?", repo.is_auto_update_repo],
            ["Tags only ?", repo.is_only_tag_update],
        ]

        if not repo.is_auto_update_repo:
            table.append(
                [
                    "Default Commit",
                    self.git_hash_limit(repo.default_commit)
                    if repo.default_commit
                    else None,
                ]
            )

        if versions and versions.unit_count:
            table.append(["Total Units", versions.unit_count])

            table_version = [["№", "Version", "Unit Count"]]

            for inc, version in enumerate(versions.versions):
                table_version.append(
                    [
                        inc,
                        version.tag
                        if version.tag
                        else self.git_hash_limit(version.commit),
                        version.unit_count,
                    ]
                )

        text += make_monospace_table_with_title(table, "Base Info")

        text += "\n"

        if versions and versions.unit_count:
            text += make_monospace_table_with_title(
                table_version, "Version distribution"
            )

        text += "```"

        keyboard = []
        if is_creator:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text="📈 Update Related Unit",
                        callback_data=f"{self.entity_name}_decres_{DecreesNames.RELATED_UNIT.value}_{repo.uuid}",
                    ),
                ],
            )

        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        text="⚡️ Registry",
                        callback_data=f"{EntityNames.REGISTRY.value}_uuid_{repo.repository_registry_uuid}_{filters.page}",
                    ),
                    InlineKeyboardButton(
                        text="✨ Units",
                        callback_data=f"{EntityNames.UNIT.value}_repo_{repo.uuid}",
                    ),
                ],
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

        with get_hand_session() as db, get_hand_clickhouse_client() as cc:
            repo_service = get_bot_repo_service(
                db, cc, str(callback.from_user.id)
            )

            text = ""
            match decrees_type:
                case DecreesNames.RELATED_UNIT:
                    text = "Success linked Unit update"
                    repo_service.update_units_firmware(repo_uuid)

        await callback.answer(parse_mode="Markdown")
        await self.telegram_response(callback, text, is_editable=False)
