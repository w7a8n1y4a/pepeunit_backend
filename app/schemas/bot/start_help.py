import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from fastapi import HTTPException

from app import settings
from app.configs.db import get_session
from app.configs.gql import get_user_service
from app.configs.sub_entities import InfoSubEntity
from app.dto.enum import CommandNames
from app.repositories.user_repository import UserRepository

base_router = Router()


@base_router.message(Command(CommandNames.START, CommandNames.HELP))
async def start_help_resolver(message: types.Message):
    args = message.text.split()
    code = args[1] if len(args) == 2 else None

    if code:
        db = next(get_session())
        try:
            user_repository = UserRepository(db)
            user = user_repository.get_user_by_telegram_id(str(message.chat.id))

            if user:
                text = f'Your account is already linked to an account on instance {settings.backend_domain}'
                await message.answer(text, parse_mode='Markdown')
            else:
                user_service = get_user_service(InfoSubEntity({'db': db, 'jwt_token': None}))
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
        except Exception as e:
            logging.error(e)
        finally:
            db.close()

        return

    documentation = '*Control*\n' '/start - bot run\n' '\n' '*Instance information*\n' '/info - base info\n'

    buttons = [
        InlineKeyboardButton(text='Instance', url=settings.backend_link),
        InlineKeyboardButton(text='Docs', url='https://pepeunit.com'),
    ]
    builder = InlineKeyboardBuilder()
    for button in buttons:
        builder.row(button)

    builder.adjust(2)

    await message.answer(documentation, reply_markup=builder.as_markup(), parse_mode='Markdown')
