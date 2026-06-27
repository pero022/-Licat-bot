import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

logging.basicConfig(level=logging.INFO)

TOKEN = "8824201157:AAHq-pj1agxPN9TIDL90RaEZYGbfr_WYrcc"

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        username = f"@{member.username}" if member.username else member.first_name
        await update.message.reply_text(f"👋 Welcome {username}!")
    await update.message.delete()

async def remove_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.delete()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, remove_left))

app.run_polling()
