from aiogram import types as aio_types
from aiogram.fsm.context import FSMContext


async def start(message: aio_types.Message, state: FSMContext):
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
            text="Пожалуйста совершите оплату: \n Отправьте каспи преревод на номер +7********** и отправьте квитанцию о переводе",
        )
        await state.set_state(PaymentState.awaiting_payment)