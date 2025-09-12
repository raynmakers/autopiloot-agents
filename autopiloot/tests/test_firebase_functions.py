"""
Integration tests for Firebase Functions using unittest framework.
Tests the scheduling and event-driven functions with proper mocking.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import json

# Add Firebase functions directory to path
firebase_functions_path = os.path.join(os.path.dirname(__file__), '..', 'firebase', 'functions')
sys.path.insert(0, firebase_functions_path)

# Import the functions to test
from main import schedule_scraper_daily, on_transcription_written, _send_slack_alert, _get_firestore_client


class TestScheduledFunction(unittest.TestCase):
    """Test cases for the scheduled scraper function."""
    
    @patch('main._send_slack_alert')
    @patch('main._get_firestore_client')
    def test_schedule_scraper_daily_success(self, mock_firestore, mock_slack):
        """Test successful execution of the scheduled scraper function."""
        # Setup mock Firestore chain
        mock_db = Mock()
        mock_firestore.return_value = mock_db
        
        # Mock the collection chain: db.collection("jobs").document("scraper").collection("daily").document()
        mock_jobs_collection = Mock()
        mock_scraper_doc = Mock()
        mock_daily_collection = Mock()
        mock_final_doc = Mock()
        mock_final_doc.id = "test-job-123"
        
        mock_db.collection.return_value = mock_jobs_collection
        mock_jobs_collection.document.return_value = mock_scraper_doc
        mock_scraper_doc.collection.return_value = mock_daily_collection
        mock_daily_collection.document.return_value = mock_final_doc
        
        # Create mock request
        mock_req = Mock()
        
        # Execute function
        result = schedule_scraper_daily(mock_req)
        
        # Assertions
        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["job_id"], "test-job-123")
        
        # Verify Firestore calls
        mock_db.collection.assert_called_with("jobs")
        mock_jobs_collection.document.assert_called_with("scraper")
        mock_scraper_doc.collection.assert_called_with("daily")
        mock_daily_collection.document.assert_called_once()
        mock_final_doc.set.assert_called_once()
        
        # Verify job data structure
        job_data = mock_final_doc.set.call_args[0][0]
        self.assertEqual(job_data["job_type"], "scraper_daily")
        self.assertEqual(job_data["status"], "queued")
        self.assertEqual(job_data["timezone"], "Europe/Amsterdam")
        self.assertEqual(job_data["source"], "scheduled")
        self.assertIn("config", job_data)
        self.assertEqual(job_data["config"]["handles"], ["@AlexHormozi"])
        
        # Verify Slack notification
        mock_slack.assert_called_once()
        slack_args = mock_slack.call_args[0]
        self.assertIn("successfully", slack_args[0])
    
    @patch('main._send_slack_alert')
    @patch('main._get_firestore_client')
    def test_schedule_scraper_daily_firestore_error(self, mock_firestore, mock_slack):
        """Test error handling when Firestore fails."""
        # Setup mock to raise exception
        mock_firestore.side_effect = Exception("Firestore connection failed")
        
        mock_req = Mock()
        
        # Execute function and expect exception
        with self.assertRaises(Exception) as context:
            schedule_scraper_daily(mock_req)
        
        self.assertIn("Firestore connection failed", str(context.exception))
        
        # Verify error alert was sent
        mock_slack.assert_called_once()
        slack_args = mock_slack.call_args[0]
        self.assertIn("Failed to schedule daily scraper job", slack_args[0])


class TestEventFunction(unittest.TestCase):
    """Test cases for the transcription event function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_event = Mock()
        self.mock_event.params = {"video_id": "test-video-123"}
        
        # Mock transcript data
        self.mock_transcript_data = {
            "created_at": "2025-01-27T10:00:00Z",
            "costs": {
                "transcription_usd": 2.50
            }
        }
        
        self.mock_event.data = Mock()
        self.mock_event.data.to_dict.return_value = self.mock_transcript_data
    
    @patch('main._send_slack_alert')
    @patch('main._get_firestore_client')
    def test_on_transcription_written_success(self, mock_firestore, mock_slack):
        """Test successful processing of transcription event."""
        # Setup mock Firestore
        mock_db = Mock()
        mock_firestore.return_value = mock_db
        
        # Mock transcripts query for daily cost calculation
        mock_query = Mock()
        mock_doc1 = Mock()
        mock_doc1.to_dict.return_value = {"costs": {"transcription_usd": 1.50}}
        mock_doc2 = Mock()
        mock_doc2.to_dict.return_value = {"costs": {"transcription_usd": 2.50}}
        mock_query.stream.return_value = [mock_doc1, mock_doc2]
        
        # Mock query chain
        mock_collection = Mock()
        mock_where1 = Mock()
        mock_where2 = Mock()
        mock_collection.where.return_value = mock_where1
        mock_where1.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        # Mock daily costs document
        mock_daily_costs_ref = Mock()
        mock_daily_costs_doc = Mock()
        mock_daily_costs_doc.exists = False
        mock_daily_costs_ref.get.return_value = mock_daily_costs_doc
        
        # Set up collection call to return different mocks for different collections
        def collection_side_effect(collection_name):
            if collection_name == "transcripts":
                return mock_collection
            elif collection_name == "costs_daily":
                mock_costs_collection = Mock()
                mock_costs_collection.document.return_value = mock_daily_costs_ref
                return mock_costs_collection
            return Mock()
        
        mock_db.collection.side_effect = collection_side_effect
        
        # Execute function
        result = on_transcription_written(self.mock_event)
        
        # Assertions
        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["video_id"], "test-video-123")
        self.assertEqual(result["daily_cost"], 4.0)  # 1.50 + 2.50
        self.assertEqual(result["budget_usage_pct"], 80.0)  # 4.0 / 5.0 * 100
        
        # Verify daily costs update
        mock_daily_costs_ref.set.assert_called()
        daily_costs_data = mock_daily_costs_ref.set.call_args[0][0]
        self.assertEqual(daily_costs_data["transcription_usd_total"], 4.0)
        self.assertEqual(daily_costs_data["transcript_count"], 2)
        
        # Verify budget alert was sent (80% threshold reached)
        mock_slack.assert_called()
        slack_args = mock_slack.call_args[0]
        self.assertIn("budget threshold reached", slack_args[0])
    
    @patch('main._send_slack_alert')
    @patch('main._get_firestore_client')
    def test_on_transcription_written_no_alert_already_sent(self, mock_firestore, mock_slack):
        """Test that no duplicate alert is sent if already sent today."""
        # Setup mock Firestore
        mock_db = Mock()
        mock_firestore.return_value = mock_db
        
        # Mock transcripts query (high cost to trigger alert)
        mock_query = Mock()
        mock_doc1 = Mock()
        mock_doc1.to_dict.return_value = {"costs": {"transcription_usd": 4.5}}
        mock_query.stream.return_value = [mock_doc1]
        
        mock_collection = Mock()
        mock_collection.where.return_value.where.return_value = mock_query
        
        # Mock daily costs document with alert already sent
        mock_daily_costs_ref = Mock()
        mock_daily_costs_doc = Mock()
        mock_daily_costs_doc.exists = True
        mock_daily_costs_doc.to_dict.return_value = {
            "alerts_sent": ["budget_threshold"]  # Alert already sent
        }
        mock_daily_costs_ref.get.return_value = mock_daily_costs_doc
        
        def collection_side_effect(collection_name):
            if collection_name == "transcripts":
                return mock_collection
            elif collection_name == "costs_daily":
                mock_costs_collection = Mock()
                mock_costs_collection.document.return_value = mock_daily_costs_ref
                return mock_costs_collection
            return Mock()
        
        mock_db.collection.side_effect = collection_side_effect
        
        # Execute function
        result = on_transcription_written(self.mock_event)
        
        # Assertions
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["budget_usage_pct"], 90.0)  # 4.5 / 5.0 * 100
        
        # Verify no budget alert was sent (already sent)
        # Only one call should be made (the daily costs update, not the alert)
        mock_daily_costs_ref.set.assert_called()
    
    def test_on_transcription_written_no_video_id(self):
        """Test error handling when video_id is missing."""
        mock_event = Mock()
        mock_event.params = {}  # No video_id
        
        result = on_transcription_written(mock_event)
        
        self.assertEqual(result["status"], "error")
        self.assertIn("video_id", result["message"])
    
    def test_on_transcription_written_no_data(self):
        """Test error handling when event data is missing."""
        mock_event = Mock()
        mock_event.params = {"video_id": "test-video"}
        mock_event.data = None  # No data
        
        result = on_transcription_written(mock_event)
        
        self.assertEqual(result["status"], "error")
        self.assertIn("transcript data", result["message"])


