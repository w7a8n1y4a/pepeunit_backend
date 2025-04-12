import logging
from typing import Optional, Union
from uuid import UUID

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from fastapi import Query
from pydantic import BaseModel

from app import settings
from app.configs.db import get_session
from app.configs.gql import get_repo_service
from app.configs.sub_entities import InfoSubEntity
from app.dto.enum import CommandNames, VisibilityLevel
from app.schemas.pydantic.repo import RepoFilter

repo_router = Router()
ITEMS_PER_PAGE = 7


class RepoStates(StatesGroup):
    waiting_for_search = State()


class RepoFilters(BaseModel):
    page: int = 1
    visibility_levels: list[str] = Query([item.value for item in VisibilityLevel])
    is_only_my_repo: bool = False
    search_string: Optional[str] = None
    previous_filters: Optional["RepoFilters"] = None

    class Config:
        arbitrary_types_allowed = True


async def get_repos_page(filters: RepoFilters, chat_id: str) -> tuple[list, int]:
    db = next(get_session())
    try:
        repo_service = get_repo_service(InfoSubEntity({'db': db, 'jwt_token': chat_id, 'is_bot_auth': True}))

        count, repos = repo_service.list(
            RepoFilter(
                offset=(filters.page - 1) * ITEMS_PER_PAGE,
                limit=ITEMS_PER_PAGE,
                visibility_level=filters.visibility_levels or None,
                creator_uuid=repo_service.access_service.current_agent.uuid if filters.is_only_my_repo else None,
                search_string=filters.search_string,
            )
        )
        total_pages = (count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

        return repos, total_pages
    except Exception as e:
        logging.error(f"Error getting repos: {e}")
        return [], 0
    finally:
        db.close()


def build_repos_keyboard(repos: list, filters: RepoFilters, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for repo in repos:
        builder.row(
            InlineKeyboardButton(
                text=f"{repo.name} {repo.visibility_level.capitalize()}",
                callback_data=f"repo_{repo.uuid}_{filters.page}",
            )
        )

    filter_buttons = [
        InlineKeyboardButton(text="🔍 Search", callback_data="repo_search"),
        InlineKeyboardButton(
            text=("🟢 " if filters.is_only_my_repo else "🔴 ") + 'My repos', callback_data="toggle_mine"
        ),
    ]
    builder.row(*filter_buttons)

    filter_visibility_buttons = [
        InlineKeyboardButton(
            text=("🟢 " if item.value in filters.visibility_levels else "🔴️ ") + item.value.capitalize(),
            callback_data="toggle_" + item.value.lower(),
        )
        for item in VisibilityLevel
    ]
    builder.row(*filter_visibility_buttons)

    if total_pages > 1:
        pagination_row = []
        if filters.page > 1:
            pagination_row.append(InlineKeyboardButton(text="⬅️", callback_data="prev_page"))

        pagination_row.append(InlineKeyboardButton(text=f"{filters.page}/{total_pages}", callback_data="noop"))

        if filters.page < total_pages:
            pagination_row.append(InlineKeyboardButton(text="➡️", callback_data="next_page"))
        builder.row(*pagination_row)

    return builder.as_markup()


async def show_repos(message: Union[types.Message, types.CallbackQuery], filters: RepoFilters):

    chat_id = message.chat.id if isinstance(message, types.Message) else message.from_user.id

    repos, total_pages = await get_repos_page(filters, str(chat_id))

    if not repos:
        text = "No repos found"

        if isinstance(message, types.Message):
            await message.answer(text)
        else:
            await message.message.edit_text(text)

        return

    keyboard = build_repos_keyboard(repos, filters, total_pages)

    text = "Repos"
    if filters.search_string:
        text += f" - {filters.search_string}"

    if isinstance(message, types.Message):
        await message.answer(text, reply_markup=keyboard)
    else:
        await message.message.edit_text(text, reply_markup=keyboard)


@repo_router.message(Command(CommandNames.REPO))
async def repo_resolver(message: types.Message, state: FSMContext):
    await state.set_state(None)
    filters = RepoFilters()
    await state.update_data(current_filters=filters)
    await show_repos(message, filters)


@repo_router.callback_query(F.data == "repo_search")
async def search_repo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Please enter search query:")
    await state.set_state(RepoStates.waiting_for_search)


@repo_router.message(RepoStates.waiting_for_search)
async def process_search(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_filters = data.get("current_filters", RepoFilters())

    filters = RepoFilters(search_string=message.text, previous_filters=current_filters)
    await state.update_data(current_filters=filters)
    await state.set_state(None)
    await show_repos(message, filters)


@repo_router.callback_query(F.data.startswith("toggle_"))
async def toggle_filter(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    filters: RepoFilters = data.get("current_filters", RepoFilters())

    match callback.data:
        case "toggle_public":
            if "Public" in filters.visibility_levels:
                filters.visibility_levels.remove("Public")
            else:
                filters.visibility_levels.append("Public")
        case "toggle_internal":
            if "Internal" in filters.visibility_levels:
                filters.visibility_levels.remove("Internal")
            else:
                filters.visibility_levels.append("Internal")
        case "toggle_private":
            if "Private" in filters.visibility_levels:
                filters.visibility_levels.remove("Private")
            else:
                filters.visibility_levels.append("Private")
        case "toggle_mine":
            filters.is_only_my_repo = not filters.is_only_my_repo

    await state.update_data(current_filters=filters)
    await show_repos(callback, filters)


@repo_router.callback_query(F.data.in_(["prev_page", "next_page"]))
async def change_page(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    filters: RepoFilters = data.get("current_filters", RepoFilters())

    if callback.data == "prev_page" and filters.page > 1:
        filters.page -= 1

    elif callback.data == "next_page":
        filters.page += 1

    await state.update_data(current_filters=filters)
    await show_repos(callback, filters)


@repo_router.callback_query(F.data == "noop")
async def handle_noop(callback: types.CallbackQuery):
    await callback.answer()


@repo_router.callback_query(F.data.startswith("repo_") and ~F.data.startswith("repo_page_"))
async def handle_repo_click(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    filters: RepoFilters = data.get("current_filters", RepoFilters())

    # Save current filters as previous
    repo_uuid = UUID(callback.data.split('_')[1])
    current_page = int(callback.data.split('_')[2])

    filters.page = current_page
    new_filters = RepoFilters(previous_filters=filters)
    await state.update_data(current_filters=new_filters)

    db = next(get_session())
    try:
        repo_service = get_repo_service(
            InfoSubEntity({'db': db, 'jwt_token': str(callback.from_user.id), 'is_bot_auth': True})
        )
        repo = repo_service.get(repo_uuid)
    finally:
        db.close()

    keyboard = [
        [
            InlineKeyboardButton(text='Update Local Repo', callback_data=f'local_update_{repo.uuid}'),
            InlineKeyboardButton(text='Update Related Unit', callback_data=f'related_unit_{repo.uuid}'),
        ],
        [
            InlineKeyboardButton(text='← Back', callback_data='repo_back'),
            InlineKeyboardButton(text='Browser', url=f'{settings.backend_link}/repo/{repo.uuid}'),
        ],
    ]

    await callback.message.edit_text(
        f'{repo.name} {repo.visibility_level.capitalize()}', reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@repo_router.callback_query(F.data == 'repo_back')
async def back_to_list(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    filters: RepoFilters = data.get("current_filters", RepoFilters())

    if filters.previous_filters:
        await state.update_data(current_filters=filters.previous_filters)
        await show_repos(callback, filters.previous_filters)
    else:
        await show_repos(callback, RepoFilters())


@repo_router.callback_query(F.data.startswith('local_update_'))
async def local_update_handler(callback: types.CallbackQuery):
    repo_uuid = UUID(callback.data.split('_')[-1])

    db = next(get_session())
    try:
        repo_service = get_repo_service(
            InfoSubEntity({'db': db, 'jwt_token': str(callback.from_user.id), 'is_bot_auth': True})
        )
        repo_service.update_local_repo(repo_uuid)
    except Exception as e:
        await callback.answer()
        await callback.message.answer(str(e))
        return
    finally:
        db.close()

    await callback.answer()
    await callback.message.answer('Local repository update successfully started')


@repo_router.callback_query(F.data.startswith('related_unit_'))
async def related_unit_handler(callback: types.CallbackQuery):
    repo_uuid = UUID(callback.data.split('_')[-1])

    db = next(get_session())
    try:
        repo_service = get_repo_service(
            InfoSubEntity({'db': db, 'jwt_token': str(callback.from_user.id), 'is_bot_auth': True})
        )
        repo_service.update_units_firmware(repo_uuid)
    except Exception as e:
        await callback.answer()
        await callback.message.answer(str(e))
        return
    finally:
        db.close()

    await callback.answer()
    await callback.message.answer('Linked Unit update has started successfully')
