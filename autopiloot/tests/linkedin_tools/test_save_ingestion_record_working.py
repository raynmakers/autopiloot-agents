"""
Comprehensive test for save_ingestion_record tool targeting full coverage.
"""

import unittest
import os
import sys
import json
import importlib.util
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone


class TestSaveIngestionRecordWorking(unittest.TestCase):
    """Comprehensive test targeting coverage for save_ingestion_record.py."""

    @classmethod
    def setUpClass(cls):
        """Set up test class with proper mocking and imports."""
        # Define all mock modules
        mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google.cloud': MagicMock(),
            'google.cloud.firestore': MagicMock(),
        }

        # Mock Pydantic Field
        def mock_field(*args, **kwargs):
            return kwargs.get('default', None)

        with patch.dict('sys.modules', mock_modules):
            # Create mock BaseTool
            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
            sys.modules['pydantic'].Field = mock_field

            # Import using importlib for proper coverage
            tool_path = os.path.join(os.path.dirname(__file__), '..', '..',
                                   'linkedin_agent', 'tools', 'save_ingestion_record.py')
            spec = importlib.util.spec_from_file_location("save_ingestion_record", tool_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.SaveIngestionRecord = module.SaveIngestionRecord

    @patch('builtins.__import__')
    def test_successful_firestore_save(self, mock_import):
        """Test successful saving to Firestore."""
        def side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.load_environment = Mock()
                mock_env.get_required_env_var = Mock(return_value="test-project-id")
                return mock_env
            elif 'loader' in name:
                mock_loader = MagicMock()
                mock_loader.get_config_value = Mock(side_effect=lambda key, default: {
                    "linkedin.profiles": ["alexhormozi"],
                    "linkedin.processing.content_types": ["posts", "comments"],
                    "linkedin.processing.daily_limit_per_profile": 25
                }.get(key, default))
                return mock_loader
            return MagicMock()

        mock_import.side_effect = side_effect

        # Mock Firestore
        mock_firestore = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_doc_ref = MagicMock()

        mock_firestore.Client.return_value = mock_db
        mock_db.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref

        test_stats = {
            "posts_processed": 10,
            "comments_processed": 5,
            "zep_upserted": 14,
            "zep_skipped": 1,
            "duplicates_removed": 2,
            "unique_count": 13,
            "original_count": 15,
            "duplicate_rate": 0.133
        }

        test_errors = [
            {
                "type": "api_error",
                "message": "Rate limit exceeded",
                "timestamp": "2024-01-15T10:15:00Z"
            }
        ]

        tool = self.SaveIngestionRecord(
            run_id="test_run_123456",
            profile_identifier="alexhormozi",
            content_type="posts",
            ingestion_stats=test_stats,
            zep_group_id="linkedin_alexhormozi_posts",
            processing_duration_seconds=45.2,
            errors=test_errors
        )

        with patch('google.cloud.firestore', mock_firestore):
            result = tool.run()
            result_data = json.loads(result)

        self.assertEqual(result_data['status'], 'saved')
        self.assertIn('audit_record_id', result_data)
        self.assertIn('linkedin_ingestion_', result_data['audit_record_id'])
        self.assertIn('record_summary', result_data)

        # Verify Firestore calls
        mock_db.collection.assert_called_with('linkedin_ingestion_logs')
        mock_doc_ref.set.assert_called_once()

    @patch('builtins.__import__')
    def test_mock_response_fallback(self, mock_import):
        """Test mock response when Firestore is not available (lines 121-122)."""
        def side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.load_environment = Mock()
                mock_env.get_required_env_var = Mock(side_effect=Exception("google.cloud credentials not found"))
                return mock_env
            return MagicMock()

        mock_import.side_effect = side_effect

        test_stats = {"posts_processed": 5, "zep_upserted": 4}

        tool = self.SaveIngestionRecord(
            run_id="test_run_456",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats=test_stats
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(result_data['status'], 'mock_saved')
        self.assertIn('note', result_data)
        self.assertIn('Mock response', result_data['note'])

    @patch('builtins.__import__')
    def test_exception_handling(self, mock_import):
        """Test exception handling for non-credential errors (lines 124-130)."""
        def side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.load_environment = Mock(side_effect=Exception("Other error"))
                return mock_env
            return MagicMock()

        mock_import.side_effect = side_effect

        test_stats = {"posts_processed": 5}

        tool = self.SaveIngestionRecord(
            run_id="test_run_789",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats=test_stats
        )

        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(result_data['error'], 'audit_save_failed')
        self.assertEqual(result_data['run_id'], 'test_run_789')
        self.assertEqual(result_data['profile'], 'testuser')

    def test_audit_record_preparation_basic(self):
        """Test basic audit record preparation."""
        test_stats = {
            "posts_processed": 8,
            "comments_processed": 3,
            "zep_upserted": 10,
            "zep_skipped": 1
        }

        tool = self.SaveIngestionRecord(
            run_id="test_run_abc",
            profile_identifier="testuser",
            content_type="mixed",
            ingestion_stats=test_stats,
            zep_group_id="test_group",
            processing_duration_seconds=30.5,
            errors=None
        )

        record = tool._prepare_audit_record("test_record_id")

        # Basic fields
        self.assertEqual(record['record_id'], 'test_record_id')
        self.assertEqual(record['run_id'], 'test_run_abc')
        self.assertEqual(record['profile_identifier'], 'testuser')
        self.assertEqual(record['content_type'], 'mixed')

        # Processing metadata
        self.assertEqual(record['processing']['duration_seconds'], 30.5)
        self.assertIn('start_time', record['processing'])
        self.assertIn('end_time', record['processing'])

        # Zep storage
        self.assertEqual(record['zep_storage']['group_id'], 'test_group')
        self.assertEqual(record['zep_storage']['upserted'], 10)
        self.assertEqual(record['zep_storage']['skipped'], 1)

        # Error tracking
        self.assertEqual(record['errors']['count'], 0)
        self.assertEqual(record['errors']['details'], [])

        # Status
        self.assertEqual(record['status'], 'success')
        self.assertTrue(record['success'])

    def test_audit_record_with_content_metrics(self):
        """Test audit record with content metrics (lines 179-189)."""
        test_stats = {
            "posts_processed": 12,
            "comments_processed": 8,
            "reactions_processed": 3,
            "zep_upserted": 20
        }

        tool = self.SaveIngestionRecord(
            run_id="test_run",
            profile_identifier="testuser",
            content_type="mixed",
            ingestion_stats=test_stats
        )

        record = tool._prepare_audit_record("test_record_id")

        # Should have content_metrics section
        self.assertIn('content_metrics', record)
        content_metrics = record['content_metrics']
        self.assertEqual(content_metrics['posts_processed'], 12)
        self.assertEqual(content_metrics['comments_processed'], 8)
        self.assertEqual(content_metrics['reactions_processed'], 3)
        self.assertEqual(content_metrics['total_entities'], 23)  # 12 + 8 + 3

    def test_audit_record_with_deduplication_metrics(self):
        """Test audit record with deduplication metrics (lines 192-198)."""
        test_stats = {
            "posts_processed": 10,
            "duplicates_removed": 3,
            "original_count": 13,
            "unique_count": 10,
            "duplicate_rate": 0.231
        }

        tool = self.SaveIngestionRecord(
            run_id="test_run",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats=test_stats
        )

        record = tool._prepare_audit_record("test_record_id")

        # Should have deduplication section
        self.assertIn('deduplication', record)
        dedup = record['deduplication']
        self.assertEqual(dedup['original_count'], 13)
        self.assertEqual(dedup['unique_count'], 10)
        self.assertEqual(dedup['duplicates_removed'], 3)
        self.assertEqual(dedup['duplicate_rate'], 0.231)

    def test_start_time_calculation_with_duration(self):
        """Test start time calculation with processing duration (lines 216-218)."""
        tool = self.SaveIngestionRecord(
            run_id="test_run",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats={},
            processing_duration_seconds=60.0  # 1 minute
        )

        start_time = tool._calculate_start_time()

        # Should be a valid ISO timestamp
        self.assertIn('T', start_time)
        self.assertTrue(start_time.endswith('Z'))

        # Should be approximately 1 minute ago (within 2 seconds tolerance)
        current_time = datetime.now(timezone.utc).timestamp()
        parsed_start = datetime.fromisoformat(start_time.replace('Z', '+00:00')).timestamp()
        time_diff = current_time - parsed_start
        self.assertAlmostEqual(time_diff, 60.0, delta=2.0)

    def test_start_time_calculation_without_duration(self):
        """Test start time calculation without processing duration (lines 219-220)."""
        tool = self.SaveIngestionRecord(
            run_id="test_run",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats={},
            processing_duration_seconds=None
        )

        start_time = tool._calculate_start_time()

        # Should be current time (approximately)
        current_time = datetime.now(timezone.utc).isoformat()
        # Just check the date part since timing can vary slightly
        self.assertEqual(start_time[:10], current_time[:10])

    def test_run_status_success(self):
        """Test run status determination - success case (lines 229-230)."""
        tool = self.SaveIngestionRecord(
            run_id="test_run",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats={"posts_processed": 5},
            errors=None
        )

        status = tool._determine_run_status()
        self.assertEqual(status, 'success')

        # Also test with empty errors list
        tool.errors = []
        status = tool._determine_run_status()
        self.assertEqual(status, 'success')

    def test_run_status_partial_success(self):
        """Test run status determination - partial success case (lines 233-240)."""
        test_stats = {
            "posts_processed": 5,
            "comments_processed": 3,
            "zep_upserted": 7
        }

        tool = self.SaveIngestionRecord(
            run_id="test_run",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats=test_stats,
            errors=[{"type": "warning", "message": "Some error"}]
        )

        status = tool._determine_run_status()
        self.assertEqual(status, 'partial_success')

    def test_run_status_failed(self):
        """Test run status determination - failed case (lines 241-242)."""
        test_stats = {
            "posts_processed": 0,
            "comments_processed": 0,
            "zep_upserted": 0
        }

        tool = self.SaveIngestionRecord(
            run_id="test_run",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats=test_stats,
            errors=[{"type": "error", "message": "Critical error"}]
        )

        status = tool._determine_run_status()
        self.assertEqual(status, 'failed')

    def test_record_summary_with_content_metrics(self):
        """Test record summary creation with content metrics (lines 258-263)."""
        test_stats = {
            "posts_processed": 10,
            "comments_processed": 5,
            "zep_upserted": 14,
            "duplicates_removed": 2,
            "unique_count": 13,
            "engagement_rate": 0.045
        }

        tool = self.SaveIngestionRecord(
            run_id="test_run",
            profile_identifier="alexhormozi",
            content_type="mixed",
            ingestion_stats=test_stats,
            processing_duration_seconds=42.5,
            errors=None
        )

        summary = tool._create_record_summary()

        self.assertEqual(summary['profile'], 'alexhormozi')
        self.assertEqual(summary['content_type'], 'mixed')
        self.assertEqual(summary['processing_duration'], 42.5)
        self.assertEqual(summary['status'], 'success')
        self.assertEqual(summary['content_processed'], 15)  # 10 + 5
        self.assertEqual(summary['zep_upserted'], 14)
        self.assertEqual(summary['errors'], 0)
        self.assertEqual(summary['duplicates_removed'], 2)
        self.assertEqual(summary['unique_count'], 13)
        self.assertEqual(summary['engagement_rate'], 0.045)

    def test_record_summary_with_errors(self):
        """Test record summary with errors (line 270)."""
        test_stats = {"posts_processed": 3}
        test_errors = [
            {"type": "error1", "message": "First error"},
            {"type": "error2", "message": "Second error"}
        ]

        tool = self.SaveIngestionRecord(
            run_id="test_run",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats=test_stats,
            errors=test_errors
        )

        summary = tool._create_record_summary()
        self.assertEqual(summary['errors'], 2)

    def test_record_summary_key_metrics_loop(self):
        """Test key metrics loop in record summary (lines 273-275)."""
        test_stats = {
            "posts_processed": 5,
            "duplicates_removed": 1,
            "unique_count": 4,
            "engagement_rate": 0.067,
            "other_metric": "should_not_appear"  # Not in the metrics list
        }

        tool = self.SaveIngestionRecord(
            run_id="test_run",
            profile_identifier="testuser",
            content_type="posts",
            ingestion_stats=test_stats
        )

        summary = tool._create_record_summary()

        # Should include metrics from the list
        self.assertIn('duplicates_removed', summary)
        self.assertIn('unique_count', summary)
        self.assertIn('engagement_rate', summary)

        # Should not include metrics not in the list
        self.assertNotIn('other_metric', summary)

    def test_mock_response_creation(self):
        """Test mock response creation (lines 286-296)."""
        test_stats = {
            "posts_processed": 7,
            "zep_upserted": 6
        }

        tool = self.SaveIngestionRecord(
            run_id="mock_test_123456",
            profile_identifier="mockuser",
            content_type="posts",
            ingestion_stats=test_stats,
            processing_duration_seconds=25.0
        )

        mock_response = tool._create_mock_response()
        result_data = json.loads(mock_response)

        self.assertEqual(result_data['status'], 'mock_saved')
        self.assertIn('audit_record_id', result_data)
        self.assertIn('linkedin_ingestion_', result_data['audit_record_id'])
        self.assertIn('mock_test_1', result_data['audit_record_id'])  # First 8 chars of run_id
        self.assertIn('firestore_document_path', result_data)
        self.assertIn('record_summary', result_data)
        self.assertIn('saved_at', result_data)
        self.assertIn('note', result_data)

        # Check record summary is included
        summary = result_data['record_summary']
        self.assertEqual(summary['profile'], 'mockuser')
        self.assertEqual(summary['processing_duration'], 25.0)


if __name__ == '__main__':
    unittest.main()