import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher, html, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

import sqlite3

con = sqlite3.connect('schedule.bd')
con.cursor()    
# Bot token can be obtained via https://t.me/BotFather
TOKEN = getenv("8443997188:AAG4NphJAlYCRrgELAmq-WsL4xmyoQBYBMM")

dp = Dispatcher()

kb = [
        [types.KeyboardButton(text="Ознакомиться с правилами")],
        [types.KeyboardButton(text="С правилами ознакомлен")]
    ]


@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(f"Привет, {message.from_user.full_name}!\n\nЭто бот для занятия очереди на стирку факультета ИИР\n\nПеред началом работы с ботом ознакомься с правилами пользования прачечной", reply_markup=keyboard)
    

@dp.message(F.text.lower() == 'ознакомиться с правилами')
async def pravila(message: Message):
    await message.answer(
        'НЕЛЬЗЯ ПИХАТЬ ХУЙ В СТИРАЛКУ!',
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    builder = ReplyKeyboardBuilder()
    builder.add(
        types.KeyboardButton(text='С правилами ознакомлен')
    )
    
    await message.answer(
        "Нажмите кнопку для согласия:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


@dp.message()
async def echo_handler(message: Message) -> None:
    try:
        # Send a copy of the received message
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        # But not all the types is supported to be copied so need to handle it
        await message.answer("Nice try!")


async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token='8443997188:AAG4NphJAlYCRrgELAmq-WsL4xmyoQBYBMM', default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # And the run events dispatching
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())