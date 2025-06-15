from courses import *
import db

class PaymentState(StatesGroup):
    awaiting_payment = State()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'courses.db')


async def start(message: aio_types.Message, state: FSMContext):
    user_id = message.from_user.id
    print(user_id)
    if db.record_payment(user_id):
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
        kb = [
            [InlineKeyboardButton(text="Bank card", callback_data="bank")],
            [InlineKeyboardButton(text="Kaspi", callback_data="kaspi")]
        ]
        await message.answer(
            text="Пожалуйста совершите оплату: \n Выберите способ оплаты",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
        await state.set_state(PaymentState.awaiting_payment)

async def handle_random_message(message: aio_types.Message, state: FSMContext):
    db.save_new_user(message.from_user)
    if message.forward_from_chat is not None:
        print(message.forward_from_chat.id)
    await message.answer("Пожалуйста, напишите /start для начала работы.")
    await state.set_state(CourseRequestForm.waiting_for_course_request)
