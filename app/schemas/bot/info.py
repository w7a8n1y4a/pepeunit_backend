import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.configs.db import get_session
from app.configs.gql import get_metrics_service
from app.configs.sub_entities import InfoSubEntity
from app.dto.enum import CommandNames
from app.schemas.pydantic.shared import Root

info_router = Router()


@info_router.message(Command(CommandNames.INFO))
async def info_resolver(message: types.Message):
    root_data = Root()

    db = next(get_session())

    try:
        metrics_service = get_metrics_service(
            InfoSubEntity({'db': db, 'jwt_token': str(message.chat.id), 'is_bot_auth': True})
        )
        metrics = metrics_service.get_instance_metrics()

    except Exception as e:
        logging.error(e)
    finally:
        db.close()

    documentation = (
        f'Current Version - {root_data.version}\n'
        '\n'
        '*Metrics*\n'
        f'User count - {metrics.user_count}'
        '\n'
        f'Repo count - {metrics.repo_count}'
        '\n'
        f'Unit count - {metrics.unit_count}'
        '\n'
        f'UnitNode count - {metrics.unit_node_count}'
        '\n'
        f'UnitNodeEdge count - {metrics.unit_node_edge_count}'
    )

    buttons = [
        InlineKeyboardButton(text='Swagger', url=root_data.swagger),
        InlineKeyboardButton(text='Graphql', url=root_data.graphql),
        InlineKeyboardButton(text='Grafana', url=root_data.grafana),
    ]
    builder = InlineKeyboardBuilder()
    for button in buttons:
        builder.row(button)

    builder.adjust(2)

    await message.answer(documentation, reply_markup=builder.as_markup(), parse_mode='Markdown')
