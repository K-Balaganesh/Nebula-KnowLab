"""Main Telegram bot runner for the Supermarket Operations Agent."""

import logging
import sys
try:
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
except ImportError:
    ApplicationBuilder = None
    CommandHandler = None
    MessageHandler = None
    filters = None

from src.bot.handlers import message_handler, new_chat_handler, start_handler
from src.config import TELEGRAM_BOT_TOKEN
from src.database.seed import seed_database

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def run_telegram_bot() -> None:
    """Initialize DB and run the Telegram bot polling loop."""
    # Ensure database is initialized with catalog and seed data
    logger.info("Initializing database and verifying Indian grocery catalog...")
    seed_database(reset=False)

    token = TELEGRAM_BOT_TOKEN.strip()
    if not token or token == "your_telegram_bot_token_here":
        logger.error(
            "ERROR: TELEGRAM_BOT_TOKEN is not configured in .env or environment.\n"
            "Please create a bot with @BotFather on Telegram, paste your token in .env,\n"
            "or test using the interactive CLI simulator: 'python cli_runner.py'."
        )
        sys.exit(1)

    if ApplicationBuilder is None:
        logger.error(
            "ERROR: 'python-telegram-bot' is not installed.\n"
            "Please install it using: pip install python-telegram-bot\n"
            "You can test the agent locally using: python cli_runner.py"
        )
        sys.exit(1)

    logger.info("Starting Supermarket Ops Agent Telegram bot...")
    app = ApplicationBuilder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", start_handler))
    app.add_handler(CommandHandler("new", new_chat_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

    logger.info("Bot is polling. Ready to receive supermarket operations commands.")
    app.run_polling()


if __name__ == "__main__":
    run_telegram_bot()
