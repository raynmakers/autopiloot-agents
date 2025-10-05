"""
Coverage test for generate_daily_digest.py using direct import approach
This test bypasses package imports to focus on the specific module
"""

import unittest
import sys
import os
import importlib.util
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import json


class TestGenerateDailyDigestCoverage(unittest.TestCase):
    """Coverage test for generate_daily_digest.py using direct imports"""

    def setUp(self):
        """Set up mocks before each test"""
        # Add module path
        module_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..',
            'observability_agent', 'tools',
            'generate_daily_digest.py'
        )

        self.module_path = os.path.abspath(module_path)

        # Standard mock modules
        self.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google.cloud.firestore': MagicMock(),
            'pytz': MagicMock(),
            'dotenv': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'audit_logger': MagicMock()
        }

        # Setup standard mocks
        self.mock_modules['pydantic'].Field = lambda *args, **kwargs: kwargs.get('default', None)

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        self.mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool

    def _import_module_directly(self):
        """Import the module directly bypassing package __init__"""
        spec = importlib.util.spec_from_file_location('generate_daily_digest', self.module_path)
        module = importlib.util.module_from_spec(spec)

        # Set up module environment
        module.__file__ = self.module_path
        module.__name__ = 'generate_daily_digest'

        spec.loader.exec_module(module)
        return module

    def test_successful_digest_generation(self):
        """Test successful daily digest generation"""
        # Mock environment functions
        self.mock_modules['env_loader'].get_required_env_var = lambda var, desc: 'test-project-id'
        self.mock_modules['loader'].load_app_config = lambda: {
            'google_drive': {
                'folder_id_transcripts': 'test-transcript-folder',
                'folder_id_summaries': 'test-summary-folder'
            }
        }
        self.mock_modules['loader'].get_config_value = lambda key, default: {
            'budgets.transcription_daily_usd': 5.0,
            'notifications.slack.digest.sections': ['summary', 'budgets', 'issues', 'links']
        }.get(key, default)

        # Mock audit logger
        mock_audit_logger = MagicMock()
        mock_audit_logger.write_audit_log = MagicMock(return_value=True)
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

        # Mock pytz
        mock_tz = MagicMock()
        mock_tz.localize = lambda dt: dt.replace(tzinfo=timezone.utc)
        self.mock_modules['pytz'].timezone = lambda tz: mock_tz

        # Mock Firestore
        mock_db = self._setup_successful_firestore_mock()
        self.mock_modules['google.cloud.firestore'].Client = MagicMock(return_value=mock_db)

        with patch.dict('sys.modules', self.mock_modules):
            module = self._import_module_directly()
            tool_class = module.GenerateDailyDigest

            tool = tool_class(
                date="2024-01-15",
                timezone_name="Europe/Amsterdam"
            )

            result = tool.run()
            result_json = json.loads(result)

            # Verify successful generation
            self.assertNotIn('error', result_json)
            self.assertEqual(result_json['date'], '2024-01-15')
            self.assertEqual(result_json['timezone'], 'Europe/Amsterdam')

            # Verify metrics
            self.assertIn('metrics', result_json)
            metrics = result_json['metrics']
            self.assertIsInstance(metrics['videos_discovered'], int)
            self.assertIsInstance(metrics['videos_transcribed'], int)

            # Verify Slack blocks
            self.assertIn('slack_blocks', result_json)
            self.assertTrue(len(result_json['slack_blocks']) > 0)

            # Verify audit logging
            mock_audit_logger.write_audit_log.assert_called()

    def test_error_handling_firestore_failure(self):
        """Test error handling when Firestore fails"""
        # Mock environment functions
        self.mock_modules['env_loader'].get_required_env_var = lambda var, desc: 'test-project-id'
        self.mock_modules['loader'].load_app_config = lambda: {}
        self.mock_modules['loader'].get_config_value = lambda key, default: default

        # Mock audit logger
        mock_audit_logger = MagicMock()
        mock_audit_logger.write_audit_log = MagicMock(return_value=True)
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

        # Mock Firestore to fail
        self.mock_modules['google.cloud.firestore'].Client.side_effect = Exception("Firestore connection failed")

        with patch.dict('sys.modules', self.mock_modules):
            module = self._import_module_directly()
            tool_class = module.GenerateDailyDigest

            tool = tool_class(date="2024-01-15")
            result = tool.run()
            result_json = json.loads(result)

            # Verify error response
            self.assertIn('error', result_json)
            self.assertEqual(result_json['error'], 'digest_generation_failed')
            self.assertIn('Firestore connection failed', result_json['message'])

    def test_metrics_collection_comprehensive(self):
        """Test comprehensive metrics collection including error paths"""
        # Mock environment functions
        self.mock_modules['env_loader'].get_required_env_var = lambda var, desc: 'test-project-id'
        self.mock_modules['loader'].get_config_value = lambda key, default: 5.0

        # Mock audit logger
        mock_audit_logger = MagicMock()
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

        with patch.dict('sys.modules', self.mock_modules):
            module = self._import_module_directly()
            tool_class = module.GenerateDailyDigest

            tool = tool_class(date="2024-01-15")

            # Test metrics collection with error
            mock_db = MagicMock()
            mock_db.collection.side_effect = Exception("Collection access failed")

            start_utc = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
            end_utc = datetime(2024, 1, 16, 0, 0, 0, tzinfo=timezone.utc)

            metrics = tool._collect_daily_metrics(mock_db, start_utc, end_utc)

            # Verify error handling
            self.assertIn('collection_error', metrics)
            self.assertEqual(metrics['collection_error'], 'Collection access failed')

    def test_content_creation_all_scenarios(self):
        """Test content creation for all budget scenarios"""
        with patch.dict('sys.modules', self.mock_modules):
            module = self._import_module_directly()
            tool_class = module.GenerateDailyDigest

            tool = tool_class(date="2024-01-15")

            # Test all budget scenarios
            scenarios = [
                # Critical (>= 90%)
                {'budget_percentage': 95.0, 'expected_emoji': '🔴', 'expected_status': 'CRITICAL'},
                # Warning (80-89%)
                {'budget_percentage': 85.0, 'expected_emoji': '🟡', 'expected_status': 'WARNING'},
                # Healthy (< 80%)
                {'budget_percentage': 60.0, 'expected_emoji': '🟢', 'expected_status': 'HEALTHY'}
            ]

            config = {'google_drive': {'folder_id_transcripts': 'test', 'folder_id_summaries': 'test'}}

            for scenario in scenarios:
                with self.subTest(budget_percentage=scenario['budget_percentage']):
                    metrics = {
                        'videos_discovered': 5, 'videos_transcribed': 4, 'summaries_generated': 3,
                        'budget_percentage': scenario['budget_percentage'], 'total_cost_usd': 4.25,
                        'dlq_entries': 1, 'errors': [], 'top_videos': []
                    }

                    content = tool._create_digest_content(metrics, "2024-01-15", config)
                    budget = content['budget_status']

                    self.assertEqual(budget['emoji'], scenario['expected_emoji'])
                    self.assertEqual(budget['status'], scenario['expected_status'])

    def test_slack_blocks_formatting(self):
        """Test Slack blocks formatting including edge cases"""
        # Mock config function
        self.mock_modules['loader'].get_config_value = lambda key, default: ['summary', 'budgets', 'issues', 'links'] if 'sections' in key else default

        with patch.dict('sys.modules', self.mock_modules):
            module = self._import_module_directly()
            tool_class = module.GenerateDailyDigest

            tool = tool_class(date="2024-01-15")

            # Test with videos (including title truncation)
            content_with_videos = {
                'header': '🌅 Daily Autopiloot Digest - 2024-01-15',
                'processing_summary': {'flow': '5 → 4 → 3', 'completion_rate': '60.0%'},
                'budget_status': {'emoji': '🟡', 'status': 'WARNING', 'spent': '$4.25', 'percentage': '85.0%', 'limit': '$5.00'},
                'issues': {'summary': '2 DLQ entries', 'dlq_count': 2},
                'links': {'transcripts': 'https://test.com/transcripts', 'summaries': 'https://test.com/summaries', 'firestore': 'https://test.com/firestore'},
                'top_videos': [
                    {'title': 'Very Long Video Title That Should Be Truncated Because It Exceeds The Fifty Character Limit', 'duration_sec': 3600}
                ]
            }

            blocks = tool._format_slack_blocks(content_with_videos)

            # Verify basic structure
            self.assertTrue(len(blocks) >= 5)  # Header + sections + footer

            # Verify header
            header_block = blocks[0]
            self.assertEqual(header_block['type'], 'header')

            # Verify video truncation
            videos_block = next((b for b in blocks if 'Top Videos' in b.get('text', {}).get('text', '')), None)
            self.assertIsNotNone(videos_block)
            # Title should be truncated to 50 chars + "..."
            self.assertIn('Very Long Video Title That Should Be Truncated Bec...', videos_block['text']['text'])

            # Test empty videos
            content_empty = dict(content_with_videos)
            content_empty['top_videos'] = []
            blocks_empty = tool._format_slack_blocks(content_empty)
            videos_block_empty = next((b for b in blocks_empty if 'Top Videos' in b.get('text', {}).get('text', '')), None)
            self.assertIsNone(videos_block_empty)

    def _setup_successful_firestore_mock(self):
        """Setup mock Firestore with successful data"""
        mock_db = MagicMock()

        # Mock documents
        mock_video_docs = [
            MagicMock(id='video1', to_dict=lambda: {
                'title': 'Test Video 1', 'status': 'summarized', 'duration_sec': 1800, 'source': 'scraper'
            }),
            MagicMock(id='video2', to_dict=lambda: {
                'title': 'Test Video 2', 'status': 'transcribed', 'duration_sec': 2400, 'source': 'sheet'
            })
        ]

        mock_transcript_docs = [
            MagicMock(to_dict=lambda: {'costs': {'transcription_usd': 1.25}}),
            MagicMock(to_dict=lambda: {'costs': {'transcription_usd': 0.75}})
        ]

        mock_summary_docs = [MagicMock(), MagicMock()]

        mock_dlq_docs = [
            MagicMock(to_dict=lambda: {'job_type': 'transcription', 'reason': 'timeout', 'retry_count': 3})
        ]

        mock_cost_doc = MagicMock()
        mock_cost_doc.exists = True
        mock_cost_doc.to_dict.return_value = {'transcription_usd_total': 2.50}

        def mock_collection(name):
            mock_coll = MagicMock()
            if name == 'videos':
                mock_coll.where.return_value.where.return_value.stream.return_value = mock_video_docs
            elif name == 'transcripts':
                mock_coll.where.return_value.where.return_value.stream.return_value = mock_transcript_docs
            elif name == 'summaries':
                mock_coll.where.return_value.where.return_value.stream.return_value = mock_summary_docs
            elif name == 'jobs_deadletter':
                mock_coll.where.return_value.where.return_value.stream.return_value = mock_dlq_docs
            elif name == 'costs_daily':
                mock_coll.document.return_value.get.return_value = mock_cost_doc
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
            return mock_coll

        mock_db.collection.side_effect = mock_collection
        return mock_db


if __name__ == "__main__":
    unittest.main()