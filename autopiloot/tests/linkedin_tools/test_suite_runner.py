"""
Comprehensive test suite runner for all LinkedIn tools.
Runs all tests and provides summary report.
"""

import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import all test modules
from . import (
    test_get_user_posts,
    test_get_post_comments,
    test_deduplicate_entities,
    test_upsert_to_zep_group,
    test_save_ingestion_record,
    test_normalize_linkedin_content
)


def run_all_tests():
    """Run comprehensive test suite for all LinkedIn tools."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test modules
    test_modules = [
        test_get_user_posts,
        test_get_post_comments,
        test_deduplicate_entities,
        test_upsert_to_zep_group,
        test_save_ingestion_record,
        test_normalize_linkedin_content
    ]

    for module in test_modules:
        suite.addTests(loader.loadTestsFromModule(module))

    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print(f"\n{'='*60}")
    print("LINKEDIN TOOLS TEST SUITE SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")

    if result.failures:
        print(f"\nFAILURES ({len(result.failures)}):")
        for test, trace in result.failures:
            print(f"- {test}")

    if result.errors:
        print(f"\nERRORS ({len(result.errors)}):")
        for test, trace in result.errors:
            print(f"- {test}")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)