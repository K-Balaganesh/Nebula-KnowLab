"""Test Hard Part 5: Idempotency.
Telegram redelivers updates upon network timeouts.
A retried update must not double-bill or double-decrement stock.
"""

import unittest
from src.bot.handlers import is_update_processed
from src.database.seed import seed_database


class TestIdempotency(unittest.TestCase):

    def setUp(self):
        seed_database(reset=True)

    def test_duplicate_update_id_discarded(self):
        """First arrival of update_id processes; duplicate arrival is flagged as already processed."""
        test_update_id = 987654321

        # 1. First reception
        already_seen = is_update_processed(test_update_id)
        self.assertFalse(already_seen, "First attempt should not be flagged as processed.")

        # 2. Telegram retry / redelivery with same update_id
        already_seen_retry = is_update_processed(test_update_id)
        self.assertTrue(already_seen_retry, "Redelivered update must be identified as already processed.")


if __name__ == "__main__":
    unittest.main()
