import os
import sqlite3
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import F
from dotenv import load_dotenv

# --- Load environment variables from .env ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# --- Configuration ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CURATOR_CHAT_ID = int(os.getenv("CURATOR_CHAT_ID", 0))
DB_PATH = os.path.join(BASE_DIR, 'courses.db')

# --- States ---
class SupportForm(StatesGroup):
    message = State()

class CourseRequestForm(StatesGroup):
    waiting_for_course_request = State()

# --- Database Setup ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

with get_db_connection() as conn:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course TEXT NOT NULL,
            paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, course)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Seed default courses
    cur = conn.execute("SELECT COUNT(*) AS cnt FROM courses")
    if cur.fetchone()["cnt"] == 0:
        conn.executemany(
            "INSERT INTO courses (name) VALUES (?)",
            [("Экспресс-грамматика",), ("Путешествия",)]
        )
    conn.commit()

# --- Helpers ---
def load_courses():
    with get_db_connection() as conn:
        return [row["name"] for row in conn.execute("SELECT name FROM courses ORDER BY id")]

# Record payment only if not exists
def record_payment(user_id: int, course: str) -> bool:
    with get_db_connection() as conn:
        cur = conn.execute(
            "SELECT 1 FROM payments WHERE user_id = ? AND course = ?",
            (user_id, course)
        )
        if cur.fetchone():
            return False
        conn.execute(
            "INSERT INTO payments (user_id, course) VALUES (?, ?)",
            (user_id, course)
        )
        conn.commit()
        return True

# Course and support commands
def add_course_to_db(name: str) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute("INSERT INTO courses (name) VALUES (?)", (name,))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def rename_course_in_db(old: str, new: str) -> bool:
    with get_db_connection() as conn:
        cur = conn.execute(
            "UPDATE courses SET name = ? WHERE name = ?", (new, old)
        )
        conn.commit()
        return cur.rowcount > 0

def save_new_user(user: types.User):
    with get_db_connection() as conn:
        cur = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user.id,))
        if not cur.fetchone():
            conn.execute(
                "INSERT INTO users (user_id, first_name, last_name, username) VALUES (?, ?, ?, ?)",
                (user.id, user.first_name, user.last_name, user.username)
            )
            conn.commit()

# --- Bot Initialization ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Handlers ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    keyboard = [
        [InlineKeyboardButton(text="Курсы", callback_data="courses")],
        [InlineKeyboardButton(text="Эфиры", callback_data="lives")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="support")]
    ]
    await message.answer(
        "Добро пожаловать! Выберите раздел:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.callback_query(lambda c: c.data == "courses")
async def courses_handler(query: types.CallbackQuery):
    courses = load_courses()
    kb = [[InlineKeyboardButton(text=c, callback_data=f"course:{c}")] for c in courses]
    await query.message.edit_text(
        "Выберите курс:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await query.answer()

@dp.callback_query(F.data.startswith("course:"))
async def course_selection_handler(query: types.CallbackQuery):
    course = query.data.split(':', 1)[1]
    user_id = query.from_user.id
    if record_payment(user_id, course):
        text = f"Спасибо, {query.from_user.first_name}! Вы записаны на курс '{course}'."
    else:
        text = f"Вы уже записаны на курс '{course}'."
    await query.message.edit_text(text)
    await query.answer()

@dp.message(Command("support"))
async def support_entry(message: types.Message, state: FSMContext):
    await message.answer("Напишите свое сообщение техподдержке:")
    await state.set_state(SupportForm.message)

@dp.message(SupportForm.message)
async def support_message_handler(message: types.Message, state: FSMContext):
    await bot.forward_message(
        chat_id=CURATOR_CHAT_ID,
        from_chat_id=message.from_user.id,
        message_id=message.message_id
    )
    await message.answer("Ваше сообщение отправлено, наш куратор скоро ответит.")
    await state.clear()

@dp.message(Command("addcourse"))
async def add_course_handler(message: types.Message):
    course = message.get_args().strip()
    if add_course_to_db(course):
        await message.answer(f"Курс '{course}' добавлен.")
    else:
        await message.answer("Неверное имя или курс уже существует.")

@dp.message(Command("renamecourse"))
async def rename_course_handler(message: types.Message):
    args = message.get_args().split(';')
    if len(args) == 2 and rename_course_in_db(args[0].strip(), args[1].strip()):
        await message.answer(
            f"Курс '{args[0].strip()}' переименован в '{args[1].strip()}'."
        )
    else:
        await message.answer("Использование: /renamecourse старое;новое")

@dp.message(CourseRequestForm.waiting_for_course_request)
async def handle_course_request(message: types.Message, state: FSMContext):
    if message.text.lower() == "i want to course":
        await message.answer("Вот ссылка на наш канал: https://t.me/+0Vf5IWnSGn5jMWNi")
    else:
        await message.answer("Пожалуйста, напишите 'I want to course' для получения ссылки на канал.")
    await state.clear()

@dp.message(lambda message: message.text == "start_message")
async def handle_start_message(message: types.Message):
    keyboard = [
        [InlineKeyboardButton(text="Кнопка 1", callback_data="button1")],
        [InlineKeyboardButton(text="Кнопка 2", callback_data="button2")],
        [InlineKeyboardButton(text="Кнопка 3", callback_data="button3")]
    ]
    await message.answer(
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.message()
async def handle_random_message(message: types.Message, state: FSMContext):
    save_new_user(message.from_user)
    await message.answer("Пожалуйста, напишите /start для начала работы.\n\nПосле этого напишите: 'I want to course', чтобы получить ссылку на канал.")
    await state.set_state(CourseRequestForm.waiting_for_course_request)

# --- Main ---
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
