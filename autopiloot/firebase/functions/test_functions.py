#!/usr/bin/env python3
"""
Test script for Firebase Functions.

This script provides local testing capabilities for the Firebase Functions
without requiring deployment to the cloud.
"""

import os
import sys
import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch

# Add the functions directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from main import schedule_scraper_daily, on_transcription_written

def test_schedule_scraper_daily():
    """Test the scheduled scraper function."""
    print("Testing schedule_scraper_daily function...")
    
    # Mock Firestore client
    with patch('main._get_firestore_client') as mock_firestore, \
         patch('main._send_slack_alert') as mock_slack:
        
        # Setup mock Firestore chain: db.collection().document().collection().document()
        mock_db = Mock()
        mock_firestore.return_value = mock_db
        
        # Mock the collection chain
        mock_jobs_collection = Mock()
        mock_scraper_doc = Mock()
        mock_daily_collection = Mock()
        mock_final_doc = Mock()
        mock_final_doc.id = "test-job-123"
        
        # Set up the chain: db.collection("jobs").document("scraper").collection("daily").document()
        mock_db.collection.return_value = mock_jobs_collection
        mock_jobs_collection.document.return_value = mock_scraper_doc
        mock_scraper_doc.collection.return_value = mock_daily_collection
        mock_daily_collection.document.return_value = mock_final_doc
        
        # Create mock request
        mock_req = Mock()
        
        # Execute function
        try:
            result = schedule_scraper_daily(mock_req)
            print(f"✅ Function executed successfully: {result}")
            
            # Verify Firestore write was called
            assert mock_final_doc.set.called
            
            # Verify Slack alert was sent
            assert mock_slack.called
            
            print("✅ All assertions passed")
            
        except Exception as e:
            print(f"❌ Function failed: {e}")
            return False
    
    return True

def test_on_transcription_written():
    """Test the transcription event function."""
    print("\nTesting on_transcription_written function...")
    
    # Mock event data
    mock_event = Mock()
    mock_event.params = {"video_id": "test-video-123"}
    
    # Mock transcript data
    mock_transcript_data = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "costs": {
            "transcription_usd": 2.50
        }
    }
    
    # Set up event.data mock properly
    mock_event.data = Mock()
    mock_event.data.to_dict.return_value = mock_transcript_data
    
    # Mock Firestore client
    with patch('main._get_firestore_client') as mock_firestore, \
         patch('main._send_slack_alert') as mock_slack:
        
        # Setup mock Firestore responses
        mock_db = Mock()
        mock_firestore.return_value = mock_db
        
        # Mock transcripts query (for daily cost calculation)
        mock_query = Mock()
        mock_doc1 = Mock()
        mock_doc1.to_dict.return_value = {"costs": {"transcription_usd": 1.50}}
        mock_doc2 = Mock()
        mock_doc2.to_dict.return_value = {"costs": {"transcription_usd": 2.50}}
        mock_query.stream.return_value = [mock_doc1, mock_doc2]
        
        mock_db.collection.return_value.where.return_value.where.return_value = mock_query
        
        # Mock daily costs document
        mock_daily_costs_ref = Mock()
        mock_daily_costs_doc = Mock()
        mock_daily_costs_doc.exists = False
        mock_daily_costs_ref.get.return_value = mock_daily_costs_doc
        mock_db.collection.return_value.document.return_value = mock_daily_costs_ref
        
        # Execute function
        try:
            result = on_transcription_written(mock_event)
            print(f"✅ Function executed successfully: {result}")
            
            # Verify daily costs update was called
            assert mock_daily_costs_ref.set.called
            
            # Check if budget alert should be sent (4.00 / 5.00 = 80%)
            expected_usage = 80.0  # Should trigger alert
            if result["budget_usage_pct"] >= 80:
                print("✅ Budget threshold reached, alert should be sent")
            
            print("✅ All assertions passed")
            
        except Exception as e:
            print(f"❌ Function failed: {e}")
            return False
    
    return True

def test_slack_integration():
    """Test Slack integration (mock only)."""
    print("\nTesting Slack integration...")
    
    with patch('main.requests.post') as mock_post:
        # Mock successful Slack response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "ts": "1234567890.123"}
        mock_post.return_value = mock_response
        
        # Import and test the function
        from main import _send_slack_alert
        
        # Set environment variable for test
        os.environ["SLACK_BOT_TOKEN"] = "xoxb-test-token"
        
        try:
            _send_slack_alert("Test message", {"test": "context"})
            print("✅ Slack alert function executed successfully")
            
            # Verify API call was made
            assert mock_post.called
            call_args = mock_post.call_args
            assert "https://slack.com/api/chat.postMessage" in call_args[0]
            
            print("✅ Slack integration test passed")
            
        except Exception as e:
            print(f"❌ Slack integration test failed: {e}")
            return False
        finally:
            # Clean up environment
            if "SLACK_BOT_TOKEN" in os.environ:
                del os.environ["SLACK_BOT_TOKEN"]
    
    return True

def main():
    """Run all tests."""
    print("🧪 Running Firebase Functions tests...\n")
    
    tests = [
        test_schedule_scraper_daily,
        test_on_transcription_written,
        test_slack_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print(f"\n📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
