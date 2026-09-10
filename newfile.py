from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8613185271:AAEpzwbiA8ajrN7fg_5MTBF8BJjYpxh5Xk0"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! 👋")

app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.run_polling()
