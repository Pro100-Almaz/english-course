import os
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram import types as aio_types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

CURATOR_CHAT_ID = int(os.getenv("CURATOR_CHAT_ID", 0))


class SupportForm(StatesGroup):
    message = State()


async def support_entry(message: aio_types.Message, state: FSMContext):
    await message.answer("Напишите свое сообщение техподдержке:")
    await state.set_state(SupportForm.message)

async def support_message_handler(message: aio_types.Message, state: FSMContext, bot: Bot):
    await bot.forward_message(
        chat_id=CURATOR_CHAT_ID,
        from_chat_id=message.from_user.id,
        message_id=message.message_id
    )
    await message.answer("Ваше сообщение отправлено, наш куратор скоро ответит.")
    await state.clear()
