from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from fastapi import HTTPException

from app import settings
from app.configs.clickhouse import get_hand_clickhouse_client
from app.configs.db import get_hand_session
from app.configs.rest import get_user_service
from app.dto.enum import CommandNames
from app.repositories.user_repository import UserRepository
from app.schemas.bot.utils import make_monospace_table_with_title
from app.schemas.pydantic.shared import Root
from app.services.user_service import UserService

base_router = Router()


@base_router.message(Command(CommandNames.START, CommandNames.HELP))
async def start_help_resolver(message: types.Message):
    args = message.text.split()
    code = args[1] if len(args) == 2 else None

    if code:
        with get_hand_session() as db:
            user_repository = UserRepository(db)
            user = user_repository.get_user_by_telegram_id(str(message.chat.id))

            if user:
                text = f'Your account is already linked to an account on instance {settings.backend_domain}'
            else:
                with get_hand_clickhouse_client() as cc:
                    user_service = get_user_service(db, cc, True)
                    try:
                        await user_service.verification(str(message.chat.id), code)
                        db.close()

                        text = 'You have been successfully verified'
                    except HTTPException as e:
                        if e.status_code == 422:
                            text = 'You are already verified'
                        else:
                            text = 'There is no such code'

        await message.answer(text, parse_mode='Markdown')
        return

    root_data = Root()

    text = f'\n```text\n'
    table = [
        ['Command', 'Info'],
        ['/info', 'Instance metrics'],
        ['/repo', 'Repo search, Repo base information, Repo base buttons'],
        [
            '/unit',
            'Unit search, Unit base information, get env file, send mqtt command, get firmware archives, check IO nodes and check logs',
        ],
    ]
    text += make_monospace_table_with_title(table, f'Backend Version - {root_data.version}', [10, 28])
    text += '```'

    buttons = [
        InlineKeyboardButton(text='Frontend', url=settings.backend_link),
        InlineKeyboardButton(text='Documentation', url='https://pepeunit.com'),
    ]
    builder = InlineKeyboardBuilder()

    builder.add(*buttons)

    buttons = [
        InlineKeyboardButton(text='Swagger', url=root_data.swagger),
        InlineKeyboardButton(text='Graphql', url=root_data.graphql),
        InlineKeyboardButton(text='Grafana', url=root_data.grafana),
    ]

    builder.row(*buttons)

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode='Markdown')
