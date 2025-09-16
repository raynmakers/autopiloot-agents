#!/usr/bin/env python3
"""
Test script for Firebase Functions with Orchestrator Agent Integration.

This script provides comprehensive local testing for Firebase Functions,
including orchestrator agent integration paths, success scenarios, and fallback mechanisms.
Tests cover TASK-FB-0004 requirements for full agent workflow integration.
"""

import os
import sys
import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

# Add the functions directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from main import schedule_scraper_daily, on_transcription_written, get_orchestrator_agent
from core import create_scraper_job, process_transcription_budget

# Import scheduler functions
try:
    from scheduler import daily_digest_delivery, get_observability_agent
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    print("Warning: scheduler module not available for testing")

def test_schedule_scraper_daily_orchestrator_success():
    """Test scheduled scraper function with successful orchestrator agent integration."""
    print("Testing schedule_scraper_daily with orchestrator agent success...")

    # Mock orchestrator agent and tools
    mock_orchestrator = MagicMock()
    mock_plan_tool = MagicMock()
    mock_dispatch_tool = MagicMock()

    # Mock tool responses
    mock_plan_tool.run.return_value = '{"status": "success", "plan": "daily_scrape"}'
    mock_dispatch_tool.run.return_value = '{"status": "dispatched", "job_id": "scraper_123"}'

    with patch('main.get_orchestrator_agent') as mock_get_agent, \
         patch('main.PlanDailyRun') as mock_plan_class, \
         patch('main.DispatchScraper') as mock_dispatch_class:

        # Setup orchestrator agent mocks
        mock_get_agent.return_value = mock_orchestrator
        mock_plan_class.return_value = mock_plan_tool
        mock_dispatch_class.return_value = mock_dispatch_tool

        # Create mock request
        mock_req = Mock()

        # Execute function
        try:
            result = schedule_scraper_daily(mock_req)
            print(f"✅ Function executed successfully: {result}")

            # Verify orchestrator agent was used
            assert mock_get_agent.called
            assert result["method"] == "orchestrator_agent"
            assert "plan" in result
            assert "dispatch" in result

            # Verify tools were called
            mock_plan_tool.run.assert_called_once()
            mock_dispatch_tool.run.assert_called_once()

            print("✅ Orchestrator integration assertions passed")

        except Exception as e:
            print(f"❌ Function failed: {e}")
            return False

    return True

def test_schedule_scraper_daily_fallback():
    """Test scheduled scraper function fallback when orchestrator agent fails."""
    print("Testing schedule_scraper_daily with orchestrator agent fallback...")

    # Mock Firestore client for fallback
    with patch('main.get_orchestrator_agent') as mock_get_agent, \
         patch('main._get_firestore_client') as mock_firestore, \
         patch('core.create_scraper_job') as mock_create_job:

        # Setup orchestrator failure
        mock_get_agent.return_value = None  # Agent unavailable

        # Setup fallback mocks
        mock_db = Mock()
        mock_firestore.return_value = mock_db
        mock_create_job.return_value = {"status": "success", "job_id": "fallback_123", "method": "fallback"}

        # Create mock request
        mock_req = Mock()

        # Execute function
        try:
            result = schedule_scraper_daily(mock_req)
            print(f"✅ Function executed with fallback: {result}")

            # Verify fallback was used
            assert mock_get_agent.called
            mock_create_job.assert_called_once_with(mock_db, "Europe/Amsterdam")
            assert result["source"] == "main_py_fallback"

            print("✅ Fallback mechanism assertions passed")

        except Exception as e:
            print(f"❌ Fallback test failed: {e}")
            return False

    return True

