#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN")


async def log_only_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if msg and msg.text:
        print(msg.text, flush=True)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # log EVERYTHING user types (text only)
    app.add_handler(MessageHandler(filters.TEXT, log_only_message))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
