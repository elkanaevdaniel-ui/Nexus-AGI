import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = "8760269302:AAEGQQFUJcn6r6nj8uDQ3KHJaZFuGR9cQ0w"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        f"✅ Your Telegram Chat ID is:\n"
        f"<code>{chat_id}</code>\n\n"
        f"Copy this number and send it back to Agent Zero!",
        parse_mode='HTML'
    )
    print(f"\n✅ CHAT ID FOUND: {chat_id}\n")

async def any_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    print(f"\n✅ CHAT ID: {chat_id}\n")
    await update.message.reply_text(f"Your Chat ID: {chat_id}")

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.ALL, any_message))
print("Bot started! Send any message to your bot on Telegram to get your Chat ID...")
print("Press Ctrl+C to stop")
app.run_polling()
