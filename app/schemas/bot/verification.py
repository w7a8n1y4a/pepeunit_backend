from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from fastapi import HTTPException

from app import settings
from app.configs.bot import dp
from app.configs.db import get_session
from app.configs.gql import get_user_service
from app.configs.sub_entities import InfoSubEntity
from app.repositories.enum import CommandNames


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

    user_service = get_user_service(InfoSubEntity({'db': db, 'jwt_token': None}))

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
