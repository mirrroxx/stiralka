import asyncio
import logging
import sys
from os import getenv
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, html, types, F, fsm, Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import State, StatesGroup
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder, InlineKeyboardMarkup
from aiogram.utils.chat_action import ChatActionSender
from contextlib import contextmanager

# Правильный импорт для исключений в aiogram 3.x
from aiogram.exceptions import TelegramBadRequest

import sqlite3
from aiogram.fsm.storage.redis import RedisStorage

bot = Bot(token='8443997188:AAG4NphJAlYCRrgELAmq-WsL4xmyoQBYBMM', default=DefaultBotProperties(parse_mode=ParseMode.HTML))

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class Form(StatesGroup):
    name = State()
    surname = State()
    
    
class Schedule(StatesGroup):
    day = State()
    time = State()

            
async def safe_edit_message(message: types.Message, new_text: str, reply_markup=None, parse_mode=None):
    """Безопасно редактирует сообщение, обрабатывая ошибку 'message not modified'"""
    try:
        await message.edit_text(new_text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.info("Message wasn't modified (no changes detected)")
        else:
            raise e


async def safe_edit_callback_message(callback: CallbackQuery, new_text: str, reply_markup=None, parse_mode=None):
    """Безопасно редактирует сообщение из callback query"""
    try:
        await callback.message.edit_text(new_text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.info("Message wasn't modified (no changes detected)")
        else:
            raise e


@contextmanager
def connect_to_bd():
    con = None
    try:
        con = sqlite3.connect('students.db')
        yield con
    except sqlite3.Error as e:
        print(f'Ошибка подключения к бд: {e}')
        raise
    finally:
        if con:
            con.close()
    
    
def get_user(user_id):
    with connect_to_bd() as con:
        cursor = con.cursor()
        user_info = cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    if user_info:
        if user_info[-1] == 1:
            return True
    return False


def add_user(user_id, user_name, user_secondname, user_room, is_autorised):
    with connect_to_bd() as con:
        cursor = con.cursor()
        cursor.execute("INSERT INTO users (user_id, user_name, user_secondname, user_room, is_autorised) VALUES (?, ?, ?, ?, ?)", (user_id, user_name, user_secondname, user_room, is_autorised))
        con.commit()
        
        
class Rent:
    def __init__(self, user_id):
        self.user_id = user_id
        
    def check_zapis(self, date, time):
        with connect_to_bd() as con:
            cursor = con.cursor()
            zapis = cursor.execute("SELECT * FROM schedule WHERE data=? AND time=?", (date, time)).fetchone()
            return zapis
    
    def take_time(self, date, time):
        with connect_to_bd() as con:
            cursor = con.cursor()
            proverka = self.check_zapis(date, time)
            if proverka == None:
                cursor.execute("INSERT INTO schedule (user_id, data, time) VALUES (?, ?, ?)", (self.user_id, date, time))
                con.commit()


async def show_days_keyboard(message: Message, state: FSMContext):
    today = datetime.now().weekday()
    pass
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text='Понедельник', callback_data='Понедельник'),
        types.InlineKeyboardButton(text='Вторник', callback_data='Вторник'),
        types.InlineKeyboardButton(text='Четверг', callback_data='Четверг'),
        types.InlineKeyboardButton(text='Пятница', callback_data='Пятница'),
        types.InlineKeyboardButton(text='Суббота', callback_data='Суббота'),
        types.InlineKeyboardButton(text='Воскресенье', callback_data='Воскресенье'),
        width=1
    )
    await message.answer('Выберите день недели для бронирования: ', reply_markup=builder.as_markup())
    await state.set_state(Schedule.day)
    

@dp.message(Command('start'))
async def cmd_start(message: types.Message, state: FSMContext):
    is_autorised = get_user(message.from_user.id)
    if is_autorised is True:
        await show_days_keyboard(message, state)
    else:
        kb = [
            [types.KeyboardButton(text="С правилами ознакомлен")]
        ]
        keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer(f"Привет, {message.from_user.full_name}!\n\nЭто бот для занятия очереди на стирку факультета ИИР\n\nПеред началом работы с ботом ознакомься с правилами пользования прачечной\n\n***СПИСОК НЕВЕРОТЯНО ВАЖЫНХ ПРАВИЛ!", reply_markup=keyboard)

    
@dp.message(F.text.lower() == 'с правилами ознакомлен')
async def registration(message: Message, state: FSMContext):
    is_autorised = get_user(message.from_user.id)
    if is_autorised is False:
        await message.answer('Теперь нужно зарегистрироваться в системе:\n\nНапишите ваше имя:', reply_markup=ReplyKeyboardRemove())
        await state.set_state(Form.name)
    

@dp.message(F.text, Form.name)
async def capture_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(f"Отлично, {message.text}, теперь укажите свою фамилию: ")
    await state.set_state(Form.surname)
    
    
@dp.message(F.text, Form.surname)
async def capture_surname(message: Message, state: FSMContext):
    kb = [
        [types.InlineKeyboardButton(text='✅Все верно', callback_data='correct')],
        [types.InlineKeyboardButton(text='❌Заполнить сначала', callback_data='incorrect')]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=kb)
    data = await state.get_data()
    await state.update_data(surname=message.text)
    await message.answer(f"Вас зовут {data['name']} {message.text}, верно?", reply_markup=keyboard)


