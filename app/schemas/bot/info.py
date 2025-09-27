from aiogram import Router, types
from aiogram.filters import Command

from app.configs.db import get_hand_session
from app.configs.rest import get_bot_metrics_service
from app.dto.enum import CommandNames
from app.schemas.bot.utils import make_monospace_table_with_title

info_router = Router()


@info_router.message(Command(CommandNames.INFO))
async def info_resolver(message: types.Message):
    with get_hand_session() as db:
        metrics_service = get_bot_metrics_service(db, str(message.chat.id))
        metrics = metrics_service.get_instance_metrics()

        table = [["Type", "Count"]]

        metrics_dict = {
            "User": metrics.user_count,
            "RepositoryRegistry": metrics.repository_registry_count,
            "Repo": metrics.repo_count,
            "Unit": metrics.unit_count,
            "UnitNode": metrics.unit_node_count,
            "UnitNodeEdge": metrics.unit_node_edge_count,
        }

        for k, v in metrics_dict.items():
            table.append([k, v])

        text = "\n```text\n"
        text += make_monospace_table_with_title(table, "Instance Stats")
        text += "```"

    await message.answer(text, parse_mode="Markdown")
