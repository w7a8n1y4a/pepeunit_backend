import logging
from typing import Optional
from uuid import UUID

from aiogram import F, Router, flags, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.configs.db import get_session
from app.configs.gql import get_repo_service
from app.configs.sub_entities import InfoSubEntity
from app.dto.enum import CommandNames
from app.schemas.pydantic.repo import RepoFilter

repo_router = Router()

ITEMS_PER_PAGE = 5


async def get_repos_page(page: int = 1, chat_id: Optional[str] = None) -> tuple[list, int]:
    db = next(get_session())
    try:
        repo_service = get_repo_service(InfoSubEntity({'db': db, 'jwt_token': str(chat_id), 'is_bot_auth': True}))

        repo_filter = RepoFilter(offset=(page - 1) * ITEMS_PER_PAGE, limit=ITEMS_PER_PAGE)

        count, repos = repo_service.list(repo_filter)
        total_pages = (count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

        return repos, total_pages
    except Exception as e:
        logging.error(e)
        return [], 0
    finally:
        db.close()


def build_repos_keyboard(repos: list, current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for repo in repos:
        builder.row(
            InlineKeyboardButton(
                text=f"{repo.name} {repo.visibility_level.capitalize()}", callback_data=f"repo_{repo.uuid}"
            )
        )

    if total_pages > 1:
        pagination_buttons = []

        if current_page > 1:
            pagination_buttons.append(InlineKeyboardButton(text="<", callback_data=f"repo_page_{current_page - 1}"))
        else:
            pagination_buttons.append(InlineKeyboardButton(text="|", callback_data="repo_noop"))

        pagination_buttons.append(
            InlineKeyboardButton(text=f"{current_page} из {total_pages}", callback_data="repo_noop")
        )

        # Кнопка "Вперед"
        if current_page < total_pages:
            pagination_buttons.append(InlineKeyboardButton(text=">", callback_data=f"repo_page_{current_page + 1}"))
        else:
            pagination_buttons.append(InlineKeyboardButton(text="|", callback_data="repo_noop"))

        builder.row(*pagination_buttons)

    return builder.as_markup()


@repo_router.message(Command(CommandNames.REPO))
async def repo_resolver(message: types.Message):
    repos, total_pages = await get_repos_page(page=1, chat_id=message.chat.id)

    if not repos:
        await message.answer("Не удалось загрузить репозитории")
        return

    keyboard = build_repos_keyboard(repos, current_page=1, total_pages=total_pages)
    await message.answer("Repos", reply_markup=keyboard, parse_mode='Markdown')


@repo_router.callback_query(F.data.startswith('repo_page_'))
async def handle_pagination(callback: types.CallbackQuery):
    page = int(callback.data.split('_')[-1])

    repos, total_pages = await get_repos_page(page=page, chat_id=callback.message.chat.id)

    if not repos:
        await callback.answer("Не удалось загрузить репозитории")
        return

    keyboard = build_repos_keyboard(repos, current_page=page, total_pages=total_pages)
    await callback.message.edit_text("Repos", reply_markup=keyboard)
    await callback.answer()


@repo_router.callback_query(F.data == 'repo_noop')
async def handle_noop(callback: types.CallbackQuery):
    await callback.answer()


@repo_router.callback_query(F.data.startswith('repo_'))
@flags.callback_answer(text="Thanks", cache_time=30)
async def handle_buttons_handler(callback: types.CallbackQuery):
    repo_uuid = UUID(callback.data.split('_')[1])
    await callback.message.answer(f'Выбран репозиторий с UUID: {repo_uuid}')
