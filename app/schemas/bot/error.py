import logging

from aiogram import F, Router
from aiogram.types import ErrorEvent, Message
from fastapi import exceptions

error_router = Router()


@error_router.error(F.update.message.as_("message"))
async def handle_my_custom_exception(event: ErrorEvent, message: Message):

    print('test')
    print(event.exception)

    error_text = 'Unknown error'
    if isinstance(event.exception, exceptions.HTTPException):
        error_text = event.exception.detail

    logging.error(error_text)
    await message.answer(error_text)