class TestSlackIntegration(unittest.TestCase):
    """Test cases for Slack notification functionality."""
    
    @patch('main.requests.post')
    def test_send_slack_alert_success(self, mock_post):
        """Test successful Slack alert sending."""
        # Setup environment variable
        os.environ["SLACK_BOT_TOKEN"] = "xoxb-test-token"
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "ts": "1234567890.123"}
        mock_post.return_value = mock_response
        
        try:
            # Execute function
            _send_slack_alert("Test message", {"test": "context"})
            
            # Verify API call
            self.assertTrue(mock_post.called)
            call_args = mock_post.call_args
            
            # Check URL
            self.assertEqual(call_args[0][0], "https://slack.com/api/chat.postMessage")
            
            # Check headers
            headers = call_args[1]["headers"]
            self.assertIn("Authorization", headers)
            self.assertIn("xoxb-test-token", headers["Authorization"])
            
            # Check payload
            payload = call_args[1]["json"]
            self.assertEqual(payload["channel"], "#ops-autopiloot")
            self.assertEqual(payload["text"], "Test message")
            self.assertIn("blocks", payload)
            
        finally:
            # Clean up environment
            if "SLACK_BOT_TOKEN" in os.environ:
                del os.environ["SLACK_BOT_TOKEN"]
    
    @patch('main.requests.post')
    def test_send_slack_alert_api_error(self, mock_post):
        """Test handling of Slack API errors."""
        os.environ["SLACK_BOT_TOKEN"] = "xoxb-test-token"
        
        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": False, "error": "channel_not_found"}
        mock_post.return_value = mock_response
        
        try:
            # Execute function (should not raise exception)
            _send_slack_alert("Test message")
            
            # Verify API was called
            self.assertTrue(mock_post.called)
            
        finally:
            if "SLACK_BOT_TOKEN" in os.environ:
                del os.environ["SLACK_BOT_TOKEN"]
    
    def test_send_slack_alert_no_token(self):
        """Test behavior when Slack token is not configured."""
        # Ensure no token is set
        if "SLACK_BOT_TOKEN" in os.environ:
            del os.environ["SLACK_BOT_TOKEN"]
        
        # Execute function (should not raise exception)
        _send_slack_alert("Test message")
        
        # Function should complete without error (logs warning)
        # No assertion needed, just verify no exception is raised


