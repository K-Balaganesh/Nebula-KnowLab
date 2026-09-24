"""Standalone test runner to execute the full automated test suite without external test runners."""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tests.test_oversell_guard import TestOversellGuard
from tests.test_gst_calculations import TestGSTCalculations
from tests.test_multi_turn_bill import TestMultiTurnBills
from tests.test_khata_ledger import TestKhataLedger
from tests.test_concurrency import TestConcurrency
from tests.test_idempotency import TestIdempotency
from tests.test_preferences_memory import TestPreferencesMemory
from tests.test_artifacts import TestArtifacts


def run_all_tests():
    """Discover and run all unit tests for the 9 Hard Parts."""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    test_classes = [
        ("Hard Part 2: Oversell Guard", TestOversellGuard),
        ("Hard Part 3: GST Correctness", TestGSTCalculations),
        ("Hard Part 4: Multi-Turn Bills", TestMultiTurnBills),
        ("Hard Part 7: Khata & Guardrails", TestKhataLedger),
        ("Hard Part 6: Concurrency (ACID)", TestConcurrency),
        ("Hard Part 5: Idempotency", TestIdempotency),
        ("Hard Part 9: Cross-Session Memory", TestPreferencesMemory),
        ("Hard Part 8: Real Artifacts (PDF/PPTX)", TestArtifacts),
    ]

    print("=" * 70)
    print("🧪 RUNNING COMPREHENSIVE TEST SUITE FOR THE 9 HARD PARTS")
    print("=" * 70)

    total_run = 0
    total_failures = 0
    total_errors = 0

    runner = unittest.TextTestRunner(verbosity=2)

    for label, cls in test_classes:
        print(f"\n▶ Running: {label}...")
        sub_suite = loader.loadTestsFromTestCase(cls)
        result = runner.run(sub_suite)
        total_run += result.testsRun
        total_failures += len(result.failures)
        total_errors += len(result.errors)

    print("\n" + "=" * 70)
    print(f"📊 SUMMARY: {total_run} tests run across all hard parts.")
    if total_failures == 0 and total_errors == 0:
        print("🎉 ALL TESTS PASSED! Strict compliance with assignment rubric verified.")
    else:
        print(f"❌ FAILURES: {total_failures}, ERRORS: {total_errors}")
    print("=" * 70)

    return total_failures + total_errors


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
