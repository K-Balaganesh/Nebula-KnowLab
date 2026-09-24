"""Test Hard Part 6: Concurrency.
Two bills — or a sale plus a stock-in — in flight at once must not corrupt stock.
Verifies ACID transaction isolation with SQLite WAL mode.
"""

import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from src.database.seed import seed_database
from src.skills.inventory_skill import search_inventory, stock_in
from src.skills.billing_skill import add_or_update_cart, finalize_bill


class TestConcurrency(unittest.TestCase):

    def setUp(self):
        seed_database(reset=True)

    def test_concurrent_stock_in_operations(self):
        """Simultaneous stock additions across multiple threads must not lose updates."""
        initial_stock = search_inventory("Maggi 70g")["products"][0]["stock_quantity"]
        num_threads = 8
        add_per_thread = 5.0

        def worker():
            stock_in("Maggi 70g", add_per_thread)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final_stock = search_inventory("Maggi 70g")["products"][0]["stock_quantity"]
        expected_stock = initial_stock + (num_threads * add_per_thread)
        self.assertEqual(final_stock, expected_stock)

    def test_concurrent_billing_and_stock_in(self):
        """Simultaneous billing and stock replenishment in flight must maintain stock consistency."""
        initial_stock = search_inventory("Tata Salt 1kg")["products"][0]["stock_quantity"]

        def bill_worker(sid):
            add_or_update_cart(session_id=sid, items=[{"item_name": "Tata Salt 1kg", "quantity": 2.0}])
            finalize_bill(session_id=sid, generate_pdf=False)

        def stock_worker():
            stock_in("Tata Salt 1kg", 10.0)

        t1 = threading.Thread(target=bill_worker, args=("session_conc_1",))
        t2 = threading.Thread(target=stock_worker)
        t3 = threading.Thread(target=bill_worker, args=("session_conc_2",))

        t1.start()
        t2.start()
        t3.start()

        t1.join()
        t2.join()
        t3.join()

        final_stock = search_inventory("Tata Salt 1kg")["products"][0]["stock_quantity"]
        # Initial + 10 - 2 - 2 = Initial + 6
        expected_stock = initial_stock + 10.0 - 4.0
        self.assertEqual(final_stock, expected_stock)


if __name__ == "__main__":
    unittest.main()
