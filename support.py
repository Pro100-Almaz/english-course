import os
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram import types as aio_types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import db
from db import load_support, add_support
from courses import ButtonStates

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'courses.db')

class SupportForm(StatesGroup):
    message = State()


async def support_handler(query: aio_types.CallbackQuery, state: FSMContext):
    message = query.message
    user_id = message.chat.id
    print(user_id)
    if db.not_admin(user_id):
        await support_entry(message, state)
    else:
        kb = [
            [InlineKeyboardButton(text="Добавить поддержку", callback_data="add_support")],
            [InlineKeyboardButton(text="Убрать из поддержки", callback_data="remove_support")],
            [InlineKeyboardButton(text="Список поддержки", callback_data="get_support")],
            [InlineKeyboardButton(text="Назад", callback_data="back")]
        ]
        await message.answer(text="Выберите действие", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        await state.clear()
        await state.set_state(ButtonStates.main_page)
        await query.answer()

async def support_entry(message: aio_types.Message, state: FSMContext):
    await message.answer("Напишите свое сообщение техподдержке:")
    await state.set_state(SupportForm.message)

async def support_message_handler(message: aio_types.Message, state: FSMContext, bot: Bot):
    CURATOR_CHAT_ID = db.load_support()
    await bot.forward_message(
        chat_id=CURATOR_CHAT_ID,
        from_chat_id=message.from_user.id,
        message_id=message.message_id
    )
    await message.answer("Ваше сообщение отправлено, наш куратор скоро ответит.")
    await state.clear()

async def add_support(message: aio_types.Message):
    db.add_support(message.chat.id)

    await message.answer(f"user {message.from_user.id} was added to support.")

async def delete_support(message: aio_types.Message):
    db.delete_support(message.chat.id)
    await message.answer(f"user {message.from_user.id} was removed from support.")

async def get_support():
    return db.get_support()

