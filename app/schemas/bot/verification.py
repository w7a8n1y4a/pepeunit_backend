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
from app.repositories.user_repository import UserRepository


class VerificationState(StatesGroup):
    check_code = State()


@dp.message(StateFilter(None), Command(CommandNames.VERIFICATION))
async def verification_user(message, state: FSMContext):

    db = next(get_session())

    user_repository = UserRepository(db)
    user = user_repository.get_user_by_telegram_id(str(message.chat.id))

    text = f'Your account is already linked to an account on instance {settings.backend_domain}'
    if user:
        await message.answer(text, parse_mode='Markdown')
        return

    db.close()

    text = f'Enter the code from your personal account on instance {settings.backend_domain}'
    await message.answer(text, parse_mode='Markdown')
    await state.set_state(VerificationState.check_code)


@dp.message(VerificationState.check_code)
async def verification_user_check_code(message, state: FSMContext):

    db = next(get_session())

    user_service = get_user_service(InfoSubEntity({'db': db, 'jwt_token': None}))

    try:
        await user_service.verification(str(message.chat.id), message.text)
        db.close()

        text = 'You have been successfully verified'
    except HTTPException as e:
        if e.status_code == 422:
            text = 'You are already verified'
        else:
            text = 'There is no such code'

    await message.answer(text, parse_mode='Markdown')
    await state.clear()
