"""Preference skill: Persistent memory stored in database surviving /new chats and restarts."""

from typing import Any, Dict
from src.database.db import get_db_connection, transaction


def set_store_preference(key: str, value: str) -> Dict[str, Any]:
    """
    Store or update a persistent shopkeeper preference.
    Examples:
      - key='default_payment', value='UPI'
      - key='default_atta', value='Aashirvaad Atta 5kg'
      - key='store_name', value='Sri Lakshmi Supermarket'
      - key='store_gstin', value='29ABCDE1234F1Z5'
    """
    clean_key = key.strip().lower().replace(" ", "_")
    clean_val = value.strip()

    conn = get_db_connection()
    with transaction(conn):
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO store_preferences (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                updated_at=CURRENT_TIMESTAMP;
            """,
            (clean_key, clean_val)
        )

    return {
        "status": "success",
        "message": f"Saved preference: '{clean_key}' = '{clean_val}'. This will be remembered across /new chats.",
        "key": clean_key,
        "value": clean_val
    }


def get_store_preferences() -> Dict[str, Any]:
    """
    Retrieve all current persistent store preferences from the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM store_preferences;")
    rows = cursor.fetchall()
    prefs = {r["key"]: r["value"] for r in rows}
    return {
        "status": "success",
        "preferences": prefs
    }
