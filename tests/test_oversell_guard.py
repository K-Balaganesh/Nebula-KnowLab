"""Test Hard Part 2: Oversell Guard.
Stock cannot go negative. Billing 10 when 6 are in stock is refused at the tool layer,
not hoped for in the prompt.
"""

import unittest
from src.database.seed import seed_database
from src.database.db import get_db_connection
from src.skills.billing_skill import add_or_update_cart, clear_active_bill, finalize_bill
from src.skills.inventory_skill import search_inventory


class TestOversellGuard(unittest.TestCase):

    def setUp(self):
        seed_database(reset=True)
        # Set Amul Butter stock to exactly 6 units
        conn = get_db_connection()
        conn.execute("UPDATE products SET stock_quantity = 6 WHERE name LIKE 'Amul Butter%';")

    def tearDown(self):
        clear_active_bill("test_oversell_session")

    def test_tool_layer_refusal_when_requested_exceeds_stock(self):
        """Billing 10 when 6 are in stock must be refused at the tool layer."""
        res = add_or_update_cart(
            session_id="test_oversell_session",
            items=[{"item_name": "Amul Butter 100g", "quantity": 10.0}]
        )
        self.assertEqual(res.get("status"), "error")
        error_msgs = " ".join(res.get("errors", []))
        self.assertIn("Oversell Guard", error_msgs)
        self.assertIn("Only 6.0", error_msgs)

        # Verify stock was untouched
        stock_res = search_inventory("Amul Butter 100g")
        current_stock = stock_res["products"][0]["stock_quantity"]
        self.assertEqual(current_stock, 6.0)

    def test_database_check_constraint_prevents_negative_stock(self):
        """Direct database write below zero must raise SQLite IntegrityError."""
        conn = get_db_connection()
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE products SET stock_quantity = -1 WHERE name LIKE 'Amul Butter%';")


if __name__ == "__main__":
    unittest.main()
