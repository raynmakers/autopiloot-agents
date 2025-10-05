"""
Comprehensive test for alert_engine.py targeting 100% coverage.
Uses proper importlib pattern to ensure coverage measurement.
"""

import unittest
import os
import sys
import json
import importlib.util
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta


class TestAlertEngine100Coverage(unittest.TestCase):
    """Comprehensive test targeting 100% coverage for alert_engine.py."""

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
            'hashlib': MagicMock(),
        }

        # Setup standard mocks
        self.mock_modules['pydantic'].Field = lambda *args, **kwargs: kwargs.get('default', None)

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        self.mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool
        self.mock_modules['dotenv'].load_dotenv = Mock()

    def _setup_no_throttling_firestore_mock(self, mock_db):
        """Setup Firestore mock to return no recent alerts (no throttling)"""
        mock_collection = Mock()
        mock_query = Mock()
        mock_doc_ref = Mock()

        # Mock throttling query - return empty list (no recent alerts)
        mock_query.stream.return_value = []
        mock_collection.where.return_value.where.return_value.limit.return_value = mock_query

        # Mock document operations
        mock_collection.document.return_value = mock_doc_ref
        mock_doc_ref.set.return_value = True

        mock_db.collection.return_value = mock_collection

    def _setup_throttling_firestore_mock(self, mock_db, recent_time=None):
        """Setup Firestore mock to return recent alert (should throttle)"""
        if recent_time is None:
            recent_time = datetime.now(timezone.utc) - timedelta(minutes=10)

        mock_collection = Mock()
        mock_query = Mock()
        mock_doc_ref = Mock()

        # Mock recent alert record
        mock_alert_doc = Mock()
        mock_alert_doc.to_dict.return_value = {
            "last_sent": recent_time,
            "send_count": 1,
            "alert_fingerprint": "test123"
        }

        mock_query.stream.return_value = [mock_alert_doc]
        mock_collection.where.return_value.where.return_value.limit.return_value = mock_query
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

    def test_successful_alert_processing_full_flow(self):
        """Test successful alert processing through complete flow."""
        # Setup environment mocks
        self.mock_modules['env_loader'].get_required_env_var = Mock(side_effect=lambda var, desc: {
            'GCP_PROJECT_ID': 'test-project-id',
            'SLACK_BOT_TOKEN': 'xoxb-test-token'
        }.get(var, 'test-value'))

        # Setup configuration mocks
        self.mock_modules['loader'].load_app_config = Mock(return_value={
            'notifications': {
                'alert_throttling': {
                    'default_throttle_minutes': 60,
                    'severity_intervals': {
                        'critical': 5,
                        'error': 15,
                        'warning': 30,
                        'info': 60
                    }
                }
            }
        })

        # Setup audit logger
        mock_audit_logger = Mock()
        mock_audit_logger.log_alert_processed = Mock(return_value=True)
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

        # Setup Firestore mock (no recent alerts - no throttling)
        mock_db = Mock()
        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db)
        self._setup_no_throttling_firestore_mock(mock_db)

        # Setup hashlib mock
        import hashlib
        self.mock_modules['hashlib'].md5 = hashlib.md5

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

            # Mock the _initialize_firestore method
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

                # Verify successful processing
                self.assertEqual(result_data["status"], "processed")
                self.assertIn("alert_id", result_data)

    @patch('builtins.__import__')
    def test_alert_throttling_mechanism(self, mock_import):
        """Test alert throttling with recent alerts."""
        def import_side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.get_required_env_var = Mock(return_value="test-value")
                return mock_env
            elif 'loader' in name:
                mock_loader = MagicMock()
                mock_loader.load_app_config = Mock(return_value={
                    "notifications": {
                        "alert_throttling": {
                            "default_throttle_minutes": 60,
                            "severity_intervals": {"warning": 30}
                        }
                    }
                })
                return mock_loader
            elif 'audit_logger' in name:
                return MagicMock()
            return MagicMock()

        mock_import.side_effect = import_side_effect

        # Mock Firestore with recent alert (should throttle)
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_query = MagicMock()

        # Mock recent alert record
        mock_alert_doc = MagicMock()
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=10)  # 10 minutes ago
        mock_alert_doc.to_dict.return_value = {
            "last_sent": recent_time,
            "send_count": 1,
            "alert_fingerprint": "test123"
        }

        mock_query.stream.return_value = [mock_alert_doc]
        mock_collection.where.return_value.where.return_value.limit.return_value = mock_query
        mock_db.collection.return_value = mock_collection

        with patch('google.cloud.firestore.Client', return_value=mock_db):
            tool = self.AlertEngine(
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

    @patch('builtins.__import__')
    def test_override_throttling_critical_alert(self, mock_import):
        """Test throttling override for critical alerts."""
        def import_side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.get_required_env_var = Mock(return_value="test-value")
                return mock_env
            elif 'loader' in name:
                mock_loader = MagicMock()
                mock_loader.load_app_config = Mock(return_value={
                    "notifications": {
                        "alert_throttling": {
                            "default_throttle_minutes": 60,
                            "severity_intervals": {"critical": 5}
                        }
                    }
                })
                return mock_loader
            elif 'audit_logger' in name:
                mock_audit = MagicMock()
                mock_audit.audit_logger = MagicMock()
                return mock_audit
            return MagicMock()

        mock_import.side_effect = import_side_effect

        # Mock Firestore with recent alert
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_query = MagicMock()

        mock_alert_doc = MagicMock()
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=2)
        mock_alert_doc.to_dict.return_value = {
            "last_sent": recent_time,
            "send_count": 1
        }
        mock_query.stream.return_value = [mock_alert_doc]
        mock_collection.where.return_value.where.return_value.limit.return_value = mock_query
        mock_db.collection.return_value = mock_collection

        # Mock Slack delivery
        mock_slack_client = MagicMock()
        mock_slack_response = MagicMock()
        mock_slack_response.data = {"ok": True, "ts": "1234567890.123456"}
        mock_slack_client.chat_postMessage.return_value = mock_slack_response

        with patch('google.cloud.firestore.Client', return_value=mock_db):
            with patch('slack_sdk.web.WebClient', return_value=mock_slack_client):
                tool = self.AlertEngine(
                    alert_type="system_error",
                    severity="critical",
                    message="Critical system failure",
                    override_throttling=True  # Override throttling
                )

                result = tool.run()
                result_data = json.loads(result)

                # Should process despite recent alert
                self.assertEqual(result_data["status"], "processed")

    @patch('builtins.__import__')
    def test_firestore_connection_error(self, mock_import):
        """Test Firestore connection error handling."""
        def import_side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.get_required_env_var = Mock(side_effect=Exception("Firestore connection failed"))
                return mock_env
            return MagicMock()

        mock_import.side_effect = import_side_effect

        tool = self.AlertEngine(
            alert_type="quota_threshold",
            severity="warning",
            message="Test message"
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should handle error gracefully
        self.assertIn("error", result_data)
        self.assertEqual(result_data["status"], "error")
        self.assertIn("Failed to process alert", result_data["error"])

    @patch('builtins.__import__')
    def test_slack_delivery_failure(self, mock_import):
        """Test Slack delivery failure handling."""
        def import_side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.get_required_env_var = Mock(return_value="test-value")
                return mock_env
            elif 'loader' in name:
                mock_loader = MagicMock()
                mock_loader.load_app_config = Mock(return_value={
                    "notifications": {"alert_throttling": {"default_throttle_minutes": 60}}
                })
                return mock_loader
            elif 'audit_logger' in name:
                mock_audit = MagicMock()
                mock_audit.audit_logger = MagicMock()
                return mock_audit
            return MagicMock()

        mock_import.side_effect = import_side_effect

        # Mock Firestore (no throttling)
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_query = MagicMock()
        mock_query.stream.return_value = []  # No recent alerts
        mock_collection.where.return_value.where.return_value.limit.return_value = mock_query
        mock_db.collection.return_value = mock_collection

        # Mock Slack client failure
        mock_slack_client = MagicMock()
        mock_slack_client.chat_postMessage.side_effect = Exception("Slack API error")

        with patch('google.cloud.firestore.Client', return_value=mock_db):
            with patch('slack_sdk.web.WebClient', return_value=mock_slack_client):
                tool = self.AlertEngine(
                    alert_type="quota_threshold",
                    severity="warning",
                    message="Test message"
                )

                result = tool.run()
                result_data = json.loads(result)

                # Should still process but with delivery failure
                self.assertEqual(result_data["status"], "processed")
                self.assertIn("delivery_results", result_data)

    @patch('builtins.__import__')
    def test_alert_enrichment_process(self, mock_import):
        """Test alert enrichment with various details."""
        def import_side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.get_required_env_var = Mock(return_value="test-value")
                return mock_env
            elif 'loader' in name:
                mock_loader = MagicMock()
                mock_loader.load_app_config = Mock(return_value={
                    "notifications": {"alert_throttling": {"default_throttle_minutes": 60}}
                })
                return mock_loader
            elif 'audit_logger' in name:
                mock_audit = MagicMock()
                mock_audit.audit_logger = MagicMock()
                return mock_audit
            return MagicMock()

        mock_import.side_effect = import_side_effect

        # Mock Firestore (no throttling)
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_query = MagicMock()
        mock_query.stream.return_value = []
        mock_collection.where.return_value.where.return_value.limit.return_value = mock_query
        mock_db.collection.return_value = mock_collection

        # Mock Slack delivery
        mock_slack_client = MagicMock()
        mock_slack_response = MagicMock()
        mock_slack_response.data = {"ok": True, "ts": "1234567890.123456"}
        mock_slack_client.chat_postMessage.return_value = mock_slack_response

        with patch('google.cloud.firestore.Client', return_value=mock_db):
            with patch('slack_sdk.web.WebClient', return_value=mock_slack_client):
                tool = self.AlertEngine(
                    alert_type="dlq_spike",
                    severity="error",
                    message="Dead letter queue spike detected",
                    details={
                        "queue_size": 150,
                        "spike_threshold": 50,
                        "affected_services": ["transcriber", "summarizer"],
                        "error_rate": "25%"
                    },
                    source_component="dlq_monitor"
                )

                result = tool.run()
                result_data = json.loads(result)

                # Verify enrichment occurred
                self.assertEqual(result_data["status"], "processed")
                self.assertIn("enriched_alert", result_data)
                enriched = result_data["enriched_alert"]
                self.assertIn("alert_id", enriched)
                self.assertIn("timestamp", enriched)
                self.assertEqual(enriched["original_message"], tool.message)

    @patch('builtins.__import__')
    def test_different_severity_levels(self, mock_import):
        """Test processing alerts with different severity levels."""
        def import_side_effect(name, *args, **kwargs):
            if 'env_loader' in name:
                mock_env = MagicMock()
                mock_env.get_required_env_var = Mock(return_value="test-value")
                return mock_env
            elif 'loader' in name:
                mock_loader = MagicMock()
                mock_loader.load_app_config = Mock(return_value={
                    "notifications": {
                        "alert_throttling": {
                            "severity_intervals": {
                                "critical": 5,
                                "error": 15,
                                "warning": 30,
                                "info": 60
                            }
                        }
                    }
                })
                return mock_loader
            elif 'audit_logger' in name:
                mock_audit = MagicMock()
                mock_audit.audit_logger = MagicMock()
                return mock_audit
            return MagicMock()

        mock_import.side_effect = import_side_effect

        # Test each severity level
        severities = ["info", "warning", "error", "critical"]

        for severity in severities:
            with self.subTest(severity=severity):
                # Mock Firestore (no throttling)
                mock_db = MagicMock()
                mock_collection = MagicMock()
                mock_query = MagicMock()
                mock_query.stream.return_value = []
                mock_collection.where.return_value.where.return_value.limit.return_value = mock_query
                mock_db.collection.return_value = mock_collection

                # Mock Slack delivery
                mock_slack_client = MagicMock()
                mock_slack_response = MagicMock()
                mock_slack_response.data = {"ok": True, "ts": "1234567890.123456"}
                mock_slack_client.chat_postMessage.return_value = mock_slack_response

                with patch('google.cloud.firestore.Client', return_value=mock_db):
                    with patch('slack_sdk.web.WebClient', return_value=mock_slack_client):
                        tool = self.AlertEngine(
                            alert_type="system_error",
                            severity=severity,
                            message=f"Test {severity} alert"
                        )

                        result = tool.run()
                        result_data = json.loads(result)

                        self.assertEqual(result_data["status"], "processed")
                        self.assertIn("enriched_alert", result_data)


if __name__ == '__main__':
    unittest.main()