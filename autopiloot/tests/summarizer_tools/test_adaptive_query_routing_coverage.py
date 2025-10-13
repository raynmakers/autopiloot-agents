"""
Comprehensive test suite for AdaptiveQueryRouting tool.
Tests intent detection, filter analysis, routing rules, and fallback mechanisms.
Target: 80%+ coverage with success paths, error paths, and edge cases.
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Mock agency_swarm before importing tool
mock_agency_swarm = MagicMock()
mock_base_tool = MagicMock()
mock_agency_swarm.tools.BaseTool = mock_base_tool
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['agency_swarm.tools'] = mock_agency_swarm.tools


class TestAdaptiveQueryRouting(unittest.TestCase):
    """Test suite for AdaptiveQueryRouting tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Import tool after mocks are in place
        import importlib.util
        tool_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'summarizer_agent',
            'tools',
            'adaptive_query_routing.py'
        )
        spec = importlib.util.spec_from_file_location("adaptive_query_routing", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.AdaptiveQueryRouting

    def test_detect_conceptual_intent(self):
        """Test detection of conceptual query intent (lines 64-113)."""
        tool = self.ToolClass(query="How to build a sales team")

        intent = tool._detect_query_intent("How to build a high-performance sales team")

        self.assertEqual(intent["intent_type"], "conceptual")
        self.assertIn("how to", intent["conceptual_signals"])
        self.assertGreater(len(intent["conceptual_signals"]), 0)
        self.assertGreaterEqual(intent["complexity_score"], 0.0)
        self.assertLessEqual(intent["complexity_score"], 1.0)

    def test_detect_factual_intent(self):
        """Test detection of factual query intent (lines 64-113)."""
        tool = self.ToolClass(query="When was this video published")

        intent = tool._detect_query_intent("When was the pricing video published and who created it?")

        self.assertEqual(intent["intent_type"], "factual")
        self.assertIn("when", intent["factual_signals"])
        self.assertIn("who", intent["factual_signals"])
        self.assertGreater(len(intent["factual_signals"]), 0)

    def test_detect_mixed_intent(self):
        """Test detection of mixed query intent (lines 64-113)."""
        tool = self.ToolClass(query="test")

        intent = tool._detect_query_intent("How to price SaaS products when launching")

        # Should detect both conceptual ("how to") and factual ("when") signals
        self.assertIn(intent["intent_type"], ["mixed", "conceptual", "factual"])
        self.assertGreaterEqual(len(intent["conceptual_signals"]) + len(intent["factual_signals"]), 1)

    def test_detect_filter_strength_strong(self):
        """Test strong filter detection (lines 115-133)."""
        tool = self.ToolClass(
            query="test",
            channel_id="UC123",
            min_published_date="2025-01-01",
            max_published_date="2025-12-31"
        )

        filter_strength = tool._detect_filter_strength(
            "UC123",
            "2025-01-01",
            "2025-12-31"
        )

        self.assertEqual(filter_strength, "strong")

    def test_detect_filter_strength_moderate(self):
        """Test moderate filter detection (lines 115-133)."""
        tool = self.ToolClass(
            query="test",
            channel_id="UC123"
        )

        filter_strength = tool._detect_filter_strength(
            "UC123",
            None,
            None
        )

        self.assertEqual(filter_strength, "moderate")

    def test_detect_filter_strength_none(self):
        """Test no filter detection (lines 115-133)."""
        tool = self.ToolClass(query="test")

        filter_strength = tool._detect_filter_strength(None, None, None)

        self.assertEqual(filter_strength, "none")

    @patch.dict(os.environ, {
        'ZEP_API_KEY': 'test_zep',
        'OPENSEARCH_HOST': 'test_opensearch',
        'GCP_PROJECT_ID': 'test_project',
        'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'
    })
    @patch('importlib.import_module')
    def test_check_source_availability_all_available(self, mock_import):
        """Test source availability when all sources configured (lines 135-153)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.bigquery.enabled': True
        }.get(key, default))
        mock_import.return_value = mock_loader

        tool = self.ToolClass(query="test")
        availability = tool._check_source_availability()

        self.assertTrue(availability["zep"])
        self.assertTrue(availability["opensearch"])
        self.assertTrue(availability["bigquery"])

    @patch.dict(os.environ, {})
    @patch('importlib.import_module')
    def test_check_source_availability_none_available(self, mock_import):
        """Test source availability when no sources configured (lines 135-153)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(return_value=False)
        mock_import.return_value = mock_loader

        tool = self.ToolClass(query="test")
        availability = tool._check_source_availability()

        self.assertFalse(availability["zep"])
        self.assertFalse(availability["opensearch"])
        self.assertFalse(availability["bigquery"])

    def test_apply_routing_rules_strong_filters(self):
        """Test routing with strong filters (lines 155-207, Rule 1)."""
        tool = self.ToolClass(query="test")

        intent = {"intent_type": "factual", "complexity_score": 0.5}
        filter_strength = "strong"
        availability = {"zep": True, "opensearch": True, "bigquery": True}

        decision = tool._apply_routing_rules(intent, filter_strength, availability)

        # Strong filters should select OpenSearch + BigQuery
        self.assertIn("opensearch", decision["selected_sources"])
        self.assertIn("bigquery", decision["selected_sources"])
        self.assertIn("filter_optimized", decision["routing_strategy"])

    def test_apply_routing_rules_conceptual_no_filters(self):
        """Test routing with conceptual query and no filters (lines 155-207, Rule 2)."""
        tool = self.ToolClass(query="test")

        intent = {"intent_type": "conceptual", "complexity_score": 0.3}
        filter_strength = "none"
        availability = {"zep": True, "opensearch": True, "bigquery": False}

        decision = tool._apply_routing_rules(intent, filter_strength, availability)

        # Conceptual without filters should prefer Zep
        self.assertIn("zep", decision["selected_sources"])
        self.assertIn("semantic_optimized", decision["routing_strategy"])

    def test_apply_routing_rules_factual_with_filters(self):
        """Test routing with factual query and moderate filters (lines 155-207, Rule 3)."""
        tool = self.ToolClass(query="test")

        intent = {"intent_type": "factual", "complexity_score": 0.4}
        filter_strength = "moderate"
        availability = {"zep": True, "opensearch": True, "bigquery": True}

        decision = tool._apply_routing_rules(intent, filter_strength, availability)

        # Factual with filters should select OpenSearch + BigQuery
        self.assertIn("opensearch", decision["selected_sources"])
        self.assertIn("bigquery", decision["selected_sources"])
        self.assertIn("keyword_optimized", decision["routing_strategy"])

    def test_apply_routing_rules_mixed_intent(self):
        """Test routing with mixed intent (lines 155-207, Rule 4)."""
        tool = self.ToolClass(query="test")

        intent = {"intent_type": "mixed", "complexity_score": 0.6}
        filter_strength = "moderate"
        availability = {"zep": True, "opensearch": True, "bigquery": True}

        decision = tool._apply_routing_rules(intent, filter_strength, availability)

        # Mixed intent should use all available sources
        self.assertIn("zep", decision["selected_sources"])
        self.assertIn("opensearch", decision["selected_sources"])
        self.assertIn("bigquery", decision["selected_sources"])
        self.assertEqual(decision["routing_strategy"], "comprehensive")

    def test_apply_routing_rules_fallback(self):
        """Test routing fallback when no rules match (lines 155-207, Rule 5)."""
        tool = self.ToolClass(query="test")

        intent = {"intent_type": "unknown", "complexity_score": 0.1}
        filter_strength = "none"
        availability = {"zep": True, "opensearch": False, "bigquery": False}

        decision = tool._apply_routing_rules(intent, filter_strength, availability)

        # Fallback should use all available sources
        self.assertIn("zep", decision["selected_sources"])
        self.assertGreater(len(decision["reasoning"]), 0)

    def test_apply_routing_rules_no_sources_available(self):
        """Test routing when no sources available (lines 155-207)."""
        tool = self.ToolClass(query="test")

        intent = {"intent_type": "conceptual", "complexity_score": 0.5}
        filter_strength = "none"
        availability = {"zep": False, "opensearch": False, "bigquery": False}

        decision = tool._apply_routing_rules(intent, filter_strength, availability)

        # Should have empty sources but include warning reasoning
        self.assertEqual(len(decision["selected_sources"]), 0)
        self.assertTrue(any("No sources available" in r for r in decision["reasoning"]))

    @patch.dict(os.environ, {'ZEP_API_KEY': 'test', 'OPENSEARCH_HOST': 'test'})
    @patch('importlib.import_module')
    def test_adaptive_mode_routing(self, mock_import):
        """Test full routing in adaptive mode (lines 209-305)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.routing.mode': 'adaptive',
            'rag.routing.always_use_all_sources': False,
            'rag.bigquery.enabled': False
        }.get(key, default))
        mock_import.return_value = mock_loader

        tool = self.ToolClass(
            query="How to build a sales team"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertEqual(data["routing_mode"], "adaptive")
        self.assertIn("routing_decision", data)
        self.assertIn("query_analysis", data)
        self.assertIn("intent", data["query_analysis"])

    @patch.dict(os.environ, {'ZEP_API_KEY': 'test', 'OPENSEARCH_HOST': 'test'})
    @patch('importlib.import_module')
    def test_always_on_mode_routing(self, mock_import):
        """Test routing in always-on mode (lines 275-284)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.routing.mode': 'always_on',
            'rag.routing.always_use_all_sources': True,
            'rag.bigquery.enabled': False
        }.get(key, default))
        mock_import.return_value = mock_loader

        tool = self.ToolClass(
            query="test query"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertEqual(data["routing_decision"]["routing_strategy"], "always_on")
        # Should use all available sources
        self.assertIn("zep", data["routing_decision"]["selected_sources"])
        self.assertIn("opensearch", data["routing_decision"]["selected_sources"])

    @patch.dict(os.environ, {'ZEP_API_KEY': 'test'})
    @patch('importlib.import_module')
    def test_forced_sources_routing(self, mock_import):
        """Test routing with forced sources (lines 265-273)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.routing.mode': 'adaptive',
            'rag.routing.always_use_all_sources': False
        }.get(key, default))
        mock_import.return_value = mock_loader

        tool = self.ToolClass(
            query="test query",
            force_sources=["zep"]
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertEqual(data["routing_decision"]["routing_strategy"], "forced")
        self.assertEqual(data["routing_decision"]["selected_sources"], ["zep"])

    @patch.dict(os.environ, {})
    @patch('importlib.import_module')
    def test_no_sources_available_status(self, mock_import):
        """Test status when no sources available (lines 315-319)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.routing.mode': 'adaptive',
            'rag.routing.always_use_all_sources': False,
            'rag.bigquery.enabled': False
        }.get(key, default))
        mock_import.return_value = mock_loader

        tool = self.ToolClass(query="test")

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "no_sources_available")
        self.assertEqual(len(data["routing_decision"]["selected_sources"]), 0)

    def test_query_analysis_includes_filters(self):
        """Test that query analysis captures filter presence (lines 308-319)."""
        tool = self.ToolClass(
            query="test",
            channel_id="UC123",
            min_published_date="2025-01-01"
        )

        # Mock the imports and config
        with patch('importlib.import_module') as mock_import:
            mock_loader = MagicMock()
            mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
                'rag.routing.mode': 'adaptive',
                'rag.routing.always_use_all_sources': False,
                'rag.bigquery.enabled': False
            }.get(key, default))
            mock_import.return_value = mock_loader

            result = tool.run()
            data = json.loads(result)

        self.assertTrue(data["query_analysis"]["has_channel_filter"])
        self.assertTrue(data["query_analysis"]["has_date_filter"])
        self.assertEqual(data["query_analysis"]["filters_provided"]["channel_id"], "UC123")
        self.assertEqual(data["query_analysis"]["filters_provided"]["min_date"], "2025-01-01")

    def test_classify_routing_strategy(self):
        """Test routing strategy classification (lines 229-237)."""
        tool = self.ToolClass(query="test")

        # Test filter_optimized
        strategy = tool._classify_routing_strategy("strong", "factual")
        self.assertEqual(strategy, "filter_optimized")

        # Test semantic_optimized
        strategy = tool._classify_routing_strategy("none", "conceptual")
        self.assertEqual(strategy, "semantic_optimized")

        # Test keyword_optimized
        strategy = tool._classify_routing_strategy("moderate", "factual")
        self.assertEqual(strategy, "keyword_optimized")

        # Test comprehensive
        strategy = tool._classify_routing_strategy("moderate", "mixed")
        self.assertEqual(strategy, "comprehensive")

    @patch('importlib.import_module')
    def test_exception_handling(self, mock_import):
        """Test general exception handling (lines 333-338)."""
        # Mock loader to raise exception
        mock_import.side_effect = Exception("Test exception")

        tool = self.ToolClass(query="test")

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "routing_failed")
        self.assertIn("Test exception", data["message"])

    def test_timestamp_generation(self):
        """Test timestamp generation (lines 340-343)."""
        tool = self.ToolClass(query="test")

        timestamp = tool._get_timestamp()

        # Should be ISO 8601 format with timezone
        self.assertIn("T", timestamp)
        self.assertTrue(timestamp.endswith("Z") or "+" in timestamp)


if __name__ == '__main__':
    unittest.main()
