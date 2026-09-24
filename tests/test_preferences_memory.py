"""Test Hard Part 9: Memory Across Sessions.
Standing preferences persist across chats.
Starting a /new chat clears conversation context but retains stored preferences.
"""

import unittest
from src.agent.session import session_manager
from src.database.seed import seed_database
from src.skills.preference_skill import get_store_preferences, set_store_preference


class TestPreferencesMemory(unittest.TestCase):

    def setUp(self):
        seed_database(reset=True)
        self.session_id = "test_memory_session"

    def test_preferences_persist_across_new_chat(self):
        """Preferences configured before /new must persist after /new."""
        # 1. Set standing preferences
        set_store_preference("default_atta", "Aashirvaad Atta 5kg")
        set_store_preference("default_payment_mode", "UPI")

        # Add message history
        session_manager.add_user_message(self.session_id, "hello")
        session_manager.add_assistant_message(self.session_id, "hi")
        self.assertEqual(len(session_manager.get_history(self.session_id)), 2)

        # 2. Trigger /new chat reset
        reset_res = session_manager.reset_session(self.session_id)
        self.assertEqual(reset_res["status"], "cleared")

        # 3. Conversation history is now empty
        self.assertEqual(len(session_manager.get_history(self.session_id)), 0)

        # 4. BUT persistent DB memory remains intact!
        prefs = get_store_preferences()["preferences"]
        self.assertEqual(prefs.get("default_atta"), "Aashirvaad Atta 5kg")
        self.assertEqual(prefs.get("default_payment_mode"), "UPI")


if __name__ == "__main__":
    unittest.main()
