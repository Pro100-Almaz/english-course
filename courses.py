import os
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram import types as aio_types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from telethon import TelegramClient, functions
from telethon import types as tele_types
from dotenv import load_dotenv
import db

# --- Load environment variables from .env ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# --- Configuration ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CURATOR_CHAT_ID = int(os.getenv("CURATOR_CHAT_ID", 0))
DB_PATH = os.path.join(BASE_DIR, 'courses.db')
API_ID = os.getenv("APP-API-ID")
API_HASH = os.getenv("APP-API-HASH")
bot_username = "devstage_chatbot"

class ChannelCreateState(StatesGroup):
    waiting_for_discription = State()

class PostStates(StatesGroup):
    choosing_course = State()
    waiting_for_content = State()

class CourseRequestForm(StatesGroup):
    waiting_for_course_request = State()

class ButtonStates(StatesGroup):
    main_page = State()
    courses_page = State()



async def courses_handler(query: aio_types.CallbackQuery, state: FSMContext):
    courses = db.load_courses_url()
    kb = [[InlineKeyboardButton(text=c, callback_data=f"course:{c}")] for c in courses]
    kb.append([InlineKeyboardButton(text="Назад", callback_data="back")])
    await query.message.edit_text(
        "Выберите курс:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.clear()
    await state.set_state(ButtonStates.main_page)
    await query.answer()

async def course_selection_handler(query: aio_types.CallbackQuery, state: FSMContext):
    course = query.data.split(':', 1)[1]
    user_id = query.from_user.id
    courses = db.load_courses_url()

    kb = [
        [InlineKeyboardButton(text= f"Присоединяйтесь к {course}", url= courses[course])],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
        ]
    await query.message.edit_text(
        text= "Выберите курс который хотите пройти",
        reply_markup= InlineKeyboardMarkup(inline_keyboard=kb))
    await state.clear()
    await state.set_state(ButtonStates.courses_page)
    await query.answer()

async def add_course_handler(message: aio_types.Message, state: FSMContext):
    if db.not_admin(message.from_user.id):
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

async def create_channel_handler(message: aio_types.Message, state: FSMContext):
    data = await state.get_data()
    course_name = data['course_name']
    description = message.text.strip()

    channel_id, channel_link = await create_channel(course_name, description)

    if db.add_course_to_db(course_name, channel_link, str(channel_id)):
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


async def rename_course_handler(message: aio_types.Message):
    if db.not_admin(message.from_user.id):
        return
    args = message.get_args().split(';')
    if len(args) == 2 and db.rename_course_in_db(args[0].strip(), args[1].strip()):
        await message.answer(
            f"Курс '{args[0].strip()}' переименован в '{args[1].strip()}'."
        )
    else:
        await message.answer("Использование: /renamecourse старое;новое")


async def create_post(message: aio_types.Message, state: FSMContext):
    if db.not_admin(message.from_user.id):
        return
    courses = db.load_courses_id()

    keyboard = [[InlineKeyboardButton(text=course, callback_data=f"course_id:{courses[course]}")] for course in courses]

    await message.answer(
        "📚 Select the course channel to post into:",
        reply_markup= InlineKeyboardMarkup(inline_keyboard= keyboard)
    )

    await state.set_state(PostStates.choosing_course)

async def course_choice_handler(callback: aio_types.CallbackQuery, state: FSMContext):
     _, channel_id = callback.data.split(':', 1)

     await callback.message.answer(
         "✍️ Great! Now send me the message (text/photo/video/etc.) you want to post."
     )
     await state.clear()
     await state.set_state(PostStates.waiting_for_content)
     await state.update_data(target_channel_id= int(channel_id))

async def post_content_handler(message: aio_types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    channel_id = data['target_channel_id']

    await bot.copy_message(
        chat_id= channel_id,
        from_chat_id= message.chat.id,
        message_id= message.message_id
    )

    await message.answer("✅ Your post has been published!")
    await state.clear()
