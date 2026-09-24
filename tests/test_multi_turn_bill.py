"""Test Hard Part 4: Multi-turn Bills.
A bill builds over several messages, supports mid-build edits,
and only decrements stock on finalize.
"""

import unittest
from src.database.seed import seed_database
from src.skills.billing_skill import (
    add_or_update_cart,
    edit_draft_cart,
    finalize_bill,
    get_active_bill,
    clear_active_bill
)
from src.skills.inventory_skill import search_inventory


class TestMultiTurnBills(unittest.TestCase):

    def setUp(self):
        seed_database(reset=True)
        self.session_id = "test_multi_turn_session"

    def tearDown(self):
        clear_active_bill(self.session_id)

    def test_multi_turn_drafting_and_atomic_finalization(self):
        """Verify step-by-step cart editing and deferred stock decrement."""
        # 1. Check initial stocks
        init_maggi = search_inventory("Maggi 70g")["products"][0]["stock_quantity"]
        init_butter = search_inventory("Amul Butter 100g")["products"][0]["stock_quantity"]
        init_sugar = search_inventory("Sugar (loose)")["products"][0]["stock_quantity"]

        # Step 1: Create initial draft cart: 2kg sugar, 4 Maggi, 1 Amul butter
        cart_step1 = add_or_update_cart(
            session_id=self.session_id,
            items=[
                {"item_name": "Sugar (loose)", "quantity": 2.0},
                {"item_name": "Maggi 70g", "quantity": 4.0},
                {"item_name": "Amul Butter 100g", "quantity": 1.0}
            ],
            payment_mode="UPI"
        )
        self.assertEqual(cart_step1["status"], "success")
        self.assertEqual(len(cart_step1["items"]), 3)

        # CRITICAL CHECK: Inventory must NOT be decremented during draft build!
        maggi_during_draft = search_inventory("Maggi 70g")["products"][0]["stock_quantity"]
        self.assertEqual(maggi_during_draft, init_maggi)

        # Step 2: Mid-build edit -> "drop the butter, make it 6 Maggi"
        cart_step2 = edit_draft_cart(
            session_id=self.session_id,
            remove_items=["Amul Butter"],
            set_quantities={"Maggi": 6.0}
        )
        self.assertEqual(cart_step2["status"], "success")
        # Cart should now have 2 items: Sugar and Maggi (butter removed)
        item_names = [i["product_name"] for i in cart_step2["items"]]
        self.assertNotIn("Amul Butter 100g", item_names)
        maggi_item = next(i for i in cart_step2["items"] if "Maggi" in i["product_name"])
        self.assertEqual(maggi_item["quantity"], 6.0)

        # Step 3: Finalize bill
        final_res = finalize_bill(session_id=self.session_id, payment_mode="UPI", generate_pdf=False)
        self.assertEqual(final_res["status"], "success")
        self.assertTrue(final_res["bill_number"].startswith("BILL-"))

        # Step 4: Verify stock decremented ONLY AFTER finalization
        final_maggi = search_inventory("Maggi 70g")["products"][0]["stock_quantity"]
        final_butter = search_inventory("Amul Butter 100g")["products"][0]["stock_quantity"]
        final_sugar = search_inventory("Sugar (loose)")["products"][0]["stock_quantity"]

        self.assertEqual(final_maggi, init_maggi - 6.0)
        self.assertEqual(final_butter, init_butter)  # Butter was dropped, stock unchanged!
        self.assertEqual(final_sugar, init_sugar - 2.0)

        # Draft bill should now be empty
        active_cart = get_active_bill(self.session_id)
        self.assertEqual(active_cart["status"], "empty")


if __name__ == "__main__":
    unittest.main()
