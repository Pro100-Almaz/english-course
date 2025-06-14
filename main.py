import os
import asyncio
import logging

from aiogram import F, Bot, Dispatcher, types as aio_types
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.types.message import ContentType
import basic_commands
import support
import payment
import courses
import db
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

# --- Load environment variables from .env ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")


# --- Bot Initialization ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Handlers ---
@dp.message(Command("start"))
async def start_handler(message: aio_types.Message, state: FSMContext):
    return await basic_commands.start(message, state)


@dp.callback_query(lambda c: c.data == "courses")
async def courses_handler(query: aio_types.CallbackQuery):
    return await courses.courses_handler(query)

@dp.callback_query(F.data.startswith("course:"))
async def course_selection_handler(query: aio_types.CallbackQuery, state: FSMContext):
    return await courses.course_selection_handler(query, state)

@dp.message(Command("support"))
async def support_entry(message: aio_types.Message, state: FSMContext):
    return await support.support_entry(message, state)

@dp.message(support.SupportForm.message)
async def support_message_handler(message: aio_types.Message, state: FSMContext):
    return await support.support_message_handler(message, state, bot)

@dp.message(Command("addcourse"))
async def add_course_handler(message: aio_types.Message, state: FSMContext):
    return await courses.add_course_handler(message, state)

@dp.message(courses.ChannelCreateState.waiting_for_discription)
async def create_channel_handler(message: aio_types.Message, state: FSMContext):
    return await courses.create_channel_handler(message, state)

@dp.message(Command("renamecourse"))
async def rename_course_handler(message: aio_types.Message):
    return await courses.rename_course_handler(message)

@dp.message(Command("addpost"))
async def create_post(message: aio_types.Message, state: FSMContext):
    return await courses.create_post(message, state)

@dp.callback_query(lambda F: F.data.startswith("course_id:"), courses.PostStates.choosing_course)
async def course_choice_handler(callback: aio_types.CallbackQuery, state: FSMContext):
     return await courses.course_choice_handler(callback, state)

@dp.message(courses.PostStates.waiting_for_content)
async def post_content_handler(message: aio_types.Message, state: FSMContext):
    return await courses.post_content_handler(message, state, bot)

@dp.message()
async def handle_random_message(message: aio_types.Message, state: FSMContext):
    if message.successful_payment:
        return await payment.successful_payment(message, bot)
    return await basic_commands.handle_random_message(message, state)

# Payments
@dp.callback_query(lambda F: F.data.startswith("bank"), payment.PaymentState.awaiting_payment)
async def payment_handler(query: CallbackQuery, state: FSMContext):
    return await payment.payment_handler(query, bot)

# pre checkout  (must be answered in 10 seconds)
@dp.pre_checkout_query(lambda query: True)
async def pre_checkout_query(pre_checkout_q: aio_types.PreCheckoutQuery):
    return await payment.pre_checkout_query(pre_checkout_q, bot)


# # successful payment
# @dp.message.register(lambda message: message.successful_payment is not None)
# async def successful_payment(message: aio_types.Message):
#     return await payment.successful_payment(message, bot)
#
# @dp.message.register(lambda message: message.content_type == aio_types.ContentType.REFUNDED_PAYMENT)
# async def refund_payment(message: aio_types.Message):
#     return await payment.refund_payment(message, bot)

@dp.callback_query(lambda F: F.data.startswith("kaspi"), payment.PaymentState.awaiting_payment)
async def kaspi_handler(query: CallbackQuery, state: FSMContext):
    await query.message.answer(text="kaspi payment")


# --- Main ---
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())


