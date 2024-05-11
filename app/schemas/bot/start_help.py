from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.configs.bot import dp, bot
from app.repositories.enum import CommandNames


@dp.message(Command(CommandNames.START.value, CommandNames.HELP.value))
async def start_help_resolver(message: types.Message):

    documentation = (
        '*Предсказание*\n'
        '/verification - верификация пользователя узла\n'
        '\n'
        '*Управление*\n'
        '/start - запуск бота\n'
    )

    buttons = [
        InlineKeyboardButton(text="Репозиторий разработки", url="https://git.pepemoss.com/universitat/ml/sam_train_backend"),
        InlineKeyboardButton(text="Репозиторий моделей", url="https://git.pepemoss.com/universitat/ml/sam_train"),
        InlineKeyboardButton(text="Open Api", url="https://pepemoss.com/sam_lora_backend/docs"),
        InlineKeyboardButton(text="Graphiql", url="https://pepemoss.com/sam_lora_backend/graphql"),
    ]
    builder = InlineKeyboardBuilder()
    for button in buttons:
        builder.row(button)

    builder.adjust(2)

    await message.answer(documentation, reply_markup=builder.as_markup(), parse_mode='Markdown')
