import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.db import get_session
from app.configs.gql import get_metrics_service
from app.configs.sub_entities import InfoSubEntity
from app.dto.enum import CommandNames
from app.schemas.bot.utils import make_monospace_table_with_title
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

    table = [['Type', 'Count']]

    metrics_dict = {
        'User': metrics.user_count,
        'Repo': metrics.repo_count,
        'Unit': metrics.unit_count,
        'UnitNode': metrics.unit_node_count,
        'UnitNodeEdge': metrics.unit_node_edge_count,
    }

    for k, v in metrics_dict.items():
        table.append([k, v])

    text = f'\n```text' '\n' f'Backend Version - {root_data.version}\n\n'
    text += make_monospace_table_with_title(table, 'Instance Stats')
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
