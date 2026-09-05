import contextlib
from uuid import UUID

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.db import get_hand_session
from app.configs.rest import get_bot_operation_task_service
from app.domain.operation_task_model import OperationTask
from app.dto.enum import (
    CommandNames,
    EntityNames,
    OperationTaskStatus,
    OperationTaskType,
)
from app.schemas.bot.base_bot_router import BaseBotFilters, BaseBotRouter
from app.schemas.bot.utils import (
    format_datetime,
    make_monospace_table_with_title,
)
from app.schemas.pydantic.operation_task import OperationTaskFilter


class OperationTaskStates(StatesGroup):
    pass


class OperationTaskBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.OPERATION_TASK.value
        super().__init__(
            entity_name=entity_name, states_group=OperationTaskStates
        )
        self.router.message(Command(CommandNames.TASKS.value))(
            self.tasks_resolver
        )

    async def tasks_resolver(self, message: types.Message, state: FSMContext):
        await state.set_state(None)
        filters = BaseBotFilters()
        await state.update_data(current_filters=filters)
        await self.show_entities(message, filters)

    async def show_entities(
        self,
        message: types.Message | types.CallbackQuery,
        filters: BaseBotFilters,
    ):
        chat_id = (
            message.chat.id
            if isinstance(message, types.Message)
            else message.from_user.id
        )
        entities, total_pages = await self.get_entities_page(
            filters, str(chat_id)
        )
        keyboard = self.build_entities_keyboard(entities, filters, total_pages)
        await self.telegram_response(message, "*Tasks*", keyboard)

    async def get_entities_page(
        self, filters: BaseBotFilters, chat_id: str
    ) -> tuple[list, int]:
        with get_hand_session() as db:
            operation_task_service = get_bot_operation_task_service(
                db, chat_id
            )
            count, tasks = operation_task_service.list(
                OperationTaskFilter(
                    offset=(filters.page - 1)
                    * settings.pu_telegram_items_per_page,
                    limit=settings.pu_telegram_items_per_page,
                    status=filters.operation_task_statuses,
                    task_type=filters.operation_task_types,
                )
            )
            total_pages = (
                count + settings.pu_telegram_items_per_page - 1
            ) // settings.pu_telegram_items_per_page
        return tasks, total_pages

    def build_entities_keyboard(
        self, entities: list, filters: BaseBotFilters, total_pages: int
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        status_buttons = [
            InlineKeyboardButton(
                text=(
                    "🟢 "
                    if item.value in filters.operation_task_statuses
                    else "🔴️ "
                )
                + item.value,
                callback_data=f"{self.entity_name}_toggle_" + item.value,
            )
            for item in OperationTaskStatus
        ]
        builder.row(*status_buttons)

        type_buttons = [
            InlineKeyboardButton(
                text=(
                    "🟢 "
                    if item.value in filters.operation_task_types
                    else "🔴️ "
                )
                + item.value,
                callback_data=f"{self.entity_name}_toggle_" + item.value,
            )
            for item in OperationTaskType
        ]
        builder.row(*type_buttons[:4])
        builder.row(*type_buttons[4:])

        if entities:
            for task in entities:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{task.status} - {task.task_type}",
                        callback_data=f"{self.entity_name}_uuid_{task.uuid}_{filters.page}",
                    )
                )
        else:
            builder.row(
                InlineKeyboardButton(text="No Data", callback_data="noop")
            )

        if total_pages > 1:
            pagination_row = []
            if filters.page > 1:
                pagination_row.append(
                    InlineKeyboardButton(
                        text="⬅️",
                        callback_data=f"{self.entity_name}_prev_page",
                    )
                )
            pagination_row.append(
                InlineKeyboardButton(
                    text=f"{filters.page}/{total_pages}",
                    callback_data="noop",
                )
            )
            if filters.page < total_pages:
                pagination_row.append(
                    InlineKeyboardButton(
                        text="➡️",
                        callback_data=f"{self.entity_name}_next_page",
                    )
                )
            builder.row(*pagination_row)

        return builder.as_markup()

    async def handle_entity_click(
        self, callback: types.CallbackQuery, state: FSMContext
    ) -> None:
        data = await state.get_data()
        filters: BaseBotFilters = (
            BaseBotFilters(**data.get("current_filters"))
            if data.get("current_filters")
            else BaseBotFilters()
        )

        task_uuid = UUID(callback.data.split("_")[-2])
        current_page = int(callback.data.split("_")[-1])

        if not filters.previous_filters:
            filters.page = current_page
            new_filters = BaseBotFilters(previous_filters=filters)
            await state.update_data(current_filters=new_filters)

        with get_hand_session() as db:
            operation_task_service = get_bot_operation_task_service(
                db, str(callback.from_user.id)
            )
            task = operation_task_service.get(task_uuid)

        text = f"*Task* - `{task.task_type}`"
        text += "\n```text\n"
        text += make_monospace_table_with_title(
            self._get_base_info_table(task),
            "Base Info",
            lengths=[15, 30],
        )
        text += "```"

        keyboard = [
            [
                InlineKeyboardButton(
                    text="← Back", callback_data=f"{self.entity_name}_back"
                ),
                InlineKeyboardButton(
                    text="↻ Refresh",
                    callback_data=f"{self.entity_name}_uuid_{task.uuid}_{filters.page}",
                ),
            ],
        ]

        await callback.answer(parse_mode="Markdown")
        with contextlib.suppress(TelegramBadRequest):
            await self.telegram_response(
                callback, text, InlineKeyboardMarkup(inline_keyboard=keyboard)
            )

    async def handle_entity_decrees(
        self, callback: types.CallbackQuery
    ) -> None:
        await callback.answer()

    @staticmethod
    def _get_base_info_table(task: OperationTask) -> list[list]:
        table = [
            ["Type", task.task_type],
            ["Status", task.status],
            ["Started", format_datetime(task.start_datetime)],
            ["Finished", format_datetime(task.finish_datetime)],
        ]

        if task.result:
            table.append(["Result", " ".join(task.result.split())])

        return table
