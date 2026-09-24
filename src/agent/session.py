"""Session and conversation memory manager for multi-turn chat sessions."""

from typing import Any, Dict, List, Optional
from src.skills.preference_skill import get_store_preferences


class SessionManager:
    """Manages chat message history per session and handles /new chat resets."""

    def __init__(self):
        # In-memory ephemeral conversation histories mapped by session_id
        self._sessions: Dict[str, List[Dict[str, Any]]] = {}

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a given session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return self._sessions[session_id]

    def add_user_message(self, session_id: str, content: str) -> None:
        """Append user message to session history."""
        hist = self.get_history(session_id)
        hist.append({"role": "user", "content": content})

    def add_assistant_message(self, session_id: str, content: str) -> None:
        """Append assistant response to session history."""
        hist = self.get_history(session_id)
        hist.append({"role": "assistant", "content": content})

    def reset_session(self, session_id: str) -> Dict[str, Any]:
        """
        Execute /new command.
        Clears conversation history for the session, while leaving persistent DB data intact!
        (Hard Part 9: Standing preferences, inventory, and khata survive across /new).
        """
        self._sessions[session_id] = []
        prefs = get_store_preferences().get("preferences", {})
        return {
            "status": "cleared",
            "message": "Conversation context cleared. Persistent store memory & preferences retained.",
            "active_preferences": prefs
        }

    def get_active_preferences(self) -> Dict[str, str]:
        """Fetch current DB store preferences."""
        res = get_store_preferences()
        return res.get("preferences", {})


# Global session manager instance
session_manager = SessionManager()
