"""
Automated Test Runner for AutoStock Studio.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    print("=" * 65)
    print("  RUNNING AUTOSTOCK STUDIO AUTOMATED TEST SUITE")
    print("=" * 65)

    loader = unittest.TestLoader()
    start_dir = str(Path(__file__).parent / "tests")
    suite = loader.discover(start_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 65)
    if result.wasSuccessful():
        print(f"  [SUCCESS] All {result.testsRun} tests passed successfully!")
        print("=" * 65)
        sys.exit(0)
    else:
        print(f"  [FAILED] {len(result.failures)} failures, {len(result.errors)} errors out of {result.testsRun} tests.")
        print("=" * 65)
        sys.exit(1)


if __name__ == "__main__":
    main()
