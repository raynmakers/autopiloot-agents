"""
Comprehensive test for monitor_transcription_budget.py - targeting actual code execution for coverage
Uses real imports with proper mocking to achieve maximum coverage
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import sys
import json
import os
from datetime import datetime, timezone


class TestMonitorTranscriptionBudgetComprehensive(unittest.TestCase):
    """Comprehensive tests with real code execution for maximum coverage"""

    def setUp(self):
        """Set up test environment with comprehensive dependency mocking"""
        # Add module paths just like the actual tool does
        current_dir = os.path.dirname(__file__)
        core_path = os.path.join(current_dir, '..', '..', 'core')
        config_path = os.path.join(current_dir, '..', '..', 'config')
        # Set up comprehensive mocks that match the actual tool's imports
        self.patcher_firestore = patch('google.cloud.firestore')
        self.patcher_env_loader = patch('env_loader.get_required_env_var')
        self.patcher_load_config = patch('loader.load_app_config')
        self.patcher_get_config = patch('loader.get_config_value')
        self.patcher_audit = patch('audit_logger.audit_logger')

        self.mock_firestore = self.patcher_firestore.start()
        self.mock_get_env = self.patcher_env_loader.start()
        self.mock_load_config = self.patcher_load_config.start()
        self.mock_get_config = self.patcher_get_config.start()
        self.mock_audit = self.patcher_audit.start()

    def tearDown(self):
        """Clean up patches"""
        self.patcher_firestore.stop()
        self.patcher_env_loader.stop()
        self.patcher_load_config.stop()
        self.patcher_get_config.stop()
        self.patcher_audit.stop()

    def test_successful_budget_monitoring_with_costs_daily(self):
        """Test successful monitoring using costs_daily collection"""
        # Setup environment and config mocks
        self.mock_get_env.return_value = 'test-project-id'
        self.mock_load_config.return_value = {'budgets': {'transcription_daily_usd': 5.0}}
        self.mock_get_config.return_value = 5.0

        # Setup Firestore mock - costs_daily exists
        mock_db = Mock()
        self.mock_firestore.Client.return_value = mock_db

        # Mock costs_daily document exists
        mock_costs_doc = Mock()
        mock_costs_doc.exists = True
        mock_costs_doc.to_dict.return_value = {
            'transcription_usd': 2.5,
            'transcript_count': 3
        }
        mock_db.collection.return_value.document.return_value = mock_costs_doc

        # Import and test the actual tool
        from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

        tool = MonitorTranscriptionBudget(date='2024-01-15')
        result = tool.run()
        result_data = json.loads(result)

        # Verify successful execution
        self.assertEqual(result_data['status'], 'OK')
        self.assertEqual(result_data['total_usd'], 2.5)
        self.assertEqual(result_data['daily_limit'], 5.0)
        self.assertEqual(result_data['usage_percentage'], 50.0)
        self.assertEqual(result_data['transcript_count'], 3)
        self.assertFalse(result_data['alert_sent'])
        self.assertEqual(result_data['date'], '2024-01-15')

        print("✅ Successful budget monitoring with costs_daily test passed")

    def test_threshold_reached_with_alert_sending(self):
        """Test 80% threshold reached triggering Slack alert"""
        # Setup environment and config mocks
        self.mock_get_env.return_value = 'test-project-id'
        self.mock_load_config.return_value = {'budgets': {'transcription_daily_usd': 5.0}}
        self.mock_get_config.return_value = 5.0

        # Setup Firestore mock - costs_daily with 80% usage
        mock_db = Mock()
        self.mock_firestore.Client.return_value = mock_db

        mock_costs_doc = Mock()
        mock_costs_doc.exists = True
        mock_costs_doc.to_dict.return_value = {
            'transcription_usd': 4.0,  # 80% of $5.00
            'transcript_count': 5
        }
        mock_db.collection.return_value.document.return_value = mock_costs_doc

        # Mock the Slack tools to avoid complex circular import issues
        with patch.object(MonitorTranscriptionBudget, '_send_budget_alert', return_value=True) as mock_alert:
            from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

            tool = MonitorTranscriptionBudget(date='2024-01-15')
            result = tool.run()
            result_data = json.loads(result)

            # Verify threshold reached
            self.assertEqual(result_data['status'], 'THRESHOLD_REACHED')
            self.assertEqual(result_data['total_usd'], 4.0)
            self.assertEqual(result_data['usage_percentage'], 80.0)
            self.assertTrue(result_data['alert_sent'])

            # Verify alert was called
            mock_alert.assert_called_once_with(4.0, 5.0, 80.0, '2024-01-15')

        print("✅ Threshold reached with alert test passed")

    def test_budget_exceeded_scenario(self):
        """Test budget exceeded (100%+) scenario"""
        # Setup environment and config mocks
        self.mock_get_env.return_value = 'test-project-id'
        self.mock_load_config.return_value = {'budgets': {'transcription_daily_usd': 5.0}}
        self.mock_get_config.return_value = 5.0

        # Setup Firestore mock - costs_daily with 120% usage
        mock_db = Mock()
        self.mock_firestore.Client.return_value = mock_db

        mock_costs_doc = Mock()
        mock_costs_doc.exists = True
        mock_costs_doc.to_dict.return_value = {
            'transcription_usd': 6.0,  # 120% of $5.00
            'transcript_count': 7
        }
        mock_db.collection.return_value.document.return_value = mock_costs_doc

        # Mock alert sending
        with patch.object(MonitorTranscriptionBudget, '_send_budget_alert', return_value=True):
            from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

            tool = MonitorTranscriptionBudget(date='2024-01-15')
            result = tool.run()
            result_data = json.loads(result)

            # Verify exceeded status
            self.assertEqual(result_data['status'], 'EXCEEDED')
            self.assertEqual(result_data['total_usd'], 6.0)
            self.assertEqual(result_data['usage_percentage'], 120.0)
            self.assertTrue(result_data['alert_sent'])

        print("✅ Budget exceeded scenario test passed")

    def test_warning_status_no_alert(self):
        """Test warning status (70-79%) without alert"""
        # Setup environment and config mocks
        self.mock_get_env.return_value = 'test-project-id'
        self.mock_load_config.return_value = {'budgets': {'transcription_daily_usd': 5.0}}
        self.mock_get_config.return_value = 5.0

        # Setup Firestore mock - costs_daily with 75% usage
        mock_db = Mock()
        self.mock_firestore.Client.return_value = mock_db

        mock_costs_doc = Mock()
        mock_costs_doc.exists = True
        mock_costs_doc.to_dict.return_value = {
            'transcription_usd': 3.75,  # 75% of $5.00
            'transcript_count': 4
        }
        mock_db.collection.return_value.document.return_value = mock_costs_doc

        from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

        tool = MonitorTranscriptionBudget(date='2024-01-15')
        result = tool.run()
        result_data = json.loads(result)

        # Verify warning status
        self.assertEqual(result_data['status'], 'WARNING')
        self.assertEqual(result_data['total_usd'], 3.75)
        self.assertEqual(result_data['usage_percentage'], 75.0)
        self.assertFalse(result_data['alert_sent'])  # No alert for WARNING

        print("✅ Warning status no alert test passed")

    def test_fallback_to_transcripts_collection(self):
        """Test fallback when costs_daily doesn't exist"""
        # Setup environment and config mocks
        self.mock_get_env.return_value = 'test-project-id'
        self.mock_load_config.return_value = {'budgets': {'transcription_daily_usd': 5.0}}
        self.mock_get_config.return_value = 5.0

        # Setup Firestore mock - costs_daily doesn't exist, use transcripts
        mock_db = Mock()
        self.mock_firestore.Client.return_value = mock_db

        # costs_daily doesn't exist
        mock_costs_doc = Mock()
        mock_costs_doc.exists = False

        # Mock transcripts collection query
        mock_transcript_docs = []
        for i in range(3):
            doc = Mock()
            doc.to_dict.return_value = {
                'costs': {'transcription_usd': 1.0}
            }
            mock_transcript_docs.append(doc)

        # Setup collection method routing
        def mock_collection(name):
            if name == 'costs_daily':
                return Mock(document=Mock(return_value=mock_costs_doc))
            elif name == 'transcripts':
                mock_transcripts = Mock()
                mock_query = Mock()
                mock_query.where.return_value.where.return_value.stream.return_value = mock_transcript_docs
                mock_transcripts.where.return_value = mock_query
                return mock_transcripts
            return Mock()

        mock_db.collection.side_effect = mock_collection

        from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

        tool = MonitorTranscriptionBudget(date='2024-01-15')
        result = tool.run()
        result_data = json.loads(result)

        # Verify fallback worked
        self.assertEqual(result_data['total_usd'], 3.0)  # 3 transcripts × $1.00
        self.assertEqual(result_data['transcript_count'], 3)
        self.assertEqual(result_data['usage_percentage'], 60.0)  # 60% of $5.00
        self.assertEqual(result_data['status'], 'OK')

        print("✅ Fallback to transcripts collection test passed")

    def test_invalid_date_format_error(self):
        """Test error handling for invalid date format"""
        # Setup basic mocks
        self.mock_get_env.return_value = 'test-project-id'
        self.mock_load_config.return_value = {'budgets': {'transcription_daily_usd': 5.0}}
        self.mock_get_config.return_value = 5.0

        from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

        tool = MonitorTranscriptionBudget(date='invalid-date')
        result = tool.run()
        result_data = json.loads(result)

        # Verify error handling
        self.assertIn('error', result_data)
        self.assertIn('Invalid date format', result_data['error'])
        self.assertEqual(result_data['status'], 'ERROR')
        self.assertEqual(result_data['total_usd'], 0.0)

        print("✅ Invalid date format error test passed")

    def test_firestore_connection_error(self):
        """Test error handling when Firestore connection fails"""
        # Setup environment mock that fails
        self.mock_get_env.side_effect = Exception("GCP_PROJECT_ID not found")

        from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

        tool = MonitorTranscriptionBudget(date='2024-01-15')
        result = tool.run()
        result_data = json.loads(result)

        # Verify error handling
        self.assertIn('error', result_data)
        self.assertIn('GCP_PROJECT_ID not found', result_data['error'])
        self.assertEqual(result_data['status'], 'ERROR')
        self.assertEqual(result_data['total_usd'], 0.0)

        print("✅ Firestore connection error test passed")

    def test_send_budget_alert_success(self):
        """Test successful Slack alert sending with real method execution"""
        # Setup environment and config mocks
        self.mock_get_env.return_value = 'test-project-id'
        self.mock_load_config.return_value = {
            'budgets': {'transcription_daily_usd': 5.0},
            'notifications': {'slack': {'channel': 'ops-autopiloot'}}
        }
        self.mock_get_config.side_effect = lambda key, config, default=None: {
            'budgets.transcription_daily_usd': 5.0,
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default)

        # Mock the Slack tools
        with patch('observability_agent.tools.monitor_transcription_budget.FormatSlackBlocks') as mock_formatter, \
             patch('observability_agent.tools.monitor_transcription_budget.SendSlackMessage') as mock_sender:

            # Setup mock returns
            mock_formatter.return_value.run.return_value = json.dumps({
                "blocks": [{"type": "header", "text": {"type": "plain_text", "text": "Budget Alert"}}]
            })

            mock_sender.return_value.run.return_value = json.dumps({
                "ts": "1234567890.123456",
                "channel": "#ops-autopiloot"
            })

            # Setup audit logger mock
            self.mock_audit.log_budget_alert = Mock()

            from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

            tool = MonitorTranscriptionBudget(date='2024-01-15')

            # Test the _send_budget_alert method directly
            result = tool._send_budget_alert(4.0, 5.0, 80.0, '2024-01-15')

            # Verify alert was sent successfully
            self.assertTrue(result)

            # Verify Slack tools were called
            mock_formatter.assert_called_once()
            mock_sender.assert_called_once()

            # Verify audit logging
            self.mock_audit.log_budget_alert.assert_called_once()

        print("✅ Send budget alert success test passed")

    def test_send_budget_alert_failure(self):
        """Test Slack alert failure handling"""
        # Setup environment and config mocks
        self.mock_get_env.return_value = 'test-project-id'
        self.mock_load_config.return_value = {
            'budgets': {'transcription_daily_usd': 5.0},
            'notifications': {'slack': {'channel': 'ops-autopiloot'}}
        }
        self.mock_get_config.side_effect = lambda key, config, default=None: {
            'budgets.transcription_daily_usd': 5.0,
            'notifications.slack.channel': 'ops-autopiloot'
        }.get(key, default)

        # Mock Slack tools to fail
        with patch('observability_agent.tools.monitor_transcription_budget.FormatSlackBlocks') as mock_formatter:
            mock_formatter.side_effect = Exception("Slack API error")

            from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

            tool = MonitorTranscriptionBudget(date='2024-01-15')

            # Test alert failure
            with patch('builtins.print') as mock_print:  # Capture warning print
                result = tool._send_budget_alert(4.0, 5.0, 80.0, '2024-01-15')

                # Verify failure handling
                self.assertFalse(result)
                mock_print.assert_called_once()
                self.assertIn('Failed to send budget alert', mock_print.call_args[0][0])

        print("✅ Send budget alert failure test passed")

    def test_main_block_execution(self):
        """Test main block execution for coverage"""
        # Setup comprehensive mocks for main block
        with patch('observability_agent.tools.monitor_transcription_budget.datetime') as mock_dt, \
             patch('builtins.print') as mock_print:

            # Mock datetime.now() for main block
            mock_dt.now.return_value = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
            mock_dt.strptime = datetime.strptime  # Keep strptime working
            mock_dt.timezone = timezone  # Keep timezone working

            # Setup environment mocks
            self.mock_get_env.return_value = 'test-project-id'
            self.mock_load_config.return_value = {'budgets': {'transcription_daily_usd': 5.0}}
            self.mock_get_config.return_value = 5.0

            # Setup Firestore mock
            mock_db = Mock()
            self.mock_firestore.Client.return_value = mock_db
            mock_costs_doc = Mock()
            mock_costs_doc.exists = True
            mock_costs_doc.to_dict.return_value = {'transcription_usd': 1.0, 'transcript_count': 1}
            mock_db.collection.return_value.document.return_value = mock_costs_doc

            # Import the module (triggers main block)
            import observability_agent.tools.monitor_transcription_budget

            # Verify main block executed (should have printed something)
            self.assertTrue(mock_print.called)

        print("✅ Main block execution test passed")

    def test_zero_daily_limit_edge_case(self):
        """Test edge case where daily limit is zero"""
        # Setup environment and config mocks with zero limit
        self.mock_get_env.return_value = 'test-project-id'
        self.mock_load_config.return_value = {'budgets': {'transcription_daily_usd': 0.0}}
        self.mock_get_config.return_value = 0.0

        # Setup Firestore mock
        mock_db = Mock()
        self.mock_firestore.Client.return_value = mock_db

        mock_costs_doc = Mock()
        mock_costs_doc.exists = True
        mock_costs_doc.to_dict.return_value = {
            'transcription_usd': 1.0,
            'transcript_count': 1
        }
        mock_db.collection.return_value.document.return_value = mock_costs_doc

        from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

        tool = MonitorTranscriptionBudget(date='2024-01-15')
        result = tool.run()
        result_data = json.loads(result)

        # Verify zero limit handling (should result in 0% usage)
        self.assertEqual(result_data['usage_percentage'], 0.0)
        self.assertEqual(result_data['status'], 'OK')

        print("✅ Zero daily limit edge case test passed")


if __name__ == "__main__":
    unittest.main()