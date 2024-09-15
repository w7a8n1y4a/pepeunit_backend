from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.bot import bot, dp
from app.repositories.enum import CommandNames


@dp.message(Command(CommandNames.START, CommandNames.HELP))
async def start_help_resolver(message: types.Message):

    documentation = (
        '*Verification*\n'
        '/verification - User verification\n'
        '\n'
        '*Control*\n'
        '/start - bot run\n'
        '\n'
        '*Instance information*\n'
        '/info - base info\n'
    )

    buttons = [
        InlineKeyboardButton(text='Instance', url=settings.backend_link),
        InlineKeyboardButton(text='Docs', url='https://pepeunit.com'),
    ]
    builder = InlineKeyboardBuilder()
    for button in buttons:
        builder.row(button)

    builder.adjust(2)

    await message.answer(documentation, reply_markup=builder.as_markup(), parse_mode='Markdown')
