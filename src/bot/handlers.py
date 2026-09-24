"""Telegram message and command handlers with idempotency protection and document dispatch."""

import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

try:
    from telegram import Update
    from telegram.constants import ParseMode
    from telegram.ext import ContextTypes
except ImportError:
    Update = Any  # type: ignore
    ParseMode = type("ParseMode", (), {"HTML": "HTML", "MARKDOWN": "Markdown"})()  # type: ignore
    ContextTypes = type("ContextTypes", (), {"DEFAULT_TYPE": Any})()  # type: ignore

from src.agent.loop import AgentLoop
from src.database.db import get_db_connection, transaction

logger = logging.getLogger(__name__)

# Shared agent instance
agent_loop = AgentLoop()


def _format_telegram_html(text: str) -> str:
    """Ensure clean HTML rendering with zero raw asterisks on screen."""
    if not text:
        return ""
    # Convert `code` to <code>code</code>
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Convert **bold** to <b>bold</b>
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    # Convert *bold* to <b>bold</b>
    text = re.sub(r"\*([^*]+)\*", r"<b>\1</b>", text)
    # Convert _italic_ to <i>italic</i>
    text = re.sub(r"_([^_]+)_", r"<i>\1</i>", text)
    # Strip any remaining stray single or double asterisks
    text = text.replace("**", "").replace("*", "")
    return text


def is_update_processed(update_id: int) -> bool:
    """
    HARD PART 5: Idempotency check.
    Checks whether this Telegram update_id was already processed.
    If not, records it in the database immediately.
    """
    conn = get_db_connection()
    with transaction(conn):
        cursor = conn.cursor()
        cursor.execute("SELECT update_id FROM processed_updates WHERE update_id = ?;", (str(update_id),))
        row = cursor.fetchone()
        if row:
            return True
        cursor.execute("INSERT INTO processed_updates (update_id) VALUES (?);", (str(update_id),))
        return False


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.effective_message:
        return

    welcome_text = (
        "🏪 <b>Welcome to Supermarket Ops Agent</b>\n"
        "────────────────────────\n"
        "Run your entire Indian kirana store directly from this chat window.\n\n"
        "<b>Quick Examples :-</b>\n"
        "• <i>50 packets of Maggi came in, cost ₹12, MRP ₹14</i>\n"
        "• <i>make a bill :- 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, UPI</i>\n"
        "• <i>drop the sugar, make it 6 Maggi</i>\n"
        "• <i>how much sugar is left?</i>\n"
        "• <i>what's running out?</i>\n"
        "• <i>put ₹500 on Ramesh's credit</i>\n"
        "• <i>Ramesh's balance?</i>\n"
        "• <i>today's sales? / close the day</i>\n"
        "• <i>send me that bill as a PDF</i>\n"
        "• <i>make this week's sales analysis deck</i>\n"
        "• <i>default atta = Aashirvaad 5kg</i>\n\n"
        "────────────────────────\n"
        "Type <code>/new</code> at any time to clear the conversation window while preserving all store records."
    )
    await update.effective_message.reply_text(_format_telegram_html(welcome_text), parse_mode=ParseMode.HTML)


async def new_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command: clears dialog context without wiping store preferences or data."""
    if not update.effective_message or not update.effective_chat:
        return

    chat_id = str(update.effective_chat.id)
    response = agent_loop.run_turn(chat_id, "/new")
    await update.effective_message.reply_text(_format_telegram_html(response.text), parse_mode=ParseMode.HTML)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Main message dispatcher.
    Guarantees idempotency against Telegram redeliveries,
    runs the agent ReAct loop, and dispatches text + file artifacts.
    """
    if not update.effective_message or not update.effective_message.text or not update.effective_chat:
        return

    update_id = update.update_id
    chat_id = str(update.effective_chat.id)
    user_text = update.effective_message.text.strip()

    # Idempotency guard: prevent duplicate executions on network retries
    if is_update_processed(update_id):
        logger.warning(f"Duplicate Telegram update {update_id} received and discarded.")
        return

    try:
        # Run agent loop turn
        agent_response = agent_loop.run_turn(session_id=chat_id, user_message=user_text)

        # 1. Send textual response formatted in clean HTML without raw asterisks
        html_text = _format_telegram_html(agent_response.text)
        try:
            await update.effective_message.reply_text(
                html_text,
                parse_mode=ParseMode.HTML
            )
        except Exception as parse_err:
            logger.warning(f"HTML send failed ({parse_err}), falling back to plain text.")
            await update.effective_message.reply_text(agent_response.text)

        # 2. Dispatch any generated file artifacts (PDF invoice, PPTX analysis deck)
        for artifact_path_str in agent_response.artifacts:
            path = Path(artifact_path_str)
            if path.exists():
                caption = f"📄 {path.name}"
                with open(path, "rb") as doc_file:
                    try:
                        await context.bot.send_document(
                            chat_id=update.effective_chat.id,
                            document=doc_file,
                            caption=caption
                        )
                    except Exception as doc_err:
                        logger.warning(f"send_document with caption failed ({doc_err}), sending without caption")
                        with open(path, "rb") as retry_file:
                            await context.bot.send_document(
                                chat_id=update.effective_chat.id,
                                document=retry_file
                            )
            else:
                logger.error(f"Generated artifact path not found on disk: {path}")

    except Exception as e:
        logger.exception("Error processing message in Telegram handler")
        await update.effective_message.reply_text(
            f"⚠️ An error occurred while processing your request: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