def test_on_transcription_written_observability_agent_success():
    """Test transcription event function with successful observability agent integration."""
    print("\nTesting on_transcription_written with observability agent success...")

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

    # Mock orchestrator agent and observability tool
    mock_orchestrator = MagicMock()
    mock_budget_monitor = MagicMock()
    mock_budget_monitor.run.return_value = '{"status": "success", "budget_usage": 50.0, "alert_sent": false}'

    with patch('main.get_orchestrator_agent') as mock_get_agent, \
         patch('main.MonitorTranscriptionBudget') as mock_monitor_class, \
         patch('main.validate_video_id') as mock_validate_vid, \
         patch('main.validate_transcript_data') as mock_validate_data:

        # Setup mocks
        mock_get_agent.return_value = mock_orchestrator
        mock_monitor_class.return_value = mock_budget_monitor
        mock_validate_vid.return_value = True
        mock_validate_data.return_value = True

        # Execute function
        try:
            result = on_transcription_written(mock_event)
            print(f"✅ Function executed successfully: {result}")

            # Verify observability agent was used
            assert mock_get_agent.called
            assert result["method"] == "observability_agent_direct"
            assert result["video_id"] == "test-video-123"
            assert "result" in result

            # Verify budget monitor tool was called
            mock_budget_monitor.run.assert_called_once()

            print("✅ Observability agent integration assertions passed")

        except Exception as e:
            print(f"❌ Function failed: {e}")
            return False

    return True

def test_on_transcription_written_fallback():
    """Test transcription event function fallback when observability agent fails."""
    print("Testing on_transcription_written with observability agent fallback...")

    # Mock event data
    mock_event = Mock()
    mock_event.params = {"video_id": "test-video-456"}

    mock_transcript_data = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "costs": {"transcription_usd": 3.50}
    }

    mock_event.data = Mock()
    mock_event.data.to_dict.return_value = mock_transcript_data

    with patch('main.get_orchestrator_agent') as mock_get_agent, \
         patch('main._get_firestore_client') as mock_firestore, \
         patch('core.process_transcription_budget') as mock_process_budget, \
         patch('main.validate_video_id') as mock_validate_vid, \
         patch('main.validate_transcript_data') as mock_validate_data:

        # Setup agent failure
        mock_get_agent.return_value = None  # Agent unavailable

        # Setup fallback mocks
        mock_db = Mock()
        mock_firestore.return_value = mock_db
        mock_validate_vid.return_value = True
        mock_validate_data.return_value = True
        mock_process_budget.return_value = {
            "status": "success",
            "method": "fallback",
            "budget_usage_pct": 70.0
        }

        # Execute function
        try:
            result = on_transcription_written(mock_event)
            print(f"✅ Function executed with fallback: {result}")

            # Verify fallback was used
            assert mock_get_agent.called
            mock_process_budget.assert_called_once_with(mock_db, "test-video-456", mock_transcript_data)
            assert result["source"] == "main_py_fallback"

            print("✅ Fallback mechanism assertions passed")

        except Exception as e:
            print(f"❌ Fallback test failed: {e}")
            return False

    return True

def test_core_py_orchestrator_delegation():
    """Test that core.py properly delegates to orchestrator agent."""
    print("\nTesting core.py orchestrator agent delegation...")

    # Mock orchestrator agent and tools
    mock_orchestrator = MagicMock()
    mock_plan_tool = MagicMock()
    mock_dispatch_tool = MagicMock()
    mock_emit_tool = MagicMock()

    # Mock tool responses
    mock_plan_tool.run.return_value = '{"status": "success", "plan": "test_plan"}'
    mock_dispatch_tool.run.return_value = '{"status": "dispatched", "job_id": "core_test_123"}'
    mock_emit_tool.run.return_value = '{"status": "emitted"}'

    with patch('core.get_orchestrator_agent') as mock_get_agent, \
         patch('core.PlanDailyRun') as mock_plan_class, \
         patch('core.DispatchScraper') as mock_dispatch_class, \
         patch('core.EmitRunEvents') as mock_emit_class:

        # Setup orchestrator agent mocks
        mock_get_agent.return_value = mock_orchestrator
        mock_plan_class.return_value = mock_plan_tool
        mock_dispatch_class.return_value = mock_dispatch_tool
        mock_emit_class.return_value = mock_emit_tool

        # Mock Firestore client
        mock_firestore = Mock()

        try:
            result = create_scraper_job(mock_firestore, "Europe/Amsterdam")
            print(f"✅ Core delegation executed successfully: {result}")

            # Verify orchestrator agent delegation
            assert mock_get_agent.called
            assert result["method"] == "orchestrator_agent"
            assert "plan" in result
            assert "dispatch" in result

            # Verify all tools were used
            mock_plan_tool.run.assert_called_once()
            mock_dispatch_tool.run.assert_called_once()
            mock_emit_tool.run.assert_called()

            print("✅ Core.py delegation assertions passed")

        except Exception as e:
            print(f"❌ Core delegation test failed: {e}")
            return False

    return True

