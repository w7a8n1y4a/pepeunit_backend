from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.bot import dp, bot
from app.repositories.enum import CommandNames
from app.schemas.pydantic.shared import Root


@dp.message(Command(CommandNames.INFO.value))
async def start_help_resolver(message: types.Message):
    root_data = Root()

    documentation = (
        f'Текущая версия - {root_data.version}\n'
        '\n'
        '*Метрики*\n'
        f'Число пользователей'
        '\n'
        f'Число Repo - '
        '\n'
        f'Число Unit - '
        '\n'
        f'Число UnitNode - '
    )

    buttons = [
        InlineKeyboardButton(text='Swagger', url=root_data.swagger),
        InlineKeyboardButton(text='Graphql', url=root_data.graphql),
    ]
    builder = InlineKeyboardBuilder()
    for button in buttons:
        builder.row(button)

    builder.adjust(2)

    await message.answer(documentation, reply_markup=builder.as_markup(), parse_mode='Markdown')
