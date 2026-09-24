"""Test Hard Part 3: GST Correctness.
Per-item slab, intra-state CGST/SGST 50-50 split, paise rounding, and legible tax breakup.
"""

import unittest
from src.utils.gst import calculate_item_gst, summarize_cart_gst


class TestGSTCalculations(unittest.TestCase):

    def test_zero_gst_loose_item(self):
        """0% GST items (e.g. loose sugar, loose rice) have 0 tax and 0 CGST/SGST."""
        res = calculate_item_gst(quantity=2.0, selling_price=44.0, gst_rate=0.00, inclusive=True)
        self.assertEqual(res["taxable_amount"], 88.0)
        self.assertEqual(res["cgst_amount"], 0.0)
        self.assertEqual(res["sgst_amount"], 0.0)
        self.assertEqual(res["total_tax"], 0.0)
        self.assertEqual(res["gross_total"], 88.0)

    def test_intra_state_split_and_rounding(self):
        """Intra-state sales must split tax 50-50 into CGST and SGST with no lost paise."""
        # 1 item of ₹60 with 12% GST inclusive:
        # Taxable = 60 / 1.12 = 53.5714... -> 53.57
        # Total Tax = 60 - 53.57 = 6.43
        # CGST = 3.22, SGST = 3.21 (or split preserving total 6.43)
        res = calculate_item_gst(quantity=1.0, selling_price=60.0, gst_rate=0.12, inclusive=True)
        self.assertEqual(res["gross_total"], 60.0)
        self.assertEqual(res["taxable_amount"], 53.57)
        self.assertEqual(res["total_tax"], 6.43)
        self.assertAlmostEqual(res["cgst_amount"] + res["sgst_amount"], 6.43, places=2)
        self.assertAlmostEqual(res["cgst_rate"], 0.06, places=4)
        self.assertAlmostEqual(res["sgst_rate"], 0.06, places=4)

    def test_multi_item_cart_summary(self):
        """Verify summary across mixed tax slabs (0%, 5%, 12%, 18%)."""
        items = [
            {"name": "Loose Sugar", "quantity": 2.0, "unit_price": 44.0, "gst_rate": 0.00},
            {"name": "Aashirvaad Atta", "quantity": 1.0, "unit_price": 275.0, "gst_rate": 0.05},
            {"name": "Maggi 70g", "quantity": 4.0, "unit_price": 14.0, "gst_rate": 0.12},
            {"name": "Surf Excel", "quantity": 1.0, "unit_price": 140.0, "gst_rate": 0.18},
        ]
        summary = summarize_cart_gst(items)
        expected_gross = 2 * 44.0 + 1 * 275.0 + 4 * 14.0 + 1 * 140.0 # 88 + 275 + 56 + 140 = 559.00
        self.assertEqual(summary["grand_total"], expected_gross)
        self.assertAlmostEqual(
            summary["total_taxable_amount"] + summary["total_tax"],
            expected_gross,
            places=2
        )
        self.assertEqual(len(summary["slab_breakup"]), 4)  # 0%, 5%, 12%, 18%


if __name__ == "__main__":
    unittest.main()
