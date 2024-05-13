from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from fastapi import HTTPException

from app import settings
from app.configs.bot import dp
from app.configs.db import get_session
from app.repositories.enum import CommandNames
from app.repositories.permission_repository import PermissionRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.services.access_service import AccessService
from app.services.user_service import UserService


class VerificationState(StatesGroup):
    check_code = State()


@dp.message(StateFilter(None), Command(CommandNames.VERIFICATION.value))
async def verification_user(message, state: FSMContext):

    text = f'Введите код из личного кабинета {settings.backend_domain}'
    await message.answer(text, parse_mode='Markdown')
    await state.set_state(VerificationState.check_code)


@dp.message(VerificationState.check_code)
async def verification_user_check_code(message, state: FSMContext):

    db = next(get_session())

    user_repository = UserRepository(db)

    user_service = UserService(
        user_repository=user_repository,
        access_service=AccessService(
            permission_repository=PermissionRepository(db),
            unit_repository=UnitRepository(db),
            user_repository=user_repository,
        ),
    )

    try:
        await user_service.verification(str(message.chat.id), message.text)
        db.close()

        text = 'Вы успешно прошли верификацию'
    except HTTPException as e:
        if e.status_code == 422:
            text = 'Вы уже верифицированы'
        else:
            text = 'Такого кода не существует'

    await message.answer(text, parse_mode='Markdown')
    await state.clear()
