import logging
from telegram import InlineKeyboardMarkup, Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, filters, MessageHandler, CallbackQueryHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a message with three inline buttons attached."""
    keyboard = [
        [
            InlineKeyboardButton("Option 1", callback_data="1"),
            InlineKeyboardButton("Option 2", callback_data="2"),
        ],
        [InlineKeyboardButton("Option 3", callback_data="3")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Please choose:", reply_markup=reply_markup)
    
    
async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(update.message.text)    
    
    

if __name__ == '__main__':
    application = ApplicationBuilder().token('8443997188:AAG4NphJAlYCRrgELAmq-WsL4xmyoQBYBMM').build()
    
    start_handler = CommandHandler('start', start)
    hello_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, hello)
    application.add_handler(start_handler)
    application.add_handler(hello_handler)
    
    application.run_polling()