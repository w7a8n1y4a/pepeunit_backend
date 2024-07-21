from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.configs.bot import dp, bot
from app.configs.db import get_session
from app.configs.gql import get_metrics_service
from app.configs.sub_entities import InfoSubEntity
from app.repositories.enum import CommandNames
from app.schemas.pydantic.shared import Root


@dp.message(Command(CommandNames.INFO.value))
async def info_resolver(message: types.Message):
    root_data = Root()

    db = next(get_session())
    metrics_service = get_metrics_service(
        InfoSubEntity({'db': db, 'jwt_token': str(message.chat.id), 'is_bot_auth': True})
    )
    metrics = metrics_service.get_instance_metrics()
    db.close()

    documentation = (
        f'Текущая версия - {root_data.version}\n'
        '\n'
        '*Метрики*\n'
        f'Число пользователей - {metrics.user_count}'
        '\n'
        f'Число Repo - {metrics.repo_count}'
        '\n'
        f'Число Unit - {metrics.unit_count}'
        '\n'
        f'Число UnitNode - {metrics.unit_node_count}'
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
