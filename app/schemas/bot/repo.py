import logging

from aiogram import F, Router, flags, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.configs.db import get_session
from app.configs.gql import get_repo_service
from app.configs.sub_entities import InfoSubEntity
from app.dto.enum import CommandNames
from app.schemas.pydantic.repo import RepoFilter

repo_router = Router()


@repo_router.message(Command(CommandNames.REPO))
async def repo_resolver(message: types.Message):
    db = next(get_session())

    try:
        repo_service = get_repo_service(
            InfoSubEntity({'db': db, 'jwt_token': str(message.chat.id), 'is_bot_auth': True})
        )
        count, repos = repo_service.list(RepoFilter())

    except Exception as e:
        logging.error(e)
    finally:
        db.close()

    keyboard_list = [
        [
            InlineKeyboardButton(
                text=repo.name + ' ' + repo.visibility_level.capitalize(), callback_data=f'repo_{repo.uuid}'
            )
        ]
        for inc, repo in enumerate(repos)
    ]

    await message.answer(
        "Repos", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_list), parse_mode='Markdown'
    )


@repo_router.callback_query(F.data.startswith('repo_'))
@flags.callback_answer(text="Thanks", cache_time=30)
async def handle_buttons_handler(callback: types.CallbackQuery):
    print(callback.data)
    await callback.message.answer('test')
