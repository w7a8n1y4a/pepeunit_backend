from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import settings
from app.configs.clickhouse import get_hand_clickhouse_client
from app.configs.db import get_hand_session
from app.configs.errors import CustomException
from app.configs.rest import (
    get_bot_instance_service,
    get_bot_repo_service,
    get_bot_repository_registry_service,
)
from app.dto.enum import (
    AgentType,
    CommandNames,
    DecreesNames,
    EntityNames,
    UserRole,
)
from app.schemas.bot.base_bot_router import (
    BaseBotFilters,
    BaseBotRouter,
    ControlStates,
)


class ControlBotRouter(BaseBotRouter):
    def __init__(self):
        entity_name = EntityNames.CONTROL.value
        super().__init__(entity_name=entity_name, states_group=ControlStates)
        self.router.message(Command(CommandNames.CONTROL.value))(
            self.control_resolver
        )

    async def control_resolver(
        self, message: types.Message, state: FSMContext
    ):
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
        with get_hand_session() as db:
            get_bot_instance_service(
                db, str(chat_id)
            ).access_service.authorization.check_access(
                [AgentType.USER],
                [UserRole.ADMIN],
            )

        keyboard = self.build_entities_keyboard([], filters, 0)
        await self.telegram_response(message, "*Control*", keyboard)

    async def get_entities_page(
        self, _filters: BaseBotFilters, _chat_id: str
    ) -> tuple[list, int]:
        return [], 0

    def build_entities_keyboard(
        self,
        _entities: list,
        _filters: BaseBotFilters,
        _total_pages: int,
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        actions = [
            (DecreesNames.INTEGRATION_TESTS, "Integration Tests"),
        ]
        if settings.pu_ff_federation_enable:
            actions.append((DecreesNames.SCAN_ALL, "Scan All Instances"))
        actions.extend(
            [
                (DecreesNames.UPDATE_ALL_REGISTRIES, "Update All Registries"),
                (
                    DecreesNames.UPDATE_ALL_UNITS_FIRMWARE,
                    "Update All Units Firmware",
                ),
            ]
        )
        for decree, label in actions:
            builder.row(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{self.entity_name}_decres_{decree.value}_0",
                )
            )
        return builder.as_markup()

    async def handle_entity_click(
        self, callback: types.CallbackQuery, _state: FSMContext
    ) -> None:
        await callback.answer()

    async def handle_entity_decrees(
        self, callback: types.CallbackQuery
    ) -> None:
        *_, decrees_type, _target = callback.data.split("_")
        chat_id = str(callback.from_user.id)
        text = ""

        try:
            with get_hand_session() as db, get_hand_clickhouse_client() as cc:
                match decrees_type:
                    case DecreesNames.INTEGRATION_TESTS:
                        get_bot_instance_service(
                            db, chat_id
                        ).start_integration_tests()
                        text = "Started Integration Tests"
                    case DecreesNames.SCAN_ALL:
                        get_bot_instance_service(db, chat_id).scan_all()
                        text = "Started Scan All Instances"
                    case DecreesNames.UPDATE_ALL_REGISTRIES:
                        get_bot_repository_registry_service(
                            db, chat_id
                        ).schedule_update_all()
                        text = "Started Update All Registries"
                    case DecreesNames.UPDATE_ALL_UNITS_FIRMWARE:
                        get_bot_repo_service(
                            db, cc, chat_id
                        ).schedule_bulk_update_units_firmware()
                        text = "Started Update All Units Firmware"
        except CustomException as e:
            text = e.message

        await callback.answer(parse_mode="Markdown")
        await self.telegram_response(callback, text, is_editable=False)
