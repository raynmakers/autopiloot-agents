"""
Test suite for MonitorTranscriptionBudget tool.
Tests TASK-AST-0040 implementation including 80% threshold alerting, Slack notifications, and budget calculations.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timezone
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'observability_agent', 
        'tools', 
        'monitor_transcription_budget.py'
    )
    spec = importlib.util.spec_from_file_location("MonitorTranscriptionBudget", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    MonitorTranscriptionBudget = module.MonitorTranscriptionBudget


class TestMonitorTranscriptionBudget(unittest.TestCase):
    """Test cases for MonitorTranscriptionBudget tool TASK-AST-0040."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_date = "2025-09-15"
        self.mock_config = {
            "budgets": {"transcription_daily_usd": 5.0},
            "notifications": {"slack": {"channel": "ops-autopiloot"}}
        }

    @patch('observability_agent.tools.monitor_transcription_budget.get_required_env_var')
    @patch('observability_agent.tools.monitor_transcription_budget.load_app_config')
    @patch('observability_agent.tools.monitor_transcription_budget.firestore.Client')
    def test_budget_ok_status(self, mock_firestore, mock_config, mock_env):
        """Test budget monitoring when usage is below 70% (OK status)."""
        # Mock environment and configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock costs_daily document (40% usage: $2.00 of $5.00)
        mock_costs_doc = MagicMock()
        mock_costs_doc.exists = True
        mock_costs_doc.to_dict.return_value = {
            "transcription_usd": 2.0,
            "transcript_count": 3
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_costs_doc
        
        tool = MonitorTranscriptionBudget(date=self.test_date)
        result = tool.run()
        data = json.loads(result)
        
        # Verify OK status and no alert
        self.assertEqual(data["status"], "OK")
        self.assertEqual(data["total_usd"], 2.0)
        self.assertEqual(data["usage_percentage"], 40.0)
        self.assertFalse(data["alert_sent"])
        
        print("✅ Budget OK status test passed")

    @patch('observability_agent.tools.monitor_transcription_budget.get_required_env_var')
    @patch('observability_agent.tools.monitor_transcription_budget.load_app_config')
    @patch('observability_agent.tools.monitor_transcription_budget.firestore.Client')
    def test_budget_warning_status_no_alert(self, mock_firestore, mock_config, mock_env):
        """Test budget monitoring when usage is 70-79% (WARNING status, no alert)."""
        # Mock environment and configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock costs_daily document (75% usage: $3.75 of $5.00)
        mock_costs_doc = MagicMock()
        mock_costs_doc.exists = True
        mock_costs_doc.to_dict.return_value = {
            "transcription_usd": 3.75,
            "transcript_count": 5
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_costs_doc
        
        tool = MonitorTranscriptionBudget(date=self.test_date)
        result = tool.run()
        data = json.loads(result)
        
        # Verify WARNING status and no alert (below 80% threshold)
        self.assertEqual(data["status"], "WARNING")
        self.assertEqual(data["total_usd"], 3.75)
        self.assertEqual(data["usage_percentage"], 75.0)
        self.assertFalse(data["alert_sent"])
        
        print("✅ Budget WARNING status (no alert) test passed")

    @patch('observability_agent.tools.monitor_transcription_budget.get_required_env_var')
    @patch('observability_agent.tools.monitor_transcription_budget.load_app_config')
    @patch('observability_agent.tools.monitor_transcription_budget.firestore.Client')
    def test_budget_threshold_reached_with_alert(self, mock_firestore, mock_config, mock_env):
        """Test budget monitoring when 80% threshold is reached (should send alert)."""
        # Mock environment and configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock costs_daily document (85% usage: $4.25 of $5.00)
        mock_costs_doc = MagicMock()
        mock_costs_doc.exists = True
        mock_costs_doc.to_dict.return_value = {
            "transcription_usd": 4.25,
            "transcript_count": 6
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_costs_doc
        
        # Mock alert sending to return success
        with patch.object(MonitorTranscriptionBudget, '_send_budget_alert', return_value=True):
            tool = MonitorTranscriptionBudget(date=self.test_date)
            result = tool.run()
            data = json.loads(result)
        
        # Verify THRESHOLD_REACHED status and alert sent
        self.assertEqual(data["status"], "THRESHOLD_REACHED")
        self.assertEqual(data["total_usd"], 4.25)
        self.assertEqual(data["usage_percentage"], 85.0)
        self.assertTrue(data["alert_sent"])
        
        print("✅ Budget threshold reached with alert test passed")

    @patch('observability_agent.tools.monitor_transcription_budget.get_required_env_var')
    @patch('observability_agent.tools.monitor_transcription_budget.load_app_config')
    @patch('observability_agent.tools.monitor_transcription_budget.firestore.Client')
    def test_budget_exceeded_status(self, mock_firestore, mock_config, mock_env):
        """Test budget monitoring when usage exceeds 100%."""
        # Mock environment and configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock costs_daily document (110% usage: $5.50 of $5.00)
        mock_costs_doc = MagicMock()
        mock_costs_doc.exists = True
        mock_costs_doc.to_dict.return_value = {
            "transcription_usd": 5.50,
            "transcript_count": 8
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_costs_doc
        
        # Mock alert sending
        with patch.object(MonitorTranscriptionBudget, '_send_budget_alert', return_value=True):
            tool = MonitorTranscriptionBudget(date=self.test_date)
            result = tool.run()
            data = json.loads(result)
        
        # Verify EXCEEDED status
        self.assertEqual(data["status"], "EXCEEDED")
        self.assertEqual(data["total_usd"], 5.5)
        self.assertEqual(data["usage_percentage"], 110.0)
        self.assertTrue(data["alert_sent"])
        
        print("✅ Budget exceeded status test passed")

    @patch('observability_agent.tools.monitor_transcription_budget.get_required_env_var')
    @patch('observability_agent.tools.monitor_transcription_budget.load_app_config')
    @patch('observability_agent.tools.monitor_transcription_budget.firestore.Client')
    def test_fallback_to_transcripts_collection(self, mock_firestore, mock_config, mock_env):
        """Test fallback to transcripts collection when costs_daily doesn't exist."""
        # Mock environment and configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        # Mock costs_daily document doesn't exist
        mock_costs_doc = MagicMock()
        mock_costs_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_costs_doc
        
        # Mock transcripts collection query
        mock_transcript1 = MagicMock()
        mock_transcript1.to_dict.return_value = {
            "costs": {"transcription_usd": 1.5}
        }
        mock_transcript2 = MagicMock()
        mock_transcript2.to_dict.return_value = {
            "costs": {"transcription_usd": 2.0}
        }
        
        mock_transcripts_ref = MagicMock()
        mock_transcripts_ref.where.return_value.where.return_value.stream.return_value = [
            mock_transcript1, mock_transcript2
        ]
        mock_db.collection.return_value = mock_transcripts_ref
        
        tool = MonitorTranscriptionBudget(date=self.test_date)
        result = tool.run()
        data = json.loads(result)
        
        # Verify calculation from transcripts collection
        self.assertEqual(data["total_usd"], 3.5)
        self.assertEqual(data["transcript_count"], 2)
        self.assertEqual(data["usage_percentage"], 70.0)
        
        print("✅ Fallback to transcripts collection test passed")

    @patch('observability_agent.tools.monitor_transcription_budget.get_required_env_var')
    @patch('observability_agent.tools.monitor_transcription_budget.load_app_config')
    def test_invalid_date_format(self, mock_config, mock_env):
        """Test error handling for invalid date format."""
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        tool = MonitorTranscriptionBudget(date="invalid-date")
        result = tool.run()
        data = json.loads(result)
        
        # Should return error response
        self.assertIn("error", data)
        self.assertIn("Invalid date format", data["error"])
        self.assertEqual(data["status"], "ERROR")
        
        print("✅ Invalid date format test passed")

    @patch('observability_agent.tools.monitor_transcription_budget.get_required_env_var')
    def test_missing_environment_variable(self, mock_env):
        """Test error handling when environment variable is missing."""
        mock_env.side_effect = ValueError("GCP_PROJECT_ID environment variable is required")
        
        tool = MonitorTranscriptionBudget(date=self.test_date)
        result = tool.run()
        data = json.loads(result)
        
        # Should return error response
        self.assertIn("error", data)
        self.assertIn("GCP_PROJECT_ID", data["error"])
        
        print("✅ Missing environment variable test passed")

    @patch('observability_agent.tools.monitor_transcription_budget.get_required_env_var')
    @patch('observability_agent.tools.monitor_transcription_budget.load_app_config')
    @patch('observability_agent.tools.monitor_transcription_budget.firestore.Client')
    def test_firestore_connection_error(self, mock_firestore, mock_config, mock_env):
        """Test error handling when Firestore connection fails."""
        # Mock environment and configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = self.mock_config
        
        # Mock Firestore client to raise exception
        mock_firestore.side_effect = Exception("Firestore connection failed")
        
        tool = MonitorTranscriptionBudget(date=self.test_date)
        result = tool.run()
        data = json.loads(result)
        
        # Should return error response
        self.assertIn("error", data)
        self.assertIn("Firestore connection failed", data["error"])
        
        print("✅ Firestore connection error test passed")

    @patch('observability_agent.tools.monitor_transcription_budget.get_required_env_var')
    @patch('observability_agent.tools.monitor_transcription_budget.load_app_config')
    @patch('observability_agent.tools.monitor_transcription_budget.firestore.Client')
    def test_budget_configuration_fallback(self, mock_firestore, mock_config, mock_env):
        """Test fallback to default budget when configuration is missing."""
        # Mock environment and missing budget configuration
        mock_env.return_value = "test-project"
        mock_config.return_value = {}  # No budget configuration
        
        # Mock Firestore client with zero costs
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_costs_doc = MagicMock()
        mock_costs_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_costs_doc
        
        # Mock empty transcripts collection
        mock_transcripts_ref = MagicMock()
        mock_transcripts_ref.where.return_value.where.return_value.stream.return_value = []
        mock_db.collection.return_value = mock_transcripts_ref
        
        tool = MonitorTranscriptionBudget(date=self.test_date)
        result = tool.run()
        data = json.loads(result)
        
        # Should use default budget limit of 5.0
        self.assertEqual(data["daily_limit"], 5.0)
        
        print("✅ Budget configuration fallback test passed")

    def test_send_budget_alert_integration(self):
        """Test _send_budget_alert method integration."""
        with patch('observability_agent.tools.monitor_transcription_budget.get_required_env_var') as mock_env, \
             patch('observability_agent.tools.monitor_transcription_budget.load_app_config') as mock_config:
            
            mock_env.return_value = "test-project"
            mock_config.return_value = self.mock_config
            
            tool = MonitorTranscriptionBudget(date=self.test_date)
            
            # Mock the FormatSlackBlocks and SendSlackMessage tools
            with patch('observability_agent.tools.monitor_transcription_budget.FormatSlackBlocks') as mock_formatter, \
                 patch('observability_agent.tools.monitor_transcription_budget.SendSlackMessage') as mock_messenger:
                
                # Mock formatter response
                mock_formatter.return_value.run.return_value = json.dumps({
                    "blocks": [{"type": "header", "text": {"type": "plain_text", "text": "Budget Alert"}}]
                })
                
                # Mock messenger response
                mock_messenger.return_value.run.return_value = json.dumps({
                    "ts": "1234567890.123",
                    "channel": "#ops-autopiloot"
                })
                
                # Test alert sending
                result = tool._send_budget_alert(4.0, 5.0, 80.0, self.test_date)
                self.assertTrue(result)
                
                # Verify tools were called
                mock_formatter.assert_called_once()
                mock_messenger.assert_called_once()
        
        print("✅ Send budget alert integration test passed")

    def test_response_structure_compliance(self):
        """Test that response structure matches BudgetMonitorResponse TypedDict."""
        with patch('observability_agent.tools.monitor_transcription_budget.get_required_env_var') as mock_env, \
             patch('observability_agent.tools.monitor_transcription_budget.load_app_config') as mock_config, \
             patch('observability_agent.tools.monitor_transcription_budget.firestore.Client') as mock_firestore:
            
            # Mock successful response
            mock_env.return_value = "test-project"
            mock_config.return_value = self.mock_config
            
            mock_db = MagicMock()
            mock_firestore.return_value = mock_db
            mock_costs_doc = MagicMock()
            mock_costs_doc.exists = True
            mock_costs_doc.to_dict.return_value = {"transcription_usd": 2.0, "transcript_count": 3}
            mock_db.collection.return_value.document.return_value.get.return_value = mock_costs_doc
            
            tool = MonitorTranscriptionBudget(date=self.test_date)
            result = tool.run()
            data = json.loads(result)
            
            # Verify required fields from BudgetMonitorResponse TypedDict
            self.assertIn("status", data)
            self.assertIn("total_usd", data)
            self.assertIsInstance(data["status"], str)
            self.assertIsInstance(data["total_usd"], (int, float))
            
        print("✅ Response structure compliance test passed")


if __name__ == '__main__':
    unittest.main()