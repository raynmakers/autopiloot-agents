"""
Comprehensive test suite for SynthesizeStrategyPlaybook tool.
Targets 90%+ coverage by testing edge cases, error conditions, and all code paths.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch, mock_open
from datetime import datetime, timezone

# Mock external dependencies before imports
sys.modules['agency_swarm'] = MagicMock()
sys.modules['agency_swarm.tools'] = MagicMock()
sys.modules['pydantic'] = MagicMock()

# Mock Field
mock_field = MagicMock()
sys.modules['pydantic'].Field = mock_field

# Mock BaseTool
mock_base_tool = MagicMock()
sys.modules['agency_swarm.tools'].BaseTool = mock_base_tool

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..')
sys.path.insert(0, project_root)

# Mock config imports
sys.modules['env_loader'] = MagicMock()
sys.modules['loader'] = MagicMock()

# Import the tool after mocking
from strategy_agent.tools.synthesize_strategy_playbook import (
    SynthesizeStrategyPlaybook,
    LLMPlaybookSynthesizer,
    RuleBasedSynthesizer,
    MockLLMClient
)


class TestSynthesizeStrategyPlaybookComprehensive(unittest.TestCase):
    """Comprehensive tests for SynthesizeStrategyPlaybook tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_keywords = {
            "keywords": [
                {"term": "business", "frequency": 15, "avg_engagement": 0.8, "engagement_boost": 0.15},
                {"term": "growth", "frequency": 12, "avg_engagement": 0.75, "engagement_boost": 0.12},
                {"term": "startup", "frequency": 10, "avg_engagement": 0.85, "engagement_boost": 0.18},
                {"term": "leadership", "frequency": 8, "avg_engagement": 0.72, "engagement_boost": 0.08},
                {"term": "technology", "frequency": 6, "avg_engagement": 0.65, "engagement_boost": 0.05}
            ]
        }

        self.sample_triggers = {
            "trigger_phrases": [
                {"phrase": "excited to announce", "log_odds": 2.5, "phrase_type": "announcement"},
                {"phrase": "what's your experience", "log_odds": 1.8, "phrase_type": "question"},
                {"phrase": "here's what I learned", "log_odds": 2.1, "phrase_type": "personal"},
                {"phrase": "you need to", "log_odds": 1.5, "phrase_type": "action"}
            ],
            "phrase_categories": {
                "announcement": 0.25,
                "question": 0.35,
                "personal": 0.20,
                "action": 0.20
            }
        }

        self.sample_post_types = {
            "analysis": {
                "engagement_by_type": {"personal_story": 0.85, "how_to": 0.72, "opinion": 0.68, "question": 0.61},
                "top_performing_types": ["personal_story", "how_to", "opinion", "question"]
            },
            "processing_metadata": {"total_input_items": 100}
        }

        self.sample_tones = {
            "overall_tone": {"primary_characteristics": ["conversational", "authentic", "professional"]},
            "authority_markers": {"authority_score": 0.72},
            "engagement_correlation": {"high_engagement_traits": ["personal", "actionable", "authentic"]}
        }

    def test_basic_functionality_success(self):
        """Test basic tool functionality with valid inputs."""
        tool = SynthesizeStrategyPlaybook(
            keywords=self.sample_keywords,
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=self.sample_tones,
            use_llm=False
        )

        result = tool.run()
        parsed_result = json.loads(result)

        self.assertIn("playbook_markdown", parsed_result)
        self.assertIn("playbook_json", parsed_result)
        self.assertIn("version", parsed_result)
        self.assertIn("created_at", parsed_result)
        self.assertIn("analysis_sources", parsed_result)

    def test_missing_required_sections_validation(self):
        """Test validation error when required sections are missing."""
        # Test missing keywords (line coverage for validation)
        tool = SynthesizeStrategyPlaybook(
            keywords={},
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=self.sample_tones
        )

        result = tool.run()
        parsed_result = json.loads(result)

        self.assertIn("error", parsed_result)
        self.assertEqual(parsed_result["error"], "missing_required_sections")
        self.assertIn("keywords", parsed_result["message"])

    def test_invalid_input_types_validation(self):
        """Test validation with invalid input types."""
        # Test with None values
        tool = SynthesizeStrategyPlaybook(
            keywords=None,
            triggers=None,
            post_types=None,
            tones=None
        )

        result = tool.run()
        parsed_result = json.loads(result)

        self.assertIn("error", parsed_result)
        self.assertEqual(parsed_result["error"], "missing_required_sections")

    def test_exception_handling_in_run_method(self):
        """Test exception handling in run method (lines 202-215)."""
        with patch.object(SynthesizeStrategyPlaybook, '_validate_inputs', side_effect=Exception("Test error")):
            tool = SynthesizeStrategyPlaybook(
                keywords=self.sample_keywords,
                triggers=self.sample_triggers,
                post_types=self.sample_post_types,
                tones=self.sample_tones
            )

            result = tool.run()
            parsed_result = json.loads(result)

            self.assertIn("error", parsed_result)
            self.assertEqual(parsed_result["error"], "playbook_synthesis_failed")
            self.assertIn("Test error", parsed_result["message"])
            self.assertIn("inputs_provided", parsed_result)

    def test_high_engagement_traits_extraction(self):
        """Test extraction of high engagement traits (line 270)."""
        tones_with_traits = {
            "overall_tone": {"primary_characteristics": ["conversational"]},
            "authority_markers": {"authority_score": 0.5},
            "engagement_correlation": {"high_engagement_traits": ["personal", "actionable"]}
        }

        tool = SynthesizeStrategyPlaybook(
            keywords=self.sample_keywords,
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=tones_with_traits,
            use_llm=False
        )

        insights = tool._extract_key_insights()
        self.assertIn("high_engagement_traits", insights)
        self.assertEqual(insights["high_engagement_traits"], ["personal", "actionable"])

    def test_unmatched_keywords_handling(self):
        """Test handling of unmatched keywords (lines 367, 371)."""
        keywords_with_unmatched = {
            "keywords": [
                {"term": "random_term", "frequency": 5, "avg_engagement": 0.6},
                {"term": "another_random", "frequency": 3, "avg_engagement": 0.7},
                {"term": "business", "frequency": 15, "avg_engagement": 0.8}  # This will match
            ]
        }

        tool = SynthesizeStrategyPlaybook(
            keywords=keywords_with_unmatched,
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=self.sample_tones,
            use_llm=False
        )

        insights = tool._extract_key_insights()
        winning_topics = tool._build_winning_topics(insights)

        # Should include general_engagement category for unmatched keywords
        topic_names = [topic["topic"] for topic in winning_topics]
        self.assertIn("general_engagement", topic_names)

    def test_frequency_recommendations_edge_cases(self):
        """Test frequency recommendation edge cases (lines 379, 382-385)."""
        tool = SynthesizeStrategyPlaybook(
            keywords=self.sample_keywords,
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=self.sample_tones,
            use_llm=False
        )

        # Test high engagement + high frequency -> weekly
        freq_weekly = tool._recommend_frequency(0.85, 15)
        self.assertEqual(freq_weekly, "weekly")

        # Test medium engagement + medium frequency -> bi-weekly
        freq_biweekly = tool._recommend_frequency(0.65, 8)
        self.assertEqual(freq_biweekly, "bi-weekly")

        # Test low-medium engagement -> monthly
        freq_monthly = tool._recommend_frequency(0.45, 3)
        self.assertEqual(freq_monthly, "monthly")

        # Test very low engagement -> occasional
        freq_occasional = tool._recommend_frequency(0.2, 2)
        self.assertEqual(freq_occasional, "occasional")

    def test_voice_characteristics_edge_cases(self):
        """Test voice characteristics generation edge cases (lines 506, 512)."""
        # Test with high authority score
        high_authority_tones = {
            "overall_tone": {"primary_characteristics": ["professional", "personal"]},
            "authority_markers": {"authority_score": 0.8},
            "engagement_correlation": {}
        }

        tool = SynthesizeStrategyPlaybook(
            keywords=self.sample_keywords,
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=high_authority_tones,
            use_llm=False
        )

        insights = tool._extract_key_insights()
        tone_guidelines = tool._build_tone_guidelines(insights)

        self.assertIn("authoritative", tone_guidelines["voice_characteristics"])
        self.assertIn("data-driven", tone_guidelines["voice_characteristics"])

        # Test with no characteristics detected (fallback case - line 512)
        empty_tones = {
            "overall_tone": {"primary_characteristics": []},
            "authority_markers": {"authority_score": 0.3},
            "engagement_correlation": {}
        }

        tool_empty = SynthesizeStrategyPlaybook(
            keywords=self.sample_keywords,
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=empty_tones,
            use_llm=False
        )

        insights_empty = tool_empty._extract_key_insights()
        tone_guidelines_empty = tool_empty._build_tone_guidelines(insights_empty)

        # Should fallback to default characteristics
        self.assertIn("professional", tone_guidelines_empty["voice_characteristics"])
        self.assertIn("engaging", tone_guidelines_empty["voice_characteristics"])
        self.assertIn("authentic", tone_guidelines_empty["voice_characteristics"])

    def test_content_calendar_edge_cases(self):
        """Test content calendar framework edge cases (lines 528, 547)."""
        # Test with no top performing types (fallback case - line 528)
        empty_insights = {"top_performing_types": []}

        tool = SynthesizeStrategyPlaybook(
            keywords=self.sample_keywords,
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=self.sample_tones,
            use_llm=False
        )

        calendar = tool._build_content_calendar_framework(empty_insights)

        # Should use default mix
        self.assertEqual(calendar["weekly_mix"]["educational"], "40%")
        self.assertEqual(calendar["weekly_mix"]["personal"], "30%")
        self.assertEqual(calendar["weekly_mix"]["industry"], "20%")
        self.assertEqual(calendar["weekly_mix"]["promotional"], "10%")

        # Test with custom performing types (line 547 fourth position)
        custom_insights = {
            "top_performing_types": ["type1", "type2", "type3", "type4", "type5"]  # More than 4 types
        }

        calendar_custom = tool._build_content_calendar_framework(custom_insights)

        # Fourth type should get 10%
        self.assertEqual(calendar_custom["weekly_mix"]["type4"], "10%")

    def test_llm_synthesizer_initialization_without_openai(self):
        """Test LLM synthesizer initialization without OpenAI (lines 658-666)."""
        with patch('os.getenv', return_value=None):  # No API key
            synthesizer = LLMPlaybookSynthesizer()
            self.assertIsInstance(synthesizer.client, MockLLMClient)

    def test_llm_synthesizer_initialization_import_error(self):
        """Test LLM synthesizer initialization with import error (lines 658-666)."""
        with patch('builtins.__import__', side_effect=ImportError("OpenAI not available")):
            synthesizer = LLMPlaybookSynthesizer()
            self.assertIsInstance(synthesizer.client, MockLLMClient)

    def test_llm_synthesizer_with_mock_client(self):
        """Test LLM synthesizer using mock client (lines 670-671)."""
        synthesizer = LLMPlaybookSynthesizer()
        synthesizer.client = MockLLMClient()

        insights = {"top_keywords": ["test"], "top_triggers": []}
        result = synthesizer.create_executive_summary(insights)

        self.assertIn("key_insights", result)
        self.assertIn("top_opportunities", result)
        self.assertIn("engagement_drivers", result)

    @patch('os.getenv')
    def test_llm_synthesizer_with_real_openai_success(self, mock_getenv):
        """Test LLM synthesizer with real OpenAI client success (lines 691-703)."""
        mock_getenv.return_value = "test-api-key"

        # Mock OpenAI response
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = json.dumps({
            "key_insights": ["insight1", "insight2"],
            "top_opportunities": ["opp1", "opp2"],
            "engagement_drivers": ["driver1", "driver2"]
        })
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch('openai.OpenAI', return_value=mock_client):
            synthesizer = LLMPlaybookSynthesizer()
            synthesizer.client = mock_client

            insights = {"test": "data"}
            result = synthesizer.create_executive_summary(insights)

            self.assertIn("key_insights", result)
            self.assertEqual(result["key_insights"], ["insight1", "insight2"])

    @patch('os.getenv')
    def test_llm_synthesizer_with_openai_error(self, mock_getenv):
        """Test LLM synthesizer with OpenAI error fallback (lines 705-706)."""
        mock_getenv.return_value = "test-api-key"

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        with patch('openai.OpenAI', return_value=mock_client):
            synthesizer = LLMPlaybookSynthesizer()
            synthesizer.client = mock_client

            insights = {"test": "data"}
            result = synthesizer.create_executive_summary(insights)

            # Should fallback to MockLLMClient result
            self.assertIn("key_insights", result)
            self.assertIsInstance(result["key_insights"], list)

    def test_llm_synthesizer_hooks_generation(self):
        """Test hooks and openers generation (lines 711-737)."""
        synthesizer = LLMPlaybookSynthesizer()
        insights = {"test": "data"}

        hooks = synthesizer.generate_hooks_and_openers(insights)

        self.assertIsInstance(hooks, list)
        self.assertTrue(len(hooks) > 0)

        # Check structure of hooks
        for hook in hooks:
            self.assertIn("hook", hook)
            self.assertIn("category", hook)
            self.assertIn("effectiveness", hook)
            self.assertIn("use_cases", hook)

    def test_llm_synthesizer_cta_patterns_generation(self):
        """Test CTA patterns generation (lines 741-761)."""
        synthesizer = LLMPlaybookSynthesizer()
        insights = {"test": "data"}

        cta_patterns = synthesizer.generate_cta_patterns(insights)

        self.assertIsInstance(cta_patterns, list)
        self.assertTrue(len(cta_patterns) > 0)

        # Check structure of CTA patterns
        for cta in cta_patterns:
            self.assertIn("cta", cta)
            self.assertIn("type", cta)
            self.assertIn("response_rate", cta)
            self.assertIn("optimal_placement", cta)

    def test_mock_llm_client_executive_summary(self):
        """Test MockLLMClient executive summary generation (line 815)."""
        mock_client = MockLLMClient()
        insights = {"test": "data"}

        result = mock_client.create_executive_summary(insights)

        self.assertIn("key_insights", result)
        self.assertIn("top_opportunities", result)
        self.assertIn("engagement_drivers", result)
        self.assertIsInstance(result["key_insights"], list)
        self.assertTrue(len(result["key_insights"]) > 0)

    def test_rule_based_synthesizer_methods(self):
        """Test RuleBasedSynthesizer methods."""
        synthesizer = RuleBasedSynthesizer()
        insights = {"test": "data"}

        # Test executive summary
        exec_summary = synthesizer.create_executive_summary(insights)
        self.assertIn("key_insights", exec_summary)
        self.assertIn("top_opportunities", exec_summary)

        # Test hooks generation
        hooks = synthesizer.generate_hooks_and_openers(insights)
        self.assertIsInstance(hooks, list)
        self.assertTrue(len(hooks) > 0)

        # Test CTA patterns
        cta_patterns = synthesizer.generate_cta_patterns(insights)
        self.assertIsInstance(cta_patterns, list)
        self.assertTrue(len(cta_patterns) > 0)

    def test_with_llm_enabled(self):
        """Test tool with LLM enabled (line 167)."""
        tool = SynthesizeStrategyPlaybook(
            keywords=self.sample_keywords,
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=self.sample_tones,
            use_llm=True,
            model="gpt-4o"
        )

        result = tool.run()
        parsed_result = json.loads(result)

        self.assertIn("synthesis_metadata", parsed_result)
        self.assertEqual(parsed_result["synthesis_metadata"]["synthesis_method"], "llm")
        self.assertEqual(parsed_result["synthesis_metadata"]["model_used"], "gpt-4o")

    def test_with_constraints_and_topics(self):
        """Test tool with constraints and topics provided."""
        constraints = {"brand_voice": "professional", "avoid_terms": ["disrupt"]}
        topics = {"clusters": [{"name": "business", "keywords": ["growth", "strategy"]}]}

        tool = SynthesizeStrategyPlaybook(
            keywords=self.sample_keywords,
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=self.sample_tones,
            constraints=constraints,
            topics=topics,
            examples={"high_performing": ["post1", "post2"]},
            use_llm=False
        )

        result = tool.run()
        parsed_result = json.loads(result)

        self.assertIn("synthesis_metadata", parsed_result)
        self.assertTrue(parsed_result["synthesis_metadata"]["constraints_applied"])
        self.assertTrue(parsed_result["synthesis_metadata"]["topics_included"])

    def test_empty_data_handling(self):
        """Test handling of empty data in various sections."""
        empty_keywords = {"keywords": []}
        empty_triggers = {"trigger_phrases": []}
        empty_post_types = {"analysis": {}, "processing_metadata": {"total_input_items": 0}}
        empty_tones = {"overall_tone": {}, "authority_markers": {}}

        tool = SynthesizeStrategyPlaybook(
            keywords=empty_keywords,
            triggers=empty_triggers,
            post_types=empty_post_types,
            tones=empty_tones,
            use_llm=False
        )

        result = tool.run()
        parsed_result = json.loads(result)

        # Should handle empty data gracefully
        self.assertIn("error", parsed_result)
        self.assertEqual(parsed_result["error"], "missing_required_sections")

    def test_phrase_type_context_mapping(self):
        """Test phrase type to context mapping."""
        tool = SynthesizeStrategyPlaybook(
            keywords=self.sample_keywords,
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=self.sample_tones,
            use_llm=False
        )

        # Test various phrase types
        contexts = {
            "announcement": tool._determine_phrase_context("announcement"),
            "personal": tool._determine_phrase_context("personal"),
            "question": tool._determine_phrase_context("question"),
            "unknown": tool._determine_phrase_context("unknown_type")
        }

        self.assertEqual(contexts["announcement"], "announcements")
        self.assertEqual(contexts["personal"], "storytelling")
        self.assertEqual(contexts["question"], "engagement")
        self.assertEqual(contexts["unknown"], "general")

    def test_usage_guidelines_generation(self):
        """Test usage guidelines generation for various phrase types."""
        tool = SynthesizeStrategyPlaybook(
            keywords=self.sample_keywords,
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=self.sample_tones,
            use_llm=False
        )

        guidelines = {
            "announcement": tool._generate_usage_guidelines("test phrase", "announcement"),
            "personal": tool._generate_usage_guidelines("test phrase", "personal"),
            "unknown": tool._generate_usage_guidelines("test phrase", "unknown_type")
        }

        self.assertIn("product launches", guidelines["announcement"])
        self.assertIn("personal stories", guidelines["personal"])
        self.assertIn("strategically", guidelines["unknown"])

    def test_markdown_generation_completeness(self):
        """Test markdown generation includes all sections."""
        tool = SynthesizeStrategyPlaybook(
            keywords=self.sample_keywords,
            triggers=self.sample_triggers,
            post_types=self.sample_post_types,
            tones=self.sample_tones,
            use_llm=False
        )

        result = tool.run()
        parsed_result = json.loads(result)
        markdown = parsed_result["playbook_markdown"]

        # Check all expected sections are present
        expected_sections = [
            "# Content Strategy Playbook",
            "## Executive Summary",
            "## Winning Topics",
            "## High-Impact Trigger Phrases",
            "## Top Performing Content Formats",
            "## Tone & Voice Guidelines",
            "## Content Calendar Framework"
        ]

        for section in expected_sections:
            self.assertIn(section, markdown)


if __name__ == "__main__":
    unittest.main()