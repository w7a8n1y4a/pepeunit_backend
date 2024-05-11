from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.bot import dp
from app.repositories.enum import CommandNames


@dp.message(Command(CommandNames.START.value, CommandNames.HELP.value))
async def start_help_resolver(message: types.Message):

    documentation = (
        '*Верификация*\n'
        '/verification - верификация пользователя\n'
        '\n'
        '*Управление*\n'
        '/start - запуск бота\n'
        '\n'
        '*Информация о узле*\n'
        '/info - базовая информация\n'
    )

    buttons = [
        InlineKeyboardButton(text='Узел', url=f'https://{settings.backend_domain}'),
        InlineKeyboardButton(text='Документация', url='https://docs.pepeunit.com'),
    ]
    builder = InlineKeyboardBuilder()
    for button in buttons:
        builder.row(button)

    builder.adjust(2)

    await message.answer(documentation, reply_markup=builder.as_markup(), parse_mode='Markdown')