def test_observability_agent_budget_monitoring():
    """Test observability agent integration for budget monitoring."""
    print("Testing observability agent budget monitoring integration...")

    mock_budget_monitor = MagicMock()
    mock_budget_monitor.run.return_value = '{"status": "success", "budget_usage_pct": 85.0, "alert_sent": true}'

    with patch('core.MonitorTranscriptionBudget') as mock_monitor_class:

        mock_monitor_class.return_value = mock_budget_monitor

        # Mock data
        mock_firestore = Mock()
        video_id = "obs_test_video"
        transcript_data = {"costs": {"transcription_usd": 4.25}}

        try:
            result = process_transcription_budget(mock_firestore, video_id, transcript_data)
            print(f"✅ Observability agent budget monitoring executed: {result}")

            # Verify observability agent was used
            assert result["method"] == "observability_agent"
            assert result["video_id"] == video_id
            assert "agent_result" in result

            # Verify budget monitor tool was called
            mock_budget_monitor.run.assert_called_once()

            print("✅ Observability agent budget monitoring assertions passed")

        except Exception as e:
            print(f"❌ Observability agent test failed: {e}")
            return False

    return True

def test_agent_lazy_initialization():
    """Test that agent lazy initialization works correctly."""
    print("Testing agent lazy initialization...")

    # Reset global agent state
    import main
    main._orchestrator_agent = None

    with patch('main.orchestrator_agent') as mock_agent_module:
        mock_agent_instance = MagicMock()
        mock_agent_module.orchestrator_agent = mock_agent_instance

        try:
            # First call should initialize
            agent1 = get_orchestrator_agent()
            assert agent1 == mock_agent_instance

            # Second call should return same instance (cached)
            agent2 = get_orchestrator_agent()
            assert agent2 == mock_agent_instance
            assert agent1 is agent2

            print("✅ Lazy initialization working correctly")

        except Exception as e:
            print(f"❌ Lazy initialization test failed: {e}")
            return False

    return True

def test_slack_integration():
    """Test Slack integration via observability agent tools."""
    print("\nTesting Slack integration via agent tools...")

    # Mock observability agent Slack tools
    mock_formatter = MagicMock()
    mock_sender = MagicMock()

    mock_formatter.run.return_value = '{"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}]}'
    mock_sender.run.return_value = '{"ok": true, "ts": "1234567890.123"}'

    with patch('core.FormatSlackBlocks') as mock_format_class, \
         patch('core.SendSlackMessage') as mock_send_class:

        mock_format_class.return_value = mock_formatter
        mock_send_class.return_value = mock_sender

        # Import and test the function
        from core import _send_slack_alert_simple

        try:
            result = _send_slack_alert_simple("Test agent integration message", {"test": "context"})
            print("✅ Agent Slack tools executed successfully")

            # Verify agent tools were used
            assert mock_formatter.run.called
            assert mock_sender.run.called
            assert result == True

            print("✅ Agent Slack integration test passed")

        except Exception as e:
            print(f"❌ Agent Slack integration test failed: {e}")
            return False

    return True

