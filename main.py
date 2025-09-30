import asyncio
import logging
import sys
from os import getenv
from datetime import datetime, timedelta
import sqlite3

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

# Инициализация бота и диспетчера
bot = Bot(token='8443997188:AAG4NphJAlYCRrgELAmq-WsL4xmyoQBYBMM', default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== КЛАССЫ ДЛЯ БРОНИРОВАНИЯ СТИРКИ ====================

class LaundryDB:
    def __init__(self, db_path='laundry.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных для стирки"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Удаляем старые таблицы если они есть
        cursor.execute('DROP TABLE IF EXISTS laundry_schedule')
        cursor.execute('DROP TABLE IF EXISTS laundry_booking_history')
        
        # Таблица с расписанием на текущую неделю
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS laundry_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                day_name TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                is_available BOOLEAN DEFAULT TRUE,
                user_id INTEGER,
                username TEXT,
                booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица для истории бронирований
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS laundry_booking_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                date TEXT,
                day_name TEXT,
                time_slot TEXT,
                booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Создаем расписание если его нет
        self.generate_weekly_schedule()
            
        conn.commit()
        conn.close()
    
    def generate_weekly_schedule(self):
        """Генерирует расписание на текущую неделю"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Очищаем текущее расписание
        cursor.execute('DELETE FROM laundry_schedule')
        
        # Находим ближайшее воскресенье (начало недели)
        today = datetime.now()
        days_until_sunday = (6 - today.weekday()) % 7
        start_date = today + timedelta(days=days_until_sunday)
        
        # Временные слоты (35 минутные интервалы как в вашем коде)
        time_slots = [
            '08:00-08:35', '08:35-09:10', '09:10-09:45', '09:45-10:20', '10:20-10:55',
            '10:55-11:30', '11:30-12:05', '12:05-12:40', '12:40-13:15', '13:15-13:50',
            '13:50-14:25', '14:25-15:00', '15:00-15:35', '15:35-16:10', '16:10-16:45',
            '16:45-17:20', '17:20-17:55', '17:55-18:30', '18:30-19:05', '19:05-19:40'
        ]
        
        # Генерируем расписание на 7 дней
        schedule_data = []
        for day in range(7):
            current_date = start_date + timedelta(days=day)
            date_str = current_date.strftime('%Y-%m-%d')
            day_name = self.get_day_name(current_date.weekday())
            
            for time_slot in time_slots:
                schedule_data.append((date_str, day_name, time_slot, True, None, None))
        
        # Вставляем данные в базу
        cursor.executemany('''
            INSERT INTO laundry_schedule (date, day_name, time_slot, is_available, user_id, username)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', schedule_data)
        
        conn.commit()
        conn.close()
        logging.info(f"Сгенерировано новое расписание с {start_date.strftime('%Y-%m-%d')}")
    
    def get_day_name(self, weekday):
        """Получить название дня недели"""
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        return days[weekday]
    
    def get_available_slots(self, day_name=None):
        """Получить доступные слоты"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if day_name:
            cursor.execute('''
                SELECT date, day_name, time_slot FROM laundry_schedule 
                WHERE is_available = TRUE AND day_name = ?
                ORDER BY date, time_slot
            ''', (day_name,))
        else:
            cursor.execute('''
                SELECT date, day_name, time_slot FROM laundry_schedule 
                WHERE is_available = TRUE
                ORDER BY date, time_slot
            ''')
        
        slots = cursor.fetchall()
        conn.close()
        return slots
    
    def book_slot(self, date, day_name, time_slot, user_id, username):
        """Забронировать слот"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Проверяем доступность
            cursor.execute('''
                SELECT is_available FROM laundry_schedule 
                WHERE date = ? AND time_slot = ?
            ''', (date, time_slot))
            
            result = cursor.fetchone()
            if not result or not result[0]:
                return False
            
            # Бронируем
            cursor.execute('''
                UPDATE laundry_schedule 
                SET is_available = FALSE, user_id = ?, username = ?
                WHERE date = ? AND time_slot = ?
            ''', (user_id, username, date, time_slot))
            
            # Сохраняем в историю (теперь с day_name)
            cursor.execute('''
                INSERT INTO laundry_booking_history (user_id, username, date, day_name, time_slot)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, date, day_name, time_slot))
            
            conn.commit()
            return True
            
        except Exception as e:
            logging.error(f"Ошибка бронирования: {e}")
            return False
        finally:
            conn.close()
    
    def cancel_booking(self, date, time_slot, user_id):
        """Отменить бронирование"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE laundry_schedule 
                SET is_available = TRUE, user_id = NULL, username = NULL
                WHERE date = ? AND time_slot = ? AND user_id = ?
            ''', (date, time_slot, user_id))
            
            conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            logging.error(f"Ошибка отмены брони: {e}")
            return False
        finally:
            conn.close()
            
    def get_user_bookings(self, user_id):
        """Получить брони пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT date, time_slot FROM schedule 
            WHERE user_id = ?
            ORDER BY date, time_slot
        ''', (user_id,))
        
        bookings = cursor.fetchall()
        conn.close()
        return bookings

class ScheduleUpdater:
    def __init__(self, db: LaundryDB, bot: Bot):
        self.db = db
        self.bot = bot
    
    async def start_scheduler(self):
        """Запуск планировщика для обновления расписания"""
        while True:
            now = datetime.now()
            
            # Проверяем, воскресенье ли и 8 утра
            if now.weekday() == 6 and now.hour == 8 and now.minute == 0:
                await self.update_schedule()
                # Ждем 61 минуту чтобы не сработать повторно
                await asyncio.sleep(61)
            else:
                # Проверяем каждую минуту
                await asyncio.sleep(60)
    
    async def update_schedule(self):
        """Обновление расписания и уведомление пользователей"""
        try:
            # Получаем текущие брони перед обновлением
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT user_id FROM laundry_schedule WHERE user_id IS NOT NULL')
            users = [user[0] for user in cursor.fetchall()]
            conn.close()
            
            # Генерируем новое расписание
            self.db.generate_weekly_schedule()
            
            # Уведомляем пользователей
            for user_id in users:
                try:
                    await self.bot.send_message(
                        user_id,
                        "📅 Расписание стирки обновлено на новую неделю! "
                        "Можете забронировать новые слоты."
                    )
                except Exception as e:
                    logging.error(f"Не удалось уведомить пользователя {user_id}: {e}")
            
            logging.info("Расписание стирки успешно обновлено")
            
        except Exception as e:
            logging.error(f"Ошибка при обновлении расписания: {e}")

# ==================== ВАШ СУЩЕСТВУЮЩИЙ КОД ====================

# Инициализация базы данных для стирки
laundry_db = LaundryDB()

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

async def show_main_menu(message: Message):
    """Показать главное меню"""
    builder = ReplyKeyboardBuilder()
    builder.add(
        types.KeyboardButton(text="📅 Расписание стирки"),
        types.KeyboardButton(text="🕒 Мои брони"),
        types.KeyboardButton(text="❓ Помощь")
    )
    builder.adjust(2)
    
    await message.answer(
        "🏠 Главное меню бронирования стирки:\n\n"
        "Выберите действие:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

async def show_days_keyboard(message: Message, state: FSMContext):
    """Показать клавиатуру с днями недели"""
    builder = InlineKeyboardBuilder()
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    
    for day in days:
        # Проверяем есть ли доступные слоты для этого дня
        available_slots = laundry_db.get_available_slots(day)
        if available_slots:
            builder.button(text=f"✅ {day}", callback_data=f"day_{day}")
        else:
            builder.button(text=f"❌ {day} (нет слотов)", callback_data=f"day_{day}")
    
    builder.button(text='⬅️ Назад', callback_data='back_to_menu')
    builder.adjust(1)
    
    await message.answer('📅 Выберите день недели для бронирования:', reply_markup=builder.as_markup())
    await state.set_state(Schedule.day)

async def show_user_bookings(message: Message):
    """Показать брони пользователя"""
    user_bookings = laundry_db.get_user_bookings(message.from_user.id)
    
    if not user_bookings:
        await message.answer("❌ У вас нет активных бронирований.")
        return
    
    response = "🕒 Ваши активные брони:\n\n"
    for date, day_name, time_slot in user_bookings:
        response += f"📅 {day_name} ({date})\n"
        response += f"⏰ {time_slot}\n"
        response += f"❌ /cancel_{date.replace('-', '')}_{time_slot.replace(':', '').replace('-', '')}\n\n"
    
    await message.answer(response)

@dp.message(Command('start'))
async def cmd_start(message: types.Message, state: FSMContext):
    is_autorised = get_user(message.from_user.id)
    if is_autorised is True:
        await show_main_menu(message)
    else:
        kb = [
            [types.KeyboardButton(text="С правилами ознакомлен")]
        ]
        keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer(
            f"Привет, {message.from_user.full_name}!\n\n"
            f"Это бот для занятия очереди на стирку факультета ИИР\n\n"
            f"Перед началом работы с ботом ознакомься с правилами пользования прачечной\n\n"
            f"***СПИСОК НЕВЕРОТЯНО ВАЖНЫХ ПРАВИЛ!",
            reply_markup=keyboard
        )

@dp.message(F.text.lower() == 'с правилами ознакомлен')
async def registration(message: Message, state: FSMContext):
    is_autorised = get_user(message.from_user.id)
    if is_autorised is False:
        await message.answer('Теперь нужно зарегистрироваться в системе:\n\nНапишите ваше имя:', reply_markup=ReplyKeyboardRemove())
        await state.set_state(Form.name)

@dp.message(F.text == "📅 Расписание стирки")
async def show_schedule_menu(message: Message, state: FSMContext):
    await show_days_keyboard(message, state)

@dp.message(F.text == "🕒 Мои брони")
async def show_my_bookings(message: Message):
    await show_user_bookings(message)

@dp.message(F.text == "❓ Помощь")
async def show_help(message: Message):
    help_text = """
📖 **Помощь по боту бронирования стирки:**

📅 *Расписание стирки* - Посмотреть доступные слоты и забронировать
🕒 *Мои брони* - Посмотреть ваши активные бронирования

⏰ **Расписание обновляется каждое воскресенье в 8:00**

❌ Чтобы отменить бронирование, используйте команду отмены из списка ваших броней

📞 Для связи с администратором: @ваш_админ
    """
    await message.answer(help_text)

@dp.message(F.text.startswith("/cancel_"))
async def cancel_booking_command(message: Message):
    """Обработчик команды отмены бронирования"""
    try:
        # Парсим команду /cancel_YYYYMMDD_HHMMHHMM
        parts = message.text.replace("/cancel_", "").split("_")
        if len(parts) != 2:
            await message.answer("❌ Неверный формат команды отмены.")
            return
        
        date_str = parts[0]
        time_str = parts[1]
        
        # Восстанавливаем формат даты и времени
        date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        time_slot = f"{time_str[:2]}:{time_str[2:4]}-{time_str[4:6]}:{time_str[6:8]}"
        
        # Отменяем бронирование
        success = laundry_db.cancel_booking(date, time_slot, message.from_user.id)
        
        if success:
            await message.answer("✅ Бронирование успешно отменено!")
        else:
            await message.answer("❌ Не удалось отменить бронирование. Возможно, оно уже отменено или не существует.")
            
    except Exception as e:
        logging.error(f"Ошибка при отмене брони: {e}")
        await message.answer("❌ Произошла ошибка при отмене бронирования.")

@dp.callback_query(F.data.startswith("day_"))
async def appointment_day(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора дня"""
    day_name = callback.data.replace("day_", "")
    await state.update_data(day=day_name)
    
    # Получаем доступные слоты для выбранного дня
    available_slots = laundry_db.get_available_slots(day_name)
    
    if not available_slots:
        await callback.message.edit_text(
            f"❌ На {day_name} нет доступных слотов для бронирования.",
            reply_markup=InlineKeyboardBuilder().button(text='⬅️ Назад', callback_data='back_to_menu').as_markup()
        )
        await callback.answer()
        return
    
    builder = InlineKeyboardBuilder()
    
    for date, day, time_slot in available_slots:
        display_text = f"{time_slot}"
        callback_data = f"time_{date}_{time_slot}"
        builder.button(text=display_text, callback_data=callback_data)
    
    builder.button(text='⬅️ Назад', callback_data='back_to_days')
    builder.adjust(2)
    
    await safe_edit_callback_message(
        callback,
        f"🕒 Выберите время для записи на {day_name}:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(Schedule.time)
    await callback.answer()

@dp.callback_query(Schedule.time, F.data.startswith("time_"))
async def capture_time(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора времени"""
    data = await state.get_data()
    day_name = data.get('day', 'неизвестный день')
    
    # Парсим callback_data: time_YYYY-MM-DD_HH:MM-HH:MM
    parts = callback.data.replace("time_", "").split("_")
    date = parts[0]
    time_slot = parts[1]
    
    # Получаем информацию о пользователе
    with connect_to_bd() as con:
        cursor = con.cursor()
        user_info = cursor.execute("SELECT user_name, user_secondname FROM users WHERE user_id=?", (callback.from_user.id,)).fetchone()
    
    if user_info:
        user_name = f"{user_info[0]} {user_info[1]}"
    else:
        user_name = callback.from_user.full_name
    
    # Сохраняем данные для подтверждения
    await state.update_data(
        date=date,
        time_slot=time_slot,
        user_name=user_name
    )
    
    buttons = [
        [InlineKeyboardButton(text='✅ Подтвердить запись', callback_data='confirm_yes')],
        [InlineKeyboardButton(text='❌ Отменить', callback_data='confirm_no')]
    ]
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await safe_edit_callback_message(
        callback,
        f"📋 Детали бронирования:\n\n"
        f"📅 День: {day_name}\n"
        f"🗓️ Дата: {date}\n"
        f"⏰ Время: {time_slot}\n"
        f"👤 Имя: {user_name}\n\n"
        f"Подтвердите запись:",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data == 'confirm_yes')
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    """Подтверждение бронирования"""
    data = await state.get_data()
    
    date = data.get('date')
    day_name = data.get('day')
    time_slot = data.get('time_slot')
    user_name = data.get('user_name')
    
    # Выполняем бронирование
    success = laundry_db.book_slot(date, day_name, time_slot, callback.from_user.id, user_name)
    
    if success:
        await callback.message.edit_text(
            f"✅ Запись подтверждена!\n\n"
            f"📅 {day_name} ({date})\n"
            f"⏰ {time_slot}\n"
            f"👤 {user_name}\n\n"
            f"Хорошей стирки! 🧼",
            reply_markup=None
        )
    else:
        await callback.message.edit_text(
            "❌ Не удалось забронировать выбранный слот. Возможно, он уже занят.",
            reply_markup=None
        )
    
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == 'confirm_no')
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    """Отмена бронирования"""
    await callback.message.edit_text(
        "❌ Бронирование отменено.",
        reply_markup=None
    )
    await show_days_keyboard(callback.message, state)
    await callback.answer()

@dp.callback_query(F.data == 'back_to_days')
async def back_to_days(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору дней"""
    await callback.message.edit_text('Возвращаемся к выбору дня...', reply_markup=None)
    await show_days_keyboard(callback.message, state)
    await callback.answer()

@dp.callback_query(F.data == 'back_to_menu')
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await callback.message.edit_text('Возвращаемся в главное меню...', reply_markup=None)
    await show_main_menu(callback.message)
    await state.clear()
    await callback.answer()

# ==================== ВАШ СУЩЕСТВУЮЩИЙ КОД РЕГИСТРАЦИИ ====================

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
            await show_main_menu(callback.message)
        else:
            new_text = 'Данный пользователь уже зарегистрирован в системе под другим аккаунтом, для разрешения ситуации пишите администратору(тг в описании бота)'
            await safe_edit_callback_message(callback, new_text, reply_markup=None)
            await state.clear()
        await callback.answer()

# ==================== ЗАПУСК ПЛАНИРОВЩИКА И БОТА ====================

async def main() -> None:
    try:
        logging.info("Запуск бота...")
        
        # Запускаем планировщик обновления расписания в фоне
        updater = ScheduleUpdater(laundry_db, bot)
        asyncio.create_task(updater.start_scheduler())
        
        logging.info("Бот и планировщик запущены")
        await dp.start_polling(bot)
        
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
        
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    
    # Явный запуск с обработкой исключений
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")