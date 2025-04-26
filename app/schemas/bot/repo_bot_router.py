from typing import Union
from uuid import UUID

from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.db import get_session
from app.configs.gql import get_repo_service
from app.configs.sub_entities import InfoSubEntity
from app.dto.enum import CommandNames, DecreesNames, EntityNames, VisibilityLevel
from app.schemas.bot.base_bot_router import BaseBotFilters, BaseBotRouter, RepoStates
from app.schemas.bot.utils import make_monospace_table_with_title
from app.schemas.pydantic.repo import RepoFilter


class RepoBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.REPO
        super().__init__(entity_name=entity_name, states_group=RepoStates)
        self.router.message(Command(CommandNames.REPO))(self.repo_resolver)

    async def repo_resolver(self, message: types.Message, state: FSMContext):
        await state.set_state(None)
        filters = BaseBotFilters()
        await state.update_data(current_filters=filters)
        await self.show_entities(message, filters)

    async def show_entities(self, message: Union[types.Message, types.CallbackQuery], filters: BaseBotFilters):
        chat_id = message.chat.id if isinstance(message, types.Message) else message.from_user.id

        entities, total_pages = await self.get_entities_page(filters, str(chat_id))
        keyboard = self.build_entities_keyboard(entities, filters, total_pages)

        text = "*Repos*"
        if filters.search_string:
            text += f" - `{filters.search_string}`"

        await self.telegram_response(message, text, keyboard)

    async def get_entities_page(self, filters: BaseBotFilters, chat_id: str) -> tuple[list, int]:
        db = next(get_session())
        try:
            repo_service = get_repo_service(InfoSubEntity({'db': db, 'jwt_token': chat_id, 'is_bot_auth': True}))

            count, repos = repo_service.list(
                RepoFilter(
                    offset=(filters.page - 1) * settings.telegram_items_per_page,
                    limit=settings.telegram_items_per_page,
                    visibility_level=filters.visibility_levels or [],
                    creator_uuid=repo_service.access_service.current_agent.uuid if filters.is_only_my_entity else None,
                    search_string=filters.search_string,
                )
            )

            total_pages = (count + settings.telegram_items_per_page - 1) // settings.telegram_items_per_page

        except Exception as e:
            repos, total_pages = [], 0
        finally:
            db.close()

        return repos, total_pages

    def build_entities_keyboard(
        self, entities: list, filters: BaseBotFilters, total_pages: int
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        filter_buttons = [
            InlineKeyboardButton(text="🔍 Search", callback_data=f"{self.entity_name}_search"),
            InlineKeyboardButton(
                text=("🟢 " if filters.is_only_my_entity else "🔴 ") + 'My repos',
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
            for repo in entities:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{self.header_name_limit(repo.name)} - {repo.visibility_level}",
                        callback_data=f"{self.entity_name}_uuid_{repo.uuid}_{filters.page}",
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

        return builder.as_markup()

    async def handle_entity_click(self, callback: types.CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        filters: BaseBotFilters = (
            BaseBotFilters(**data.get("current_filters")) if data.get("current_filters") else BaseBotFilters()
        )

        repo_uuid = UUID(callback.data.split('_')[-2])
        current_page = int(callback.data.split('_')[-1])

        if not filters.previous_filters:
            filters.page = current_page
            new_filters = BaseBotFilters(previous_filters=filters)
            await state.update_data(current_filters=new_filters)

        db = next(get_session())
        try:
            repo_service = get_repo_service(
                InfoSubEntity({'db': db, 'jwt_token': str(callback.from_user.id), 'is_bot_auth': True})
            )
            repo = repo_service.get(repo_uuid)

            versions = None
            try:
                versions = repo_service.get_versions(repo_uuid)
            except Exception as e:
                pass

        finally:
            db.close()

        text = f'*Repo* - `{self.header_name_limit(repo.name)}` - *{repo.visibility_level}*'

        if versions and versions.unit_count:
            text += f'\n```text\nTotal Units this Repo - {versions.unit_count}\n\n'

            table = [['№', 'Version', 'Unit Count']]

            for inc, version in enumerate(versions.versions):
                table.append(
                    [inc, version.tag if version.tag else self.git_hash_limit(version.commit), version.unit_count]
                )

            text += make_monospace_table_with_title(table, 'Version distribution')

            text += '```'

        keyboard = [
            [
                InlineKeyboardButton(
                    text='🫀 Update Local Repo',
                    callback_data=f'{self.entity_name}_decrees_{DecreesNames.LOCAL_UPDATE}_{repo.uuid}',
                ),
                InlineKeyboardButton(
                    text='📈 Update Related Unit',
                    callback_data=f'{self.entity_name}_decrees_{DecreesNames.RELATED_UNIT}_{repo.uuid}',
                ),
            ],
            [
                InlineKeyboardButton(text='✨ Units', callback_data=f'{EntityNames.UNIT}_repo_{repo.uuid}'),
            ],
            [
                InlineKeyboardButton(text='← Back', callback_data=f'{self.entity_name}_back'),
                InlineKeyboardButton(text='Browser', url=f'{settings.backend_link}/repo/{repo.uuid}'),
            ],
        ]

        await callback.answer(parse_mode='Markdown')
        await self.telegram_response(callback, text, InlineKeyboardMarkup(inline_keyboard=keyboard))

    async def handle_entity_decrees(self, callback: types.CallbackQuery) -> None:

        *_, decrees_type, repo_uuid = callback.data.split('_')
        repo_uuid = UUID(repo_uuid)

        db = next(get_session())
        try:
            repo_service = get_repo_service(
                InfoSubEntity({'db': db, 'jwt_token': str(callback.from_user.id), 'is_bot_auth': True})
            )

            text = ''
            match decrees_type:
                case DecreesNames.LOCAL_UPDATE:
                    text = 'Local repository update successfully started'
                    repo_service.update_local_repo(repo_uuid)
                case DecreesNames.RELATED_UNIT:
                    text = 'Linked Unit update has started successfully'
                    repo_service.update_units_firmware(repo_uuid)

        except Exception as e:
            try:
                text = e.message
            except AttributeError:
                text = e
        finally:
            db.close()

        await callback.answer(parse_mode='Markdown')
        await self.telegram_response(callback, text, is_editable=False)