def main():
    """Run all tests including orchestrator agent integration tests."""
    print("🧪 Running Enhanced Firebase Functions Tests (TASK-FB-0004)...\n")

    # Comprehensive test suite covering orchestrator agent integration
    tests = [
        # Orchestrator agent integration tests
        test_schedule_scraper_daily_orchestrator_success,
        test_schedule_scraper_daily_fallback,
        test_on_transcription_written_observability_agent_success,
        test_on_transcription_written_fallback,

        # Core.py delegation tests
        test_core_py_orchestrator_delegation,
        test_observability_agent_budget_monitoring,

        # Infrastructure tests
        test_agent_lazy_initialization,
        test_slack_integration,

        # Daily digest tests (TASK-DIG-0063)
        test_daily_digest_delivery_success,
        test_daily_digest_delivery_error_handling,
        test_daily_digest_integration
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"\n🔍 Running {test.__name__}...")
            if test():
                passed += 1
                print(f"✅ {test.__name__} PASSED")
            else:
                failed += 1
                print(f"❌ {test.__name__} FAILED")
        except Exception as e:
            print(f"💥 Test {test.__name__} crashed: {e}")
            failed += 1

    print(f"\n📊 FINAL TEST RESULTS:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed/(passed+failed)*100):.1f}%" if (passed+failed) > 0 else "N/A")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Orchestrator agent integration is working correctly.")
        print("✅ TASK-FB-0004 test requirements satisfied.")
        return 0
    else:
        print(f"\n⚠️  {failed} TEST(S) FAILED - please review orchestrator agent integration.")
        return 1


def test_daily_digest_delivery_success():
    """Test daily digest delivery function with successful generation."""
    if not SCHEDULER_AVAILABLE:
        print("❌ Daily digest test skipped - scheduler module not available")
        return False

    print("Testing daily_digest_delivery function...")

    # Mock event
    mock_event = Mock()
    mock_event.id = "test_digest_event_123"

    # Mock observability agent and tools
    mock_observability = MagicMock()
    mock_digest_tool = MagicMock()
    mock_slack_tool = MagicMock()

    # Mock digest generation result
    digest_result = {
        "date": "2025-09-15",
        "timezone": "Europe/Amsterdam",
        "metrics": {
            "videos_discovered": 3,
            "videos_transcribed": 2,
            "summaries_generated": 1,
            "total_cost_usd": 2.50,
            "dlq_entries": 0
        },
        "slack_blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": "🌅 Daily Autopiloot Digest - 2025-09-15"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "*📊 Processing Summary*"}}
        ]
    }

    mock_digest_tool.run.return_value = json.dumps(digest_result)
    mock_slack_tool.run.return_value = json.dumps({"status": "sent", "ts": "1234567890.123"})

    with patch('scheduler.get_observability_agent', return_value=None), \
         patch('scheduler.GenerateDailyDigest', return_value=mock_digest_tool), \
         patch('scheduler.SendSlackMessage', return_value=mock_slack_tool), \
         patch('scheduler.db') as mock_db, \
         patch('scheduler.datetime') as mock_datetime, \
         patch('scheduler.pytz') as mock_pytz:

        # Mock timezone handling
        mock_ams_tz = Mock()
        mock_now_ams = Mock()
        mock_yesterday_ams = Mock()
        mock_yesterday_ams.strftime.return_value = "2025-09-15"

        mock_pytz.timezone.return_value = mock_ams_tz
        mock_datetime.now.return_value = mock_now_ams
        mock_now_ams.__sub__.return_value = mock_yesterday_ams

        # Mock Firestore audit logging
        mock_audit_ref = Mock()
        mock_db.collection.return_value.document.return_value = mock_audit_ref

        # Call the function
        result = daily_digest_delivery(mock_event)

        # Verify result
        assert result["ok"] is True
        assert result["date"] == "2025-09-15"
        assert result["timezone"] == "Europe/Amsterdam"
        assert "execution_time" in result

        # Verify tool calls
        mock_digest_tool.run.assert_called_once()
        mock_slack_tool.run.assert_called_once()

        # Verify audit logging
        mock_audit_ref.set.assert_called()

        print("✅ Daily digest delivery test passed")
        return True


