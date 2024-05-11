from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app import settings


storage = MemoryStorage()
bot = Bot(token=settings.telegram_token)
dp = Dispatcher(bot=bot)
