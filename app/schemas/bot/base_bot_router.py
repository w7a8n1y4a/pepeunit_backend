from abc import ABC, abstractmethod
from typing import Optional

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup
from fastapi import Query
from pydantic import BaseModel, field_validator

from app import settings
from app.dto.enum import (
    EntityNames,
    LogLevel,
    RepositoryRegistryType,
    UnitNodeTypeEnum,
    VisibilityLevel,
)


class DashboardStates(StatesGroup):
    waiting_for_search = State()


class RepositoryRegistryStates(StatesGroup):
    waiting_for_search = State()


class RepoStates(StatesGroup):
    waiting_for_search = State()


class UnitStates(StatesGroup):
    waiting_for_search = State()


class UnitNodeStates(StatesGroup):
    waiting_for_search = State()


class BaseBotFilters(BaseModel):
    page: int = 1
    visibility_levels: list[str] = Query(
        [item.value for item in VisibilityLevel]
    )
    unit_types: list[str] = Query([item.value for item in UnitNodeTypeEnum])
    log_levels: list[str] = Query([item.value for item in LogLevel])
    repository_types: list[str] = Query(
        [item.value for item in RepositoryRegistryType]
    )
    is_only_my_entity: bool = False
    search_string: str | None = None
    previous_filters: Optional["BaseBotFilters"] = None
    repo_uuid: str | None = None
    unit_uuid: str | None = None

    @field_validator("previous_filters")
    def validate_previous_filters(cls, v):
        if v is not None and v.previous_filters is not None:
            v.previous_filters = None
        return v

    class Config:
        arbitrary_types_allowed = True


