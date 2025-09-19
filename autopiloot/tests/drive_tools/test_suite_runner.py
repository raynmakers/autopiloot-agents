"""
Drive Agent test suite runner for comprehensive coverage validation.
Runs all Drive Agent tool tests and provides detailed coverage report.
"""

import unittest
import sys
import os

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Import all Drive Agent test modules
from tests.drive_tools.test_list_tracked_targets_from_config import TestListTrackedTargetsFromConfig
from tests.drive_tools.test_upsert_drive_docs_to_zep import TestUpsertDriveDocsToZep
from tests.drive_tools.test_save_drive_ingestion_record import TestSaveDriveIngestionRecord
from tests.drive_tools.test_extract_text_from_document import TestExtractTextFromDocument


def create_drive_agent_test_suite():
    """Create comprehensive test suite for all Drive Agent tools."""
    suite = unittest.TestSuite()

    # Add all Drive Agent tool test classes
    test_classes = [
        TestListTrackedTargetsFromConfig,
        TestUpsertDriveDocsToZep,
        TestSaveDriveIngestionRecord,
        TestExtractTextFromDocument,
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    return suite


def run_drive_agent_tests():
    """Run all Drive Agent tests and return results."""
    print("🔍 Running Drive Agent Test Suite...")
    print("=" * 60)

    suite = create_drive_agent_test_suite()
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print("📊 Drive Agent Test Results Summary:")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    print(f"   Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")

    if result.failures:
        print(f"\n❌ {len(result.failures)} Test Failures:")
        for test, traceback in result.failures:
            print(f"   - {test}: {traceback.split('AssertionError:')[-1].strip()}")

    if result.errors:
        print(f"\n🚨 {len(result.errors)} Test Errors:")
        for test, traceback in result.errors:
            print(f"   - {test}: {traceback.split('Exception:')[-1].strip()}")

    print("\n🎯 Tool Coverage:")
    print("   ✅ ListTrackedTargetsFromConfig - Configuration loading and validation")
    print("   ✅ UpsertDriveDocsToZep - Zep GraphRAG integration and document indexing")
    print("   ✅ SaveDriveIngestionRecord - Firestore audit logging and metrics")
    print("   ✅ ExtractTextFromDocument - Multi-format text extraction pipeline")
    print("   ⏳ ResolveFolderTree - TODO: Add comprehensive tests")
    print("   ⏳ ListDriveChanges - TODO: Add comprehensive tests")
    print("   ⏳ FetchFileContent - TODO: Add comprehensive tests")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_drive_agent_tests()
    sys.exit(0 if success else 1)