@dp.callback_query(F.data == 'incorrect')
async def incorrect(callback: CallbackQuery, state: FSMContext):
    is_autorised = get_user(callback.from_user.id)
    if is_autorised is False:
        await state.clear()
        new_text = 'Давайте попробуем еще!\n\nНапишите ваше имя: '
        await safe_edit_callback_message(callback, new_text, reply_markup=None)
        await state.set_state(Form.name)
        await callback.answer()
    else:
        await callback.message.answer('Вы уже зарегистрированы!')
        await callback.answer()


@dp.callback_query(F.data == 'correct')
async def correct(callback: CallbackQuery, state: FSMContext):
    with connect_to_bd() as con:
        data = await state.get_data()
        cursor = con.cursor()
        check_user = cursor.execute("SELECT * FROM users WHERE (user_name=? AND user_secondname=?) OR user_id=?", (data['name'], data['surname'], callback.from_user.id)).fetchone()
        if check_user is None:
            add_user(callback.from_user.id, data['name'], data['surname'], None, 1)
            new_text = 'Вы успешно зарегистрировались в боте, теперь вы можете начать им пользоваться!'
            await safe_edit_callback_message(callback, new_text, reply_markup=None)
            await state.clear()
            await show_days_keyboard(callback.message, state)
        else:
            new_text = 'Данный пользователь уже зарегистрирован в системе под другим аккаунтом, для разрешения ситуации пишите администратору(тг в описании бота)'
            await safe_edit_callback_message(callback, new_text, reply_markup=None)
            await state.clear()
        await callback.answer()


@dp.callback_query(Schedule.day)
async def appointment_day(callback: CallbackQuery, state: FSMContext):
    await state.update_data(day=callback.data)
    
    time_slots = [
        ((8, 0), (8, 35)), ((8, 35), (9, 10)), ((9, 10), (9, 45)), 
        ((9, 45), (10, 20)), ((10, 20), (10, 55)), ((10, 55), (11, 30)), 
        ((11, 30), (12, 5)), ((12, 5), (12, 40)), ((12, 40), (13, 15)), 
        ((13, 15), (13, 50)), ((13, 50), (14, 25)), ((14, 25), (15, 0)), 
        ((15, 0), (15, 35)), ((15, 35), (16, 10)), ((16, 10), (16, 45)), 
        ((16, 45), (17, 20)), ((17, 20), (17, 55)), ((17, 55), (18, 30)), 
        ((18, 30), (19, 5)), ((19, 5), (19, 40))
    ]
    time_now = datetime.now().time()
    builder = InlineKeyboardBuilder()
    for start, finish in time_slots: 
        display_text = f"{start[0]}:{start[1]:02d}-{finish[0]}:{finish[1]:02d}"
        callback_data = f"time_{start[0]}:{start[1]:02d}-{finish[0]}:{finish[1]:02d}"
        builder.button(text=display_text, callback_data=callback_data)
    builder.button(text='⬅️ Назад', callback_data='back')
    
    builder.adjust(1)
    
    await safe_edit_callback_message(
        callback,
        f"Выберите время для записи на {callback.data}:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(Schedule.time)
    await callback.answer()
    

@dp.callback_query(Schedule.time, F.data.startswith("time_"))
async def capture_time(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    day = data.get('day', 'неизвестный день')
    
    time_slot = callback.data.replace("time_", "")
    
    time_parts = time_slot.split('-')
    start_time = time_parts[0]
    end_time = time_parts[1]
    
    start_time = start_time.replace(':00', ':0').replace(':0', '') if ':0' in start_time else start_time
    end_time = end_time.replace(':00', ':0').replace(':0', '') if ':0' in end_time else end_time
    
    buttons = [
        [InlineKeyboardButton(text='✅ Да', callback_data='yes')],
        [InlineKeyboardButton(text='❌ Нет', callback_data='no')]
    ]
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await safe_edit_callback_message(
        callback,
        f"⌛ Выбрано время: {start_time}-{end_time}\n"
        f"📅 День: {day}\n\n"
        f"✅ Подтвердите запись ниже 👇",
        reply_markup=None
    )
    
    await callback.message.answer(
        f"🤔 Вы хотите записаться на:\n"
        f"📅 День: {day}\n"
        f"⏰ Время: {start_time}-{end_time}\n\n"
        f"Не забудьте о своей записи!",
        reply_markup=kb
    )
    await state.update_data(time=callback.data)
    await callback.answer()
    
    
@dp.callback_query(F.data=='back')
async def go_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text('Возвращаемся назад...', reply_markup=None)
    await show_days_keyboard(callback.message, state)


@dp.callback_query(F.data.in_(['yes', 'no']))
async def handle_confirm(callback: CallbackQuery, state: FSMContext):
    if callback.data == 'yes':
        data = await state.get_data()
        day = data['day']
        time = data['time'].lstrip('time_')
        zapis = Rent(callback.from_user.id)
        zapis.take_time(date=day, time=time)
        check = zapis.check_zapis(date=day, time=time)
        if check == None:
            await callback.message.edit_text(
                f"✅ Запись подтверждена, хорошей стирки!\n",
                reply_markup=None
            )
            await state.clear()
        else:
            await callback.message.edit_text(
                f"❌ Запись занята\n\nВыберите день заново:",
                reply_markup=None
            )
            await state.clear()
            await show_days_keyboard(callback.message, state)
    else:
        await callback.message.edit_text(
            "❌ Запись отменена\n\nВыберите день заново:",
            reply_markup=None
        )
        await state.clear()
        await show_days_keyboard(callback.message, state)
    
    await callback.answer()


async def main() -> None:
    bot = Bot(token='8443997188:AAG4NphJAlYCRrgELAmq-WsL4xmyoQBYBMM', default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())