def test_daily_digest_delivery_error_handling():
    """Test daily digest delivery error handling."""
    if not SCHEDULER_AVAILABLE:
        print("❌ Daily digest error test skipped - scheduler module not available")
        return False

    print("Testing daily_digest_delivery error handling...")

    # Mock event
    mock_event = Mock()
    mock_event.id = "test_digest_error_event"

    # Mock digest tool that raises exception
    mock_digest_tool = MagicMock()
    mock_digest_tool.run.side_effect = Exception("Firestore connection failed")

    # Mock error alert tool
    mock_error_tool = MagicMock()
    mock_error_tool.run.return_value = json.dumps({"status": "alert_sent"})

    with patch('scheduler.get_observability_agent', return_value=None), \
         patch('scheduler.GenerateDailyDigest', return_value=mock_digest_tool), \
         patch('scheduler.SendErrorAlert', return_value=mock_error_tool), \
         patch('scheduler.db') as mock_db, \
         patch('scheduler.datetime') as mock_datetime, \
         patch('scheduler.pytz') as mock_pytz:

        # Mock timezone handling
        mock_ams_tz = Mock()
        mock_now_ams = Mock()
        mock_yesterday_ams = Mock()
        mock_yesterday_ams.strftime.return_value = "2025-09-15"

        mock_pytz.timezone.return_value = mock_ams_tz
        mock_datetime.now.return_value = mock_now_ams
        mock_now_ams.__sub__.return_value = mock_yesterday_ams

        # Mock Firestore audit logging
        mock_audit_ref = Mock()
        mock_db.collection.return_value.document.return_value = mock_audit_ref

        # Call the function (should handle error gracefully)
        result = daily_digest_delivery(mock_event)

        # Verify error result
        assert result["ok"] is False
        assert "error" in result
        assert "Firestore connection failed" in result["error"]

        # Verify error alert was sent
        mock_error_tool.run.assert_called_once()

        # Verify error audit logging
        mock_audit_ref.set.assert_called()

        print("✅ Daily digest error handling test passed")
        return True


def test_daily_digest_integration():
    """Test complete daily digest integration workflow."""
    if not SCHEDULER_AVAILABLE:
        print("❌ Daily digest integration test skipped - scheduler module not available")
        return False

    print("Testing complete daily digest integration...")

    # Create a more realistic integration test
    mock_event = Mock()

    # Test with both agent success and tool fallback paths
    test_scenarios = [
        {"agent_available": True, "agent_success": True},
        {"agent_available": True, "agent_success": False},  # Agent fails, fallback to tools
        {"agent_available": False, "agent_success": False}   # No agent, direct tools
    ]

    for i, scenario in enumerate(test_scenarios):
        print(f"  Scenario {i+1}: Agent={scenario['agent_available']}, Success={scenario['agent_success']}")

        mock_agent = MagicMock() if scenario['agent_available'] else None
        if scenario['agent_available'] and not scenario['agent_success']:
            mock_agent.run.side_effect = Exception("Agent workflow failed")

        # Mock tools for fallback
        mock_digest_tool = MagicMock()
        mock_digest_tool.run.return_value = json.dumps({
            "date": "2025-09-15",
            "slack_blocks": [{"type": "header"}]
        })

        mock_slack_tool = MagicMock()
        mock_slack_tool.run.return_value = json.dumps({"status": "sent"})

        with patch('scheduler.get_observability_agent', return_value=mock_agent), \
             patch('scheduler.GenerateDailyDigest', return_value=mock_digest_tool), \
             patch('scheduler.SendSlackMessage', return_value=mock_slack_tool), \
             patch('scheduler.db'), \
             patch('scheduler.datetime') as mock_datetime, \
             patch('scheduler.pytz'):

            # Mock time
            mock_yesterday = Mock()
            mock_yesterday.strftime.return_value = "2025-09-15"
            mock_datetime.now.return_value.__sub__.return_value = mock_yesterday

            # Call function
            result = daily_digest_delivery(mock_event)

            # All scenarios should succeed (with fallback if needed)
            assert result["ok"] is True
            print(f"    ✅ Scenario {i+1} passed")

    print("✅ Daily digest integration test passed")
    return True

if __name__ == "__main__":
    sys.exit(main())