class TestFirestoreClient(unittest.TestCase):
    """Test cases for Firestore client functionality."""
    
    @patch('main.firestore.client')
    def test_get_firestore_client(self, mock_firestore_client):
        """Test Firestore client creation."""
        mock_client = Mock()
        mock_firestore_client.return_value = mock_client
        
        result = _get_firestore_client()
        
        self.assertEqual(result, mock_client)
        mock_firestore_client.assert_called_once()


class TestIntegrationScenarios(unittest.TestCase):
    """Integration test scenarios combining multiple components."""
    
    @patch('main._send_slack_alert')
    @patch('main._get_firestore_client')
    def test_full_budget_monitoring_flow(self, mock_firestore, mock_slack):
        """Test complete budget monitoring flow from transcript write to alert."""
        # Setup test scenario: multiple transcripts throughout the day
        # resulting in budget threshold being exceeded
        
        mock_db = Mock()
        mock_firestore.return_value = mock_db
        
        # Create multiple mock events representing transcripts throughout the day
        events_data = [
            {"video_id": "video-1", "cost": 1.0},
            {"video_id": "video-2", "cost": 1.5},
            {"video_id": "video-3", "cost": 1.5},
            {"video_id": "video-4", "cost": 1.2},  # This should trigger alert (5.2 > 4.0)
        ]
        
        total_cost = 0.0
        
        for i, event_data in enumerate(events_data):
            # Create mock event
            mock_event = Mock()
            mock_event.params = {"video_id": event_data["video_id"]}
            mock_event.data = Mock()
            mock_event.data.to_dict.return_value = {
                "created_at": "2025-01-27T10:00:00Z",
                "costs": {"transcription_usd": event_data["cost"]}
            }
            
            # Update running total
            total_cost += event_data["cost"]
            
            # Mock query to return all transcripts processed so far
            mock_docs = []
            for j in range(i + 1):
                mock_doc = Mock()
                mock_doc.to_dict.return_value = {
                    "costs": {"transcription_usd": events_data[j]["cost"]}
                }
                mock_docs.append(mock_doc)
            
            mock_query = Mock()
            mock_query.stream.return_value = mock_docs
            
            mock_collection = Mock()
            mock_collection.where.return_value.where.return_value = mock_query
            
            # Mock daily costs document
            mock_daily_costs_ref = Mock()
            mock_daily_costs_doc = Mock()
            mock_daily_costs_doc.exists = False  # No alerts sent yet
            mock_daily_costs_ref.get.return_value = mock_daily_costs_doc
            
            def collection_side_effect(collection_name):
                if collection_name == "transcripts":
                    return mock_collection
                elif collection_name == "costs_daily":
                    mock_costs_collection = Mock()
                    mock_costs_collection.document.return_value = mock_daily_costs_ref
                    return mock_costs_collection
                return Mock()
            
            mock_db.collection.side_effect = collection_side_effect
            
            # Execute function
            result = on_transcription_written(mock_event)
            
            # Verify result
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["video_id"], event_data["video_id"])
            self.assertEqual(result["daily_cost"], total_cost)
            
            # Check if alert should be triggered (80% of $5 = $4.00)
            if total_cost >= 4.0:
                # Alert should be sent
                mock_slack.assert_called()
                slack_message = mock_slack.call_args[0][0]
                self.assertIn("budget threshold reached", slack_message)
                break
            else:
                # No alert yet
                mock_slack.assert_not_called()
            
            # Reset mocks for next iteration
            mock_slack.reset_mock()


if __name__ == '__main__':
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)
