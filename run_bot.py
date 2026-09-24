"""Main entry point to launch the Supermarket Ops Agent Telegram bot."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.bot.telegram_bot import run_telegram_bot

if __name__ == "__main__":
    run_telegram_bot()
