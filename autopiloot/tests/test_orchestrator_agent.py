"""
Unit tests for OrchestratorAgent using unittest framework.
Tests agent initialization, configuration loading, agency wiring, and all orchestrator tools.
"""

import os
import sys
import unittest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Add orchestrator_agent directory to path for imports
orchestrator_dir = Path(__file__).parent.parent / "orchestrator_agent"
sys.path.append(str(orchestrator_dir))

# Add tools directory to path for imports
tools_dir = orchestrator_dir / "tools"
sys.path.append(str(tools_dir))

# Add config directory to path for imports
config_dir = Path(__file__).parent.parent / "config"
sys.path.append(str(config_dir))

from orchestrator_agent import orchestrator_agent
from agency import AutopilootAgency

# Import all orchestrator tools
from plan_daily_run import PlanDailyRun
from dispatch_scraper import DispatchScraper
from dispatch_transcriber import DispatchTranscriber
from dispatch_summarizer import DispatchSummarizer
from enforce_policies import EnforcePolicies
from handle_dlq import HandleDLQ
from query_dlq import QueryDLQ
from emit_run_events import EmitRunEvents


class TestOrchestratorAgent(unittest.TestCase):
    """Test cases for the orchestrator agent."""
    
    def test_agent_initialization(self):
        """Test that orchestrator agent initializes correctly."""
        self.assertEqual(orchestrator_agent.name, "Orchestrator")
        self.assertIn("CEO", orchestrator_agent.description)
        self.assertIn("end-to-end pipeline orchestration", orchestrator_agent.description)
        self.assertIn("policy enforcement", orchestrator_agent.description)
        
    def test_agent_instructions(self):
        """Test that agent has instructions file configured."""
        self.assertEqual(orchestrator_agent.instructions, "./instructions.md")
        
        # Verify instructions file exists
        instructions_path = Path(__file__).parent.parent / "orchestrator_agent" / "instructions.md"
        self.assertTrue(instructions_path.exists(), "Instructions file should exist")
        
    def test_agent_tools_folder(self):
        """Test that agent has tools folder configured."""
        self.assertEqual(orchestrator_agent.tools_folder, "./tools")
        
        # Verify tools directory exists
        tools_path = Path(__file__).parent.parent / "orchestrator_agent" / "tools"
        self.assertTrue(tools_path.exists(), "Tools directory should exist")
        self.assertTrue(tools_path.is_dir(), "Tools path should be a directory")
        
    def test_model_settings(self):
        """Test that agent has proper model settings."""
        model_settings = orchestrator_agent.model_settings
        self.assertIsNotNone(model_settings)
        
        # Check that model is configured (should be from config or default)
        self.assertIsNotNone(model_settings.model)
        self.assertIsInstance(model_settings.model, str)
        
        # Check temperature is reasonable
        self.assertIsNotNone(model_settings.temperature)
        self.assertIsInstance(model_settings.temperature, (int, float))
        self.assertGreaterEqual(model_settings.temperature, 0.0)
        self.assertLessEqual(model_settings.temperature, 1.0)
        
        # Check max_completion_tokens is set
        self.assertIsNotNone(model_settings.max_completion_tokens)
        self.assertIsInstance(model_settings.max_completion_tokens, int)
        self.assertGreater(model_settings.max_completion_tokens, 0)
        
    def test_agency_wiring(self):
        """Test that agency includes orchestrator as CEO and has proper communication flows."""
        agency = AutopilootAgency()
        
        # Get the agency chart from the agency instance
        agency_chart = agency.agency_chart
        self.assertIsNotNone(agency_chart)
        self.assertGreater(len(agency_chart), 0)
        
        # First element should be the CEO (orchestrator)
        ceo_agent = agency_chart[0]
        self.assertEqual(ceo_agent.name, "Orchestrator")
        
        # Verify orchestrator can communicate with all other agents
        orchestrator_flows = [flow for flow in agency_chart if isinstance(flow, list) and len(flow) == 2 and flow[0].name == "Orchestrator"]
        
        # Should have flows to all 4 other agents
        target_agents = {"ScraperAgent", "TranscriberAgent", "SummarizerAgent", "ObservabilityAgent"}
        orchestrator_targets = {flow[1].name for flow in orchestrator_flows}
        
        self.assertTrue(target_agents.issubset(orchestrator_targets), 
                       f"Orchestrator should communicate with all agents. Missing: {target_agents - orchestrator_targets}")
        
    def test_instructions_content(self):
        """Test that instructions file contains required content."""
        instructions_path = Path(__file__).parent.parent / "orchestrator_agent" / "instructions.md"
        
        with open(instructions_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for key sections
        self.assertIn("# Role", content)
        self.assertIn("CEO", content)
        self.assertIn("orchestrator", content.lower())
        
        # Check for key responsibilities
        self.assertIn("Budget", content)
        self.assertIn("Quota", content) 
        self.assertIn("Policy", content)
        self.assertIn("Status", content)
        
        # Check for workflow section
        self.assertIn("Process Workflow", content)
        self.assertIn("1.", content)  # Numbered workflow
        
        # Check for important technical details
        self.assertIn("Firestore", content)
        self.assertIn("idempotency", content.lower())
        self.assertIn("retry", content.lower())


class TestOrchestratorTools(unittest.TestCase):
    """Test cases for orchestrator agent tools."""
    
    def test_plan_daily_run_tool(self):
        """Test PlanDailyRun tool initialization and basic functionality."""
        # Test with default parameters
        tool = PlanDailyRun()
        self.assertIsInstance(tool, PlanDailyRun)
        
        # Test with custom parameters
        tool_custom = PlanDailyRun(
            target_channels=["@TestChannel"],
            max_videos_per_channel=5
        )
        self.assertEqual(tool_custom.target_channels, ["@TestChannel"])
        self.assertEqual(tool_custom.max_videos_per_channel, 5)
        
        # Test run method returns valid JSON
        with patch('plan_daily_run.load_app_config') as mock_config:
            mock_config.return_value = {
                "scraper": {"handles": ["@AlexHormozi"], "daily_limit_per_channel": 10},
                "budgets": {"transcription_daily_usd": 5.0}
            }
            
            result = tool.run()
            self.assertIsInstance(result, str)
            
            # Parse and validate JSON structure
            data = json.loads(result)
            self.assertIn("channels", data)
            self.assertIn("per_channel_limit", data)
            self.assertIn("windows", data)
            self.assertIn("resource_limits", data)
    
    def test_dispatch_scraper_tool(self):
        """Test DispatchScraper tool validation and payload structure."""
        # Test channel scrape job
        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": ["@TestChannel"], "limit_per_channel": 5}
        )
        self.assertEqual(tool.job_type, "channel_scrape")
        self.assertIn("channels", tool.inputs)
        
        # Test validation
        with self.assertRaises(ValueError):
            invalid_tool = DispatchScraper(
                job_type="invalid_type",
                inputs={}
            )
            invalid_tool._validate_inputs()
        
        # Test sheet backfill job
        sheet_tool = DispatchScraper(
            job_type="sheet_backfill",
            inputs={"sheet_id": "test123", "range": "Sheet1!A:D"}
        )
        self.assertEqual(sheet_tool.job_type, "sheet_backfill")
        
        # Test priority calculation
        self.assertEqual(tool._calculate_priority(), "high")
        self.assertEqual(sheet_tool._calculate_priority(), "medium")
    
    def test_dispatch_transcriber_tool(self):
        """Test DispatchTranscriber tool budget validation and configuration."""
        # Test single video job
        tool = DispatchTranscriber(
            job_type="single_video",
            inputs={"video_id": "test123", "priority": "high"},
            policy_overrides={"budget_limit_usd": 1.0}
        )
        self.assertEqual(tool.job_type, "single_video")
        self.assertIn("video_id", tool.inputs)
        
        # Test budget check
        with patch('dispatch_transcriber.load_app_config') as mock_config:
            mock_config.return_value = {"budgets": {"transcription_daily_usd": 5.0}}
            
            budget_check = tool._check_budget_constraints(mock_config.return_value)
            self.assertIn("allowed", budget_check)
            self.assertIn("estimated_cost", budget_check)
        
        # Test batch job
        batch_tool = DispatchTranscriber(
            job_type="batch_transcribe",
            inputs={"video_ids": ["vid1", "vid2", "vid3"], "batch_size": 2}
        )
        self.assertEqual(len(batch_tool.inputs["video_ids"]), 3)
    
    def test_dispatch_summarizer_tool(self):
        """Test DispatchSummarizer tool platform validation and LLM configuration."""
        # Test single summary job
        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test123", "platforms": ["drive", "zep"]},
            policy_overrides={"temperature": 0.3}
        )
        self.assertEqual(tool.job_type, "single_summary")
        self.assertIn("platforms", tool.inputs)
        
        # Test platform validation
        with self.assertRaises(ValueError):
            invalid_tool = DispatchSummarizer(
                job_type="single_summary",
                inputs={"video_id": "test123", "platforms": ["invalid_platform"]}
            )
            invalid_tool._validate_inputs()
        
        # Test LLM config building
        with patch('dispatch_summarizer.load_app_config') as mock_config:
            mock_config.return_value = {
                "llm": {
                    "default": {"model": "gpt-4o", "temperature": 0.2, "max_output_tokens": 1500},
                    "tasks": {
                        "summarizer_generate_short": {
                            "model": "gpt-4o", 
                            "temperature": 0.2,
                            "prompt_id": "coach_v1"
                        }
                    }
                }
            }
            
            llm_config = tool._build_llm_config(mock_config.return_value)
            self.assertIn("model", llm_config)
            self.assertIn("temperature", llm_config)
            self.assertEqual(llm_config["temperature"], 0.3)  # Override applied
    
    def test_enforce_policies_tool(self):
        """Test EnforcePolicies tool decision logic and calculations."""
        # Test proceed scenario
        tool = EnforcePolicies(
            job_context={
                "job_id": "test123",
                "job_type": "single_video",
                "retry_count": 1,
                "error_type": "api_timeout"
            },
            current_state={
                "quota_usage": {"youtube": 5000, "assemblyai": 25}
            }
        )
        
        # Test retry policy evaluation
        retry_decision = tool._evaluate_retry_policy(1, 3, "api_timeout")
        self.assertEqual(retry_decision["action"], "retry")
        
        retry_decision_dlq = tool._evaluate_retry_policy(3, 3, "api_timeout")
        self.assertEqual(retry_decision_dlq["action"], "dlq")
        
        # Test terminal error handling
        terminal_decision = tool._evaluate_retry_policy(1, 3, "invalid_video_id")
        self.assertEqual(terminal_decision["action"], "dlq")
        
        # Test backoff calculation
        self.assertEqual(tool._calculate_backoff_delay(1, 60), 120)  # 60 * 2^1
        self.assertEqual(tool._calculate_backoff_delay(2, 60), 240)  # 60 * 2^2
        
        # Test quota evaluation
        with patch('enforce_policies.load_app_config') as mock_config:
            mock_config.return_value = {}
            with patch('enforce_policies.get_youtube_daily_limit', return_value=10000):
                quota_decision = tool._evaluate_quota_constraints("channel_scrape", {})
                self.assertEqual(quota_decision["action"], "proceed")
    
    def test_handle_dlq_tool(self):
        """Test HandleDLQ tool severity calculation and payload structure."""
        tool = HandleDLQ(
            job_id="test123",
            job_type="single_video",
            failure_context={
                "error_type": "authorization_failed",
                "error_message": "API key invalid",
                "retry_count": 2,
                "original_inputs": {"video_id": "test123"}
            },
            recovery_hints={"manual_action_required": True}
        )
        
        # Test severity calculation
        self.assertEqual(tool._calculate_severity(), "high")  # auth failures are high severity
        
        # Test recovery priority
        self.assertEqual(tool._calculate_recovery_priority(), "urgent")  # high severity = urgent
        
        # Test job-specific metadata
        metadata = tool._build_job_specific_metadata()
        self.assertIn("video_id", metadata)
        self.assertEqual(metadata["video_id"], "test123")
        
        # Test validation
        tool._validate_inputs()  # Should not raise
    
    def test_query_dlq_tool(self):
        """Test QueryDLQ tool filtering and statistics calculation."""
        tool = QueryDLQ(
            filter_job_type="single_video",
            filter_severity="high",
            time_range_hours=24,
            include_statistics=True,
            limit=10
        )
        
        # Test input validation
        tool._validate_inputs()  # Should not raise
        
        # Test invalid inputs
        with self.assertRaises(ValueError):
            invalid_tool = QueryDLQ(filter_severity="invalid")
            invalid_tool._validate_inputs()
        
        # Test video ID matching
        entry_data = {
            "video_id": "test123",
            "failure_context": {"original_inputs": {"video_id": "test456"}}
        }
        self.assertTrue(tool._matches_video_id(entry_data, "test123"))
        self.assertTrue(tool._matches_video_id(entry_data, "test456"))
        self.assertFalse(tool._matches_video_id(entry_data, "notfound"))
        
        # Test statistics calculation
        sample_entries = [
            {"job_type": "single_video", "severity": "high", "processing_attempts": 3},
            {"job_type": "channel_scrape", "severity": "medium", "processing_attempts": 2},
            {"job_type": "single_video", "severity": "low", "processing_attempts": 1}
        ]
        
        stats = tool._calculate_statistics(sample_entries)
        self.assertEqual(stats["total_entries"], 3)
        self.assertEqual(stats["by_job_type"]["single_video"], 2)
        self.assertEqual(stats["average_processing_attempts"], 2.0)
    
    def test_emit_run_events_tool(self):
        """Test EmitRunEvents tool metrics calculation and message formatting."""
        tool = EmitRunEvents(
            run_summary={
                "planned": 25,
                "succeeded": 22,
                "failed": 3,
                "dlq_count": 1,
                "quota_state": {"youtube": 0.75, "assemblyai": 0.45},
                "total_cost_usd": 2.35
            },
            run_context={
                "run_id": "test_run",
                "run_type": "scheduled_daily",
                "started_at": "2025-01-27T01:00:00Z",
                "completed_at": "2025-01-27T03:45:00Z"
            },
            alert_level="info"
        )
        
        # Test validation
        tool._validate_inputs()  # Should not raise
        
        # Test success rate calculation
        success_rate = tool._calculate_success_rate()
        self.assertAlmostEqual(success_rate, 22/25, places=3)
        
        # Test cost efficiency
        cost_efficiency = tool._calculate_cost_efficiency()
        self.assertAlmostEqual(cost_efficiency, 2.35/22, places=3)
        
        # Test duration calculation
        duration = tool._calculate_run_duration()
        self.assertAlmostEqual(duration, 2.75, places=2)  # 2 hours 45 minutes
        
        # Test health score calculation
        health_score = tool._calculate_health_score()
        self.assertGreater(health_score, 60)  # Should be a good score
        self.assertLessEqual(health_score, 100)
        
        # Test Slack message formatting
        event_payload = {"test": "data"}
        slack_msg = tool._format_slack_message(event_payload)
        self.assertIn("channel", slack_msg)
        self.assertIn("title", slack_msg)
        self.assertIn("summary_text", slack_msg)
        
        # Test status emoji
        self.assertEqual(tool._get_status_emoji(0.95, "info"), "✅")
        self.assertEqual(tool._get_status_emoji(0.5, "error"), "❌")


if __name__ == "__main__":
    unittest.main(verbosity=2)