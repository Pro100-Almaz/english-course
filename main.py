import os
import sqlite3
import asyncio
import logging
from PyPDF2 import PdfReader

from aiogram import Bot, Dispatcher
from aiogram import types as aio_types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import F
from telethon import TelegramClient, functions
from telethon import types as tele_types
from dotenv import load_dotenv

from check_validator import pdf_images_to_text

# --- Load environment variables from .env ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# --- Configuration ---

DOWNLOAD_DIR = "./downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CURATOR_CHAT_ID = int(os.getenv("CURATOR_CHAT_ID", 0))
DB_PATH = os.path.join(BASE_DIR, 'courses.db')
API_ID = os.getenv("APP-API-ID")
API_HASH = os.getenv("APP-API-HASH")
bot_username = "devstage_chatbot"
# --- States ---
class PaymentState(StatesGroup):
    awaiting_payment = State()

class SupportForm(StatesGroup):
    message = State()

class ChannelCreateState(StatesGroup):
    waiting_for_discription = State()

class PostStates(StatesGroup):
    choosing_course = State()
    waiting_for_content = State()

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
            name TEXT UNIQUE NOT NULL,
            url TEXT UNIQUE NOT NULL,
            channel_id TEXT NOT NULL DEFAULT '-1002519961960'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            "INSERT INTO courses (name, url) VALUES (?, ?)",
            [("Экспресс-грамматика", "https://t.me/+uKg4xGQ0MDtkMTBi"), ("Путешествия", "https://t.me/+umKj0R00Rb9jNzE6")]
        )
    conn.commit()

# --- Helpers ---
def load_courses_url():
    with get_db_connection() as conn:
        return {row["name"]: row["url"] for row in conn.execute("SELECT name, url FROM courses ORDER BY id")}

def load_courses_id():
    with get_db_connection() as conn:
        return {row['name']: row['channel_id'] for row in conn.execute("SELECT name, channel_id FROM courses ORDER BY id")}


# Record payment only if not exists
def record_payment(user_id: int) -> bool:
    with get_db_connection() as conn:
        cur = conn.execute(
            "SELECT 1 FROM payments WHERE user_id = ?",
            (user_id, )
        )
        if cur.fetchone(): return True
        else: return False

def update_record_payment(user_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO payments (user_id) VALUES (?)",
                (user_id, ))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

# Course and support commands

def not_admin(user_id: int) -> bool:
    try:
        with get_db_connection() as conn:
            cur = conn.execute("SELECT * FROM admin WHERE user_id = ?",
                         (user_id,))
            if cur.fetchone():
                return False
            return True
    except sqlite3.IntegrityError:
        return False

def add_course_to_db(name: str, url: str, id: str) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute("INSERT INTO courses (name, url, channel_id) VALUES (?, ?, ?)",
                         (name, url, id))
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

def save_new_user(user: aio_types.User):
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
async def start_handler(message: aio_types.Message, state: FSMContext):
    user_id = message.from_user.id
    print(user_id)
    if record_payment(user_id):
        keyboard = [
            [InlineKeyboardButton(text="Курсы", callback_data="courses")],
            [InlineKeyboardButton(text="Эфиры", callback_data="lives")],
            [InlineKeyboardButton(text="Техподдержка", callback_data="support")]
        ]
        await message.answer(
            "Добро пожаловать! Выберите раздел:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    else:
        await message.answer(
            text= "Пожалуйста совершите оплату: \n Отправьте каспи преревод на номер +7********** и отправьте квитанцию о переводе",
        )
        await state.set_state(PaymentState.awaiting_payment)

@dp.message(PaymentState.awaiting_payment)
async def check_payment(message: aio_types.Message, state: FSMContext):
    doc = message.document

    # 1. Check it’s a PDF
    if doc.mime_type != "application/pdf" and not doc.file_name.lower().endswith(".pdf"):
        return await message.reply("Пожалуйста отправьте файл формата '.pdf'")

    # 2. Download the PDF
    local_path = os.path.join(DOWNLOAD_DIR, doc.file_name)
    file_obj = await bot.get_file(doc.file_id)
    await bot.download_file(
        file_path=file_obj.file_path,
        destination=local_path
    )

    check_text = pdf_images_to_text(local_path)
    metadata = PdfReader(local_path).metadata

    if data_check(check_text, metadata):
        if update_record_payment(message.from_user.id):
            print("Payment record updated succesfully")
            await message.answer(
                text= "Your payment was accepted. \nYou can join our main channel where we post important news and etc.",
                reply_markup= InlineKeyboardMarkup(
                    inline_keyboard= [[InlineKeyboardButton(text="Main Channel", url="https://t.me/+qpdCOmNRNxw5Mjhi")]]
                )
            )
        else:
            print("Payment record was not updated")
    else:
        os.remove(local_path)
        await message.answer(text= "Wrong payment!")
    await state.clear()


def data_check(check_text, metadata):
    # checks if the payment data is valid
    if metadata.author != 'Kaspi.kz':
        return False

    if '860 T' not in check_text or 'Epacpin 1.' not in check_text:
        return False
    return True



@dp.callback_query(lambda c: c.data == "courses")
async def courses_handler(query: aio_types.CallbackQuery):
    courses = load_courses_url()
    kb = [[InlineKeyboardButton(text=c, callback_data=f"course:{c}")] for c in courses]
    await query.message.edit_text(
        "Выберите курс:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await query.answer()

@dp.callback_query(F.data.startswith("course:"))
async def course_selection_handler(query: aio_types.CallbackQuery, state: FSMContext):
    course = query.data.split(':', 1)[1]
    user_id = query.from_user.id
    courses = load_courses_url()

    kb = [[InlineKeyboardButton(text= f"Присоединяйтесь к {course}", url= courses[course])]]
    await query.message.edit_text(
        text= "Выберите курс который хотите пройти",
        reply_markup= InlineKeyboardMarkup(inline_keyboard=kb))
    await query.answer()

@dp.message(Command("support"))
async def support_entry(message: aio_types.Message, state: FSMContext):
    await message.answer("Напишите свое сообщение техподдержке:")
    await state.set_state(SupportForm.message)

@dp.message(SupportForm.message)
async def support_message_handler(message: aio_types.Message, state: FSMContext):
    await bot.forward_message(
        chat_id=CURATOR_CHAT_ID,
        from_chat_id=message.from_user.id,
        message_id=message.message_id
    )
    await message.answer("Ваше сообщение отправлено, наш куратор скоро ответит.")
    await state.clear()

@dp.message(Command("addcourse"))
async def add_course_handler(message: aio_types.Message, state: FSMContext):
    if not_admin(message.from_user.id):
        return
    parts = message.text.split()

    if parts[0].startswith('/addcourse'):
        parts = parts[1:]
    if len(parts) < 1:
        await message.answer("Напишите имя курса \n В формате: /addcourse <название-курса>")
        return

    course_name = "".join(parts)
    await state.update_data(course_name= course_name)
    await message.answer("Напишите описание для канала курса")
    await state.set_state(ChannelCreateState.waiting_for_discription)

@dp.message(ChannelCreateState.waiting_for_discription)
async def create_channel_handler(message: aio_types.Message, state: FSMContext):
    data = await state.get_data()
    course_name = data['course_name']
    description = message.text.strip()

    channel_id, channel_link = await create_channel(course_name, description)

    if add_course_to_db(course_name, channel_link, str(channel_id)):
        await message.reply(f"✅ Курс «{course_name}» добавлен с ссылкой:\n{channel_link} \n ID канала курса {channel_id}")
    else:
        await message.reply("🚫 Такой курс или URL уже есть.")

    await state.clear()

async def create_channel(channel_name: str, channel_discript: str):
    client = TelegramClient(session= 'session', api_id= int(API_ID), api_hash= API_HASH)
    await client.start()


    result_chan = await client(functions.channels.CreateChannelRequest(
        title= channel_name,
        about= channel_discript,
        broadcast=True,  # this makes it a channel, not a group
        megagroup=False  # False → regular channel (private by default)
    ))
    channel = result_chan.chats[0]


    result_grp = await client(functions.channels.CreateChannelRequest(
        title=f'Discussion: {channel_name}',
        about=f'Discussion of posts in {channel_name}',
        broadcast=False,  # False + megagroup=True → supergroup
        megagroup=True
    ))
    discussion = result_grp.chats[0]

    await client(functions.channels.SetDiscussionGroupRequest(
        broadcast=channel,  # the channel you created
        group=discussion  # the supergroup you created
    ))


    bot_entity = await client.get_entity(bot_username)
    await client(functions.channels.EditAdminRequest(
        channel= channel,
        user_id= bot_entity,
        admin_rights=tele_types.ChatAdminRights(
            post_messages=True,
            edit_messages=True,
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            change_info=True,
            pin_messages=True,
            add_admins=True
        ),
        rank="Channel Manager"  # optional label
    ))

    invite = await client(functions.messages.ExportChatInviteRequest(
        peer=channel
    ))
    invite_link = invite.link
    await client.disconnect()
    #
    # print('✅ Channel ID:', channel.id)
    # print('✅ Discussion ID:', discussion.id)
    # print('✅ Invite link:', invite_link)
    return int(f"-100{channel.id}"), invite_link


@dp.message(Command("renamecourse"))
async def rename_course_handler(message: aio_types.Message):
    if not_admin(message.from_user.id):
        return
    args = message.get_args().split(';')
    if len(args) == 2 and rename_course_in_db(args[0].strip(), args[1].strip()):
        await message.answer(
            f"Курс '{args[0].strip()}' переименован в '{args[1].strip()}'."
        )
    else:
        await message.answer("Использование: /renamecourse старое;новое")


@dp.message(Command("addpost"))
async def create_post(message: aio_types.Message, state: FSMContext):
    if not_admin(message.from_user.id):
        return
    courses = load_courses_id()

    keyboard = [[InlineKeyboardButton(text=course, callback_data=f"course_id:{courses[course]}")] for course in courses]

    await message.answer(
        "📚 Select the course channel to post into:",
        reply_markup= InlineKeyboardMarkup(inline_keyboard= keyboard)
    )

    await state.set_state(PostStates.choosing_course)

@dp.callback_query(lambda F: F.data.startswith("course_id:"), PostStates.choosing_course)
async def course_choice_handler(callback: aio_types.CallbackQuery, state: FSMContext):
     _, channel_id = callback.data.split(':', 1)

     await callback.message.answer(
         "✍️ Great! Now send me the message (text/photo/video/etc.) you want to post."
     )
     await state.clear()
     await state.set_state(PostStates.waiting_for_content)
     await state.update_data(target_channel_id= int(channel_id))

@dp.message(PostStates.waiting_for_content)
async def post_content_handler(message: aio_types.Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data['target_channel_id']

    await bot.copy_message(
        chat_id= channel_id,
        from_chat_id= message.chat.id,
        message_id= message.message_id
    )

    await message.answer("✅ Your post has been published!")
    await state.clear()

@dp.message()
async def handle_random_message(message: aio_types.Message, state: FSMContext):
    save_new_user(message.from_user)
    if message.forward_from_chat is not None:
        print(message.forward_from_chat.id)
    await message.answer("Пожалуйста, напишите /start для начала работы.")
    await state.set_state(CourseRequestForm.waiting_for_course_request)

# --- Main ---
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
