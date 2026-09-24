"""Test Hard Part 7: Khata (Credit Ledger) and Guardrails.
Customers buy on credit and settle later.
Guardrail: Don't settle a khata that doesn't exist — confirm or refuse.
"""

import unittest
from src.database.seed import seed_database
from src.skills.khata_skill import add_credit_entry, get_khata_balance, record_khata_payment


class TestKhataLedger(unittest.TestCase):

    def setUp(self):
        seed_database(reset=True)

    def test_khata_credit_and_repayment_cycle(self):
        """Put ₹500 on Ramesh's credit -> check balance -> Ramesh paid ₹300 -> check balance."""
        # 1. Put ₹500 on credit
        res1 = add_credit_entry("Ramesh", 500.0)
        self.assertEqual(res1["status"], "success")
        self.assertEqual(res1["current_balance"], 500.0)

        # 2. Check balance
        bal1 = get_khata_balance("Ramesh")
        self.assertEqual(bal1["balance"], 500.0)

        # 3. Ramesh pays ₹300
        res2 = record_khata_payment("Ramesh", 300.0)
        self.assertEqual(res2["status"], "success")
        self.assertEqual(res2["current_balance"], 200.0)

        # 4. Check updated balance
        bal2 = get_khata_balance("Ramesh")
        self.assertEqual(bal2["balance"], 200.0)
        self.assertEqual(len(bal2["recent_transactions"]), 2)

    def test_guardrail_refuse_settling_non_existent_khata(self):
        """Attempting to settle debt for a customer who does not exist must be refused."""
        res = record_khata_payment("NonExistentCustomer123", 500.0)
        self.assertEqual(res["status"], "error")
        self.assertIn("does not exist", res["message"])


if __name__ == "__main__":
    unittest.main()