class BaseBotRouter(ABC):
    def __init__(
        self, entity_name: EntityNames, states_group: type[StatesGroup]
    ):
        self.router = Router()
        self.entity_name: EntityNames = entity_name
        self.states_group = states_group
        self._register_default_handlers()

    @abstractmethod
    async def show_entities(
        self,
        message: types.Message | types.CallbackQuery,
        filters: BaseBotFilters,
    ):
        pass

    @abstractmethod
    async def get_entities_page(
        self, filters, chat_id: str
    ) -> tuple[list, int]:
        pass

    @abstractmethod
    def build_entities_keyboard(
        self, entities: list, filters: BaseBotFilters, total_pages: int
    ) -> InlineKeyboardMarkup:
        pass

    @abstractmethod
    async def handle_entity_click(
        self, callback: types.CallbackQuery, state: FSMContext
    ) -> None:
        pass

    @abstractmethod
    async def handle_entity_decrees(
        self, callback: types.CallbackQuery
    ) -> None:
        pass

    async def handle_back(
        self, callback: types.CallbackQuery, state: FSMContext
    ):
        data = await state.get_data()
        filters: BaseBotFilters = (
            BaseBotFilters(**data.get("current_filters"))
            if data.get("current_filters")
            else BaseBotFilters()
        )

        if filters.previous_filters:
            await state.update_data(current_filters=filters.previous_filters)
            await self.show_entities(callback, filters.previous_filters)
        else:
            await self.show_entities(callback, BaseBotFilters())

    def _register_default_handlers(self):
        self.router.callback_query(F.data == "noop")(self.handle_noop)
        self.router.callback_query(
            F.data.in_(
                [
                    f"{self.entity_name}_prev_page",
                    f"{self.entity_name}_next_page",
                ]
            )
        )(self.handle_pagination)
        self.router.callback_query(F.data == f"{self.entity_name}_back")(
            self.handle_back
        )
        self.router.callback_query(F.data == f"{self.entity_name}_search")(
            self.handle_search
        )
        self.router.callback_query(
            F.data.startswith(f"{self.entity_name}_toggle_")
        )(self.toggle_filter)
        self.router.callback_query(
            F.data.startswith(f"{self.entity_name}_uuid_")
        )(self.handle_entity_click)
        self.router.callback_query(
            F.data.startswith(f"{self.entity_name}_decres_")
        )(self.handle_entity_decrees)
        if self.states_group in (
            RepositoryRegistryStates,
            RepoStates,
            UnitStates,
            UnitNodeStates,
            DashboardStates,
        ):
            self.router.message(self.states_group.waiting_for_search)(
                self.process_search
            )

    @staticmethod
    async def handle_noop(callback: types.CallbackQuery):
        await callback.answer(parse_mode="Markdown")

    async def handle_pagination(
        self, callback: types.CallbackQuery, state: FSMContext
    ):
        data = await state.get_data()
        filters: BaseBotFilters = (
            BaseBotFilters(**data.get("current_filters"))
            if data.get("current_filters")
            else BaseBotFilters()
        )

        if (
            callback.data == f"{self.entity_name}_prev_page"
            and filters.page > 1
        ):
            filters.page -= 1

        elif callback.data == f"{self.entity_name}_next_page":
            filters.page += 1

        await state.update_data(current_filters=filters)
        await self.show_entities(callback, filters)

    async def handle_search(
        self, callback: types.CallbackQuery, state: FSMContext
    ):
        if self.states_group in (
            RepositoryRegistryStates,
            RepoStates,
            UnitStates,
            UnitNodeStates,
            DashboardStates,
        ):
            await callback.message.edit_text(
                "Please enter search query:", parse_mode="Markdown"
            )
            await state.set_state(self.states_group.waiting_for_search)
        else:
            await callback.message.edit_text(
                "Command not available for this entity", parse_mode="Markdown"
            )

    async def toggle_filter(
        self, callback: types.CallbackQuery, state: FSMContext
    ):
        data = await state.get_data()
        filters: BaseBotFilters = (
            BaseBotFilters(**data.get("current_filters"))
            if data.get("current_filters")
            else BaseBotFilters()
        )

        entity, *_, target = callback.data.split("_")

        if target == "mine":
            filters.is_only_my_entity = not filters.is_only_my_entity
        elif entity != EntityNames.REGISTRY.value and target in [
            item.value for item in VisibilityLevel
        ]:
            if target in filters.visibility_levels:
                filters.visibility_levels.remove(target)
            else:
                filters.visibility_levels.append(target)

        elif target in [item.value for item in UnitNodeTypeEnum]:
            if target in filters.unit_types:
                filters.unit_types.remove(target)
            else:
                filters.unit_types.append(target)

        elif target in [item.value for item in LogLevel]:
            if target in filters.log_levels:
                filters.log_levels.remove(target)
            else:
                filters.log_levels.append(target)

        elif target in [item.value for item in RepositoryRegistryType]:
            if target in filters.repository_types:
                filters.repository_types.remove(target)
            else:
                filters.repository_types.append(target)

        await state.update_data(current_filters=filters)
        await self.show_entities(callback, filters)

    async def process_search(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        current_filters = (
            BaseBotFilters(**data.get("current_filters"))
            if data.get("current_filters")
            else BaseBotFilters()
        )
        if self.entity_name == EntityNames.UNIT_NODE.value:
            filters = BaseBotFilters(
                search_string=message.text,
                unit_uuid=current_filters.unit_uuid,
                previous_filters=current_filters,
            )
        else:
            filters = BaseBotFilters(
                search_string=message.text, previous_filters=current_filters
            )
        await state.update_data(current_filters=filters)
        await state.set_state(None)
        await self.show_entities(message, filters)

    @staticmethod
    def header_name_limit(data: str) -> str:
        return data[: settings.telegram_header_entity_length]

    @staticmethod
    def registry_name_limit(data: str, coefficient: float = 1) -> str:
        return data[
            -int(settings.telegram_header_entity_length * coefficient) :
        ]

    @staticmethod
    def registry_url_small(data: str) -> str:
        return data.replace(
            "https://" if data.find("https://") == 0 else "http://", ""
        )[:-4]

    @staticmethod
    def registry_type_to_bool(
        data: list[RepositoryRegistryType],
    ) -> bool | None:
        result = None
        if (
            RepositoryRegistryType.PUBLIC.value in data
            and RepositoryRegistryType.PRIVATE.value not in data
        ):
            result = True
        if (
            RepositoryRegistryType.PRIVATE.value in data
            and RepositoryRegistryType.PUBLIC.value not in data
        ):
            result = False
        return result

    @staticmethod
    def git_hash_limit(data: str) -> str:
        return data[: settings.telegram_git_hash_length]

    @staticmethod
    async def telegram_response(
        message: types.Message | types.CallbackQuery,
        text: str = None,
        keyboard: InlineKeyboardMarkup = None,
        is_editable: bool = True,
    ):
        import asyncio
        import logging

        params = {
            "text": text,
            "reply_markup": keyboard,
            "parse_mode": "Markdown",
        }

        try:
            if isinstance(message, types.Message):
                await message.answer(**params)
                return

            if isinstance(message, types.CallbackQuery) and is_editable:
                await message.message.edit_text(**params)
            else:
                await message.message.answer(**params)
        except (RuntimeError, asyncio.CancelledError) as e:
            if "Event loop is closed" in str(e) or isinstance(
                e, asyncio.CancelledError
            ):
                logging.warning(
                    f"Telegram bot operation cancelled or event loop closed: {e}"
                )
                return
            raise
        except Exception as e:
            logging.error(f"Error in telegram_response: {e}")
            raise
