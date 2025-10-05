"""
Minimal test for alert_engine.py targeting basic coverage improvements.
Focuses on getting the tool to at least 80% coverage.
"""

import unittest
import os
import sys
import json
import importlib.util
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta


class TestAlertEngineMinimalCoverage(unittest.TestCase):
    """Minimal test targeting basic coverage for alert_engine.py."""

    def setUp(self):
        """Set up test environment"""
        # Get the module path
        module_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..',
            'observability_agent', 'tools',
            'alert_engine.py'
        )
        self.module_path = os.path.abspath(module_path)

        # Comprehensive mock modules
        self.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google': MagicMock(),
            'google.cloud': MagicMock(),
            'google.cloud.firestore': MagicMock(),
            'slack_sdk': MagicMock(),
            'slack_sdk.web': MagicMock(),
            'dotenv': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'audit_logger': MagicMock(),
        }

        # Setup standard mocks
        self.mock_modules['pydantic'].Field = lambda *args, **kwargs: kwargs.get('default', None)

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        self.mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool
        self.mock_modules['dotenv'].load_dotenv = Mock()

    def test_basic_exception_handling(self):
        """Test basic exception handling in run method."""
        # Setup environment mocks to cause failure
        self.mock_modules['env_loader'].get_required_env_var = Mock(
            side_effect=Exception("Environment setup failed")
        )

        with patch.dict('sys.modules', self.mock_modules):
            # Import module with mocks in place
            spec = importlib.util.spec_from_file_location('alert_engine', self.module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_class = module.AlertEngine

            tool = tool_class(
                alert_type="quota_threshold",
                severity="warning",
                message="Test message"
            )

            result = tool.run()
            result_data = json.loads(result)

            # Should handle exception gracefully
            self.assertIn("error", result_data)
            self.assertEqual(result_data["status"], "error")
            self.assertIn("Failed to process alert", result_data["error"])

    def test_alert_fingerprint_generation(self):
        """Test alert fingerprint generation method."""
        # Setup basic mocks
        self.mock_modules['env_loader'].get_required_env_var = Mock(return_value="test-value")

        with patch.dict('sys.modules', self.mock_modules):
            # Import module with mocks in place
            spec = importlib.util.spec_from_file_location('alert_engine', self.module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_class = module.AlertEngine

            tool = tool_class(
                alert_type="quota_threshold",
                severity="warning",
                message="Test message",
                details={"quota_type": "youtube_api", "service": "transcriber"},
                source_component="quota_monitor"
            )

            # Test fingerprint generation
            fingerprint = tool._generate_alert_fingerprint()

            # Should return a hash string
            self.assertIsInstance(fingerprint, str)
            self.assertEqual(len(fingerprint), 12)  # MD5 hash truncated to 12 chars

    def test_throttle_window_calculation(self):
        """Test throttle window calculation."""
        # Setup configuration mocks
        self.mock_modules['env_loader'].get_required_env_var = Mock(return_value="test-value")
        self.mock_modules['loader'].load_app_config = Mock(return_value={
            'notifications': {
                'alert_throttling': {
                    'default_throttle_minutes': 90
                }
            }
        })

        with patch.dict('sys.modules', self.mock_modules):
            # Import module with mocks in place
            spec = importlib.util.spec_from_file_location('alert_engine', self.module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_class = module.AlertEngine

            tool = tool_class(
                alert_type="quota_threshold",
                severity="warning",
                message="Test message"
            )

            # Test throttle window calculation
            window = tool._get_throttle_window()
            self.assertEqual(window, 90)

    def test_severity_interval_calculation(self):
        """Test severity interval calculation for different severity levels."""
        # Setup configuration mocks
        self.mock_modules['env_loader'].get_required_env_var = Mock(return_value="test-value")
        self.mock_modules['loader'].load_app_config = Mock(return_value={
            'notifications': {
                'alert_throttling': {
                    'severity_intervals': {
                        'critical': 5,
                        'error': 15,
                        'warning': 30,
                        'info': 60
                    }
                }
            }
        })

        with patch.dict('sys.modules', self.mock_modules):
            # Import module with mocks in place
            spec = importlib.util.spec_from_file_location('alert_engine', self.module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_class = module.AlertEngine

            # Test different severity levels
            severities = [
                ("critical", 5),
                ("error", 15),
                ("warning", 30),
                ("info", 60)
            ]

            for severity, expected_interval in severities:
                with self.subTest(severity=severity):
                    tool = tool_class(
                        alert_type="system_error",
                        severity=severity,
                        message=f"Test {severity} message"
                    )

                    interval = tool._get_min_interval_for_severity()
                    self.assertEqual(interval, expected_interval)

    def test_no_throttling_scenario(self):
        """Test scenario where no throttling should occur."""
        # Setup mocks for successful processing
        self.mock_modules['env_loader'].get_required_env_var = Mock(side_effect=lambda var, desc: {
            'GCP_PROJECT_ID': 'test-project-id',
            'SLACK_BOT_TOKEN': 'xoxb-test-token'
        }.get(var, 'test-value'))

        self.mock_modules['loader'].load_app_config = Mock(return_value={
            'notifications': {
                'alert_throttling': {
                    'default_throttle_minutes': 60,
                    'severity_intervals': {'warning': 30}
                }
            }
        })

        # Setup audit logger
        mock_audit_logger = Mock()
        mock_audit_logger.log_alert_processed = Mock(return_value=True)
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

        # Setup Firestore mock (no recent alerts)
        mock_db = Mock()
        mock_collection = Mock()
        mock_query = Mock()
        mock_doc_ref = Mock()

        mock_query.stream.return_value = []  # No recent alerts
        mock_collection.where.return_value.where.return_value.limit.return_value = mock_query
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db)

        # Setup Slack mock
        mock_slack_client = Mock()
        mock_slack_response = Mock()
        mock_slack_response.data = {"ok": True, "ts": "1234567890.123456"}
        mock_slack_client.chat_postMessage.return_value = mock_slack_response
        self.mock_modules['slack_sdk.web'].WebClient = Mock(return_value=mock_slack_client)

        with patch.dict('sys.modules', self.mock_modules):
            # Import module with mocks in place
            spec = importlib.util.spec_from_file_location('alert_engine', self.module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_class = module.AlertEngine

            # Mock the _initialize_firestore method to avoid real connections
            with patch.object(tool_class, '_initialize_firestore', return_value=mock_db):
                tool = tool_class(
                    alert_type="quota_threshold",
                    severity="warning",
                    message="Test quota alert message",
                    details={"quota_type": "youtube_api", "usage_percentage": 85},
                    source_component="quota_monitor"
                )

                result = tool.run()
                result_data = json.loads(result)

                # Should process successfully (no throttling)
                self.assertEqual(result_data["status"], "processed")
                self.assertIn("alert_id", result_data)

    def test_throttling_scenario(self):
        """Test scenario where throttling should occur."""
        # Setup mocks
        self.mock_modules['env_loader'].get_required_env_var = Mock(return_value="test-value")
        self.mock_modules['loader'].load_app_config = Mock(return_value={
            'notifications': {
                'alert_throttling': {
                    'severity_intervals': {'warning': 30}
                }
            }
        })

        # Setup Firestore mock with recent alert
        mock_db = Mock()
        mock_collection = Mock()
        mock_query = Mock()

        # Mock recent alert record (10 minutes ago, should throttle for 30 min interval)
        mock_alert_doc = Mock()
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        mock_alert_doc.to_dict.return_value = {
            "last_sent": recent_time,
            "send_count": 1,
            "alert_fingerprint": "test123"
        }

        mock_query.stream.return_value = [mock_alert_doc]
        mock_collection.where.return_value.where.return_value.limit.return_value = mock_query
        mock_db.collection.return_value = mock_collection

        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db)

        with patch.dict('sys.modules', self.mock_modules):
            # Import module with mocks in place
            spec = importlib.util.spec_from_file_location('alert_engine', self.module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_class = module.AlertEngine

            with patch.object(tool_class, '_initialize_firestore', return_value=mock_db):
                tool = tool_class(
                    alert_type="quota_threshold",
                    severity="warning",
                    message="Test quota alert",
                    source_component="quota_monitor"
                )

                result = tool.run()
                result_data = json.loads(result)

                # Should be throttled
                self.assertEqual(result_data["status"], "throttled")
                self.assertIn("reason", result_data)
                self.assertFalse(result_data["delivery_attempted"])


if __name__ == '__main__':
    unittest.main()