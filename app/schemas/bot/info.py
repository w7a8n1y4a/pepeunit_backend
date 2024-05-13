from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.bot import dp, bot
from app.configs.db import get_session
from app.repositories.enum import CommandNames
from app.repositories.permission_repository import PermissionRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.shared import Root
from app.services.access_service import AccessService
from app.services.metrics_service import MetricsService


@dp.message(Command(CommandNames.INFO.value))
async def start_help_resolver(message: types.Message):
    root_data = Root()

    db = next(get_session())
    metrics_service = MetricsService(
        unit_repository=UnitRepository(db),
        repo_repository=RepoRepository(db),
        unit_node_repository=UnitNodeRepository(db),
        user_repository=UserRepository(db),
        access_service=AccessService(
            permission_repository=PermissionRepository(db),
            unit_repository=UnitRepository(db),
            user_repository=UserRepository(db),
            jwt_token=str(message.chat.id),
            is_bot_auth=True,
        ),
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
