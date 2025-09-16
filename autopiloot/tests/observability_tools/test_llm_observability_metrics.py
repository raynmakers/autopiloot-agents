"""
Tests for observability_agent.tools.llm_observability_metrics module.

This module tests the LLMObservabilityMetrics tool which tracks LLM usage,
costs, token consumption, and integrates with Langfuse for observability.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

# Add the parent directories to sys.path for imports
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

from observability_agent.tools.llm_observability_metrics import LLMObservabilityMetrics


class TestLLMObservabilityMetrics(unittest.TestCase):
    """Test cases for LLMObservabilityMetrics observability tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Firestore client
        self.mock_firestore_client = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_query = MagicMock()

        self.mock_firestore_client.collection.return_value = self.mock_collection
        self.mock_collection.where.return_value = self.mock_query
        self.mock_query.where.return_value = self.mock_query
        self.mock_query.order_by.return_value = self.mock_query

        # Sample LLM usage data
        self.sample_llm_usage = [
            self._create_mock_doc('usage1', {
                'model': 'gpt-4o',
                'tokens_input': 1500,
                'tokens_output': 500,
                'cost_usd': 0.045,
                'operation': 'summarization',
                'agent': 'summarizer',
                'timestamp': datetime.now(timezone.utc) - timedelta(hours=1)
            }),
            self._create_mock_doc('usage2', {
                'model': 'gpt-4o-mini',
                'tokens_input': 800,
                'tokens_output': 300,
                'cost_usd': 0.012,
                'operation': 'analysis',
                'agent': 'scraper',
                'timestamp': datetime.now(timezone.utc) - timedelta(hours=2)
            }),
            self._create_mock_doc('usage3', {
                'model': 'gpt-4o',
                'tokens_input': 2000,
                'tokens_output': 800,
                'cost_usd': 0.074,
                'operation': 'error_analysis',
                'agent': 'observability',
                'timestamp': datetime.now(timezone.utc) - timedelta(hours=3)
            })
        ]

    def _create_mock_doc(self, doc_id, data):
        """Create a mock Firestore document."""
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.to_dict.return_value = data
        return mock_doc

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    @patch('observability_agent.tools.llm_observability_metrics.audit_logger')
    def test_successful_llm_metrics_collection(self, mock_audit, mock_env, mock_firestore):
        """Test successful collection of LLM usage metrics."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock LLM usage data
        self.mock_query.stream.return_value = iter(self.sample_llm_usage)

        # Create tool with default parameters
        tool = LLMObservabilityMetrics()

        result = tool.run()
        result_data = json.loads(result)

        # Assert successful metrics collection
        self.assertIn('analysis_timestamp', result_data)
        self.assertIn('usage_summary', result_data)
        self.assertIn('cost_analysis', result_data)
        self.assertIn('model_breakdown', result_data)
        self.assertIn('agent_usage', result_data)

        # Verify usage summary
        summary = result_data['usage_summary']
        self.assertGreater(summary['total_requests'], 0)
        self.assertGreater(summary['total_tokens_input'], 0)
        self.assertGreater(summary['total_tokens_output'], 0)
        self.assertGreater(summary['total_cost_usd'], 0)

        # Verify Firestore operations
        self.mock_firestore_client.collection.assert_called()
        mock_audit.log_action.assert_called()

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_cost_breakdown_analysis(self, mock_env, mock_firestore):
        """Test detailed cost breakdown and analysis."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter(self.sample_llm_usage)

        # Create tool with cost analysis enabled
        tool = LLMObservabilityMetrics(include_cost_breakdown=True)

        result = tool.run()
        result_data = json.loads(result)

        # Verify cost analysis
        cost_analysis = result_data['cost_analysis']
        self.assertIn('total_cost_usd', cost_analysis)
        self.assertIn('cost_by_model', cost_analysis)
        self.assertIn('cost_by_operation', cost_analysis)
        self.assertIn('cost_efficiency', cost_analysis)

        # Should calculate costs correctly
        expected_total = sum(usage.to_dict()['cost_usd'] for usage in self.sample_llm_usage)
        self.assertAlmostEqual(cost_analysis['total_cost_usd'], expected_total, places=3)

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_model_performance_comparison(self, mock_env, mock_firestore):
        """Test comparison of performance across different models."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter(self.sample_llm_usage)

        tool = LLMObservabilityMetrics(include_model_comparison=True)

        result = tool.run()
        result_data = json.loads(result)

        # Should include model breakdown
        model_breakdown = result_data['model_breakdown']
        self.assertIn('gpt-4o', model_breakdown)
        self.assertIn('gpt-4o-mini', model_breakdown)

        # Each model should have usage stats
        for model_name, model_data in model_breakdown.items():
            self.assertIn('request_count', model_data)
            self.assertIn('total_tokens', model_data)
            self.assertIn('total_cost', model_data)
            self.assertIn('avg_cost_per_request', model_data)

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_agent_usage_breakdown(self, mock_env, mock_firestore):
        """Test breakdown of LLM usage by agent."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter(self.sample_llm_usage)

        tool = LLMObservabilityMetrics()

        result = tool.run()
        result_data = json.loads(result)

        # Should include agent usage breakdown
        agent_usage = result_data['agent_usage']
        self.assertIn('summarizer', agent_usage)
        self.assertIn('scraper', agent_usage)
        self.assertIn('observability', agent_usage)

        # Each agent should have detailed metrics
        for agent_name, agent_data in agent_usage.items():
            self.assertIn('requests', agent_data)
            self.assertIn('tokens_used', agent_data)
            self.assertIn('cost_usd', agent_data)
            self.assertIn('operations', agent_data)

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    @patch('observability_agent.tools.llm_observability_metrics.langfuse')
    def test_langfuse_integration(self, mock_langfuse, mock_env, mock_firestore):
        """Test integration with Langfuse for extended observability."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock Langfuse client and data
        mock_langfuse_client = MagicMock()
        mock_langfuse.Langfuse.return_value = mock_langfuse_client

        mock_langfuse_traces = [
            {'id': 'trace1', 'name': 'summarization', 'cost': 0.045},
            {'id': 'trace2', 'name': 'analysis', 'cost': 0.012}
        ]
        mock_langfuse_client.get_traces.return_value = mock_langfuse_traces

        self.mock_query.stream.return_value = iter(self.sample_llm_usage)

        # Create tool with Langfuse integration
        tool = LLMObservabilityMetrics(
            include_langfuse_data=True,
            lookback_hours=24
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should include Langfuse data
        if 'langfuse_metrics' in result_data:
            langfuse_data = result_data['langfuse_metrics']
            self.assertIn('trace_count', langfuse_data)
            self.assertIn('total_traces_cost', langfuse_data)

        # Verify Langfuse client was called
        mock_langfuse_client.get_traces.assert_called()

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_token_usage_analysis(self, mock_env, mock_firestore):
        """Test detailed token usage analysis and patterns."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter(self.sample_llm_usage)

        tool = LLMObservabilityMetrics(include_token_analysis=True)

        result = tool.run()
        result_data = json.loads(result)

        # Should include token analysis
        usage_summary = result_data['usage_summary']
        self.assertIn('total_tokens_input', usage_summary)
        self.assertIn('total_tokens_output', usage_summary)
        self.assertIn('avg_tokens_per_request', usage_summary)

        # Calculate expected values
        total_input = sum(usage.to_dict()['tokens_input'] for usage in self.sample_llm_usage)
        total_output = sum(usage.to_dict()['tokens_output'] for usage in self.sample_llm_usage)

        self.assertEqual(usage_summary['total_tokens_input'], total_input)
        self.assertEqual(usage_summary['total_tokens_output'], total_output)

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_custom_time_range(self, mock_env, mock_firestore):
        """Test metrics collection for custom time ranges."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter(self.sample_llm_usage)

        # Test with 48-hour lookback
        tool = LLMObservabilityMetrics(lookback_hours=48)

        result = tool.run()
        result_data = json.loads(result)

        # Should include time range info
        self.assertEqual(result_data['lookback_hours'], 48)

        # Verify time filter was applied in query
        where_calls = self.mock_query.where.call_args_list
        time_filter_found = any(
            call[0][0] == 'timestamp' and call[0][1] == '>='
            for call in where_calls
        )
        self.assertTrue(time_filter_found)

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_cost_threshold_alerting(self, mock_env, mock_firestore):
        """Test alerting when cost thresholds are exceeded."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Create high-cost usage data
        high_cost_usage = []
        for i in range(10):
            high_cost_usage.append(self._create_mock_doc(f'expensive_{i}', {
                'model': 'gpt-4o',
                'tokens_input': 5000,
                'tokens_output': 2000,
                'cost_usd': 0.15,  # High cost per request
                'operation': 'complex_analysis',
                'agent': 'summarizer',
                'timestamp': datetime.now(timezone.utc) - timedelta(hours=i)
            }))

        self.mock_query.stream.return_value = iter(high_cost_usage)

        # Set low cost threshold to trigger alert
        tool = LLMObservabilityMetrics(
            cost_alert_threshold=0.50,  # $0.50 threshold
            lookback_hours=24
        )

        result = tool.run()
        result_data = json.loads(result)

        # Should include cost alerts
        if 'alerts' in result_data:
            alerts = result_data['alerts']
            cost_alert = next((alert for alert in alerts
                             if 'cost' in alert.get('type', '')), None)
            self.assertIsNotNone(cost_alert)

        # Total cost should exceed threshold
        total_cost = result_data['cost_analysis']['total_cost_usd']
        self.assertGreater(total_cost, 0.50)

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_empty_usage_data(self, mock_env, mock_firestore):
        """Test handling when no LLM usage data is available."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock empty usage data
        self.mock_query.stream.return_value = iter([])

        tool = LLMObservabilityMetrics()

        result = tool.run()
        result_data = json.loads(result)

        # Should handle empty data gracefully
        summary = result_data['usage_summary']
        self.assertEqual(summary['total_requests'], 0)
        self.assertEqual(summary['total_tokens_input'], 0)
        self.assertEqual(summary['total_tokens_output'], 0)
        self.assertEqual(summary['total_cost_usd'], 0.0)

        # Should note no usage in analysis
        self.assertIn('no_usage_detected', result_data)
        self.assertTrue(result_data['no_usage_detected'])

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_operation_type_analysis(self, mock_env, mock_firestore):
        """Test analysis of LLM usage by operation type."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter(self.sample_llm_usage)

        tool = LLMObservabilityMetrics()

        result = tool.run()
        result_data = json.loads(result)

        # Should include operation breakdown in cost analysis
        cost_analysis = result_data['cost_analysis']
        if 'cost_by_operation' in cost_analysis:
            op_costs = cost_analysis['cost_by_operation']
            self.assertIn('summarization', op_costs)
            self.assertIn('analysis', op_costs)
            self.assertIn('error_analysis', op_costs)

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_firestore_query_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore query failures."""
        # Setup mocks to simulate query failure
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        # Mock query failure
        self.mock_query.stream.side_effect = Exception("Query failed")

        tool = LLMObservabilityMetrics()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Query failed', result_data['error'])

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_firestore_connection_failure(self, mock_env, mock_firestore):
        """Test handling of Firestore connection failures."""
        # Setup mocks to simulate connection failure
        mock_firestore.side_effect = Exception("Connection failed")
        mock_env.return_value = 'test-project'

        tool = LLMObservabilityMetrics()

        result = tool.run()
        result_data = json.loads(result)

        # Assert error handling
        self.assertIn('error', result_data)
        self.assertIn('Connection failed', result_data['error'])

    def test_tool_parameter_validation(self):
        """Test parameter validation and defaults."""
        # Test valid parameters
        tool = LLMObservabilityMetrics(
            lookback_hours=48,
            include_cost_breakdown=False,
            cost_alert_threshold=1.0
        )
        self.assertEqual(tool.lookback_hours, 48)
        self.assertFalse(tool.include_cost_breakdown)
        self.assertEqual(tool.cost_alert_threshold, 1.0)

        # Test defaults
        tool_defaults = LLMObservabilityMetrics()
        self.assertEqual(tool_defaults.lookback_hours, 24)
        self.assertTrue(tool_defaults.include_cost_breakdown)
        self.assertEqual(tool_defaults.cost_alert_threshold, 10.0)

    def test_tool_properties(self):
        """Test that the tool has correct properties."""
        tool = LLMObservabilityMetrics(
            lookback_hours=12,
            include_model_comparison=False
        )

        # Test that it's a BaseTool
        self.assertIsInstance(tool, LLMObservabilityMetrics)

        # Test parameter values
        self.assertEqual(tool.lookback_hours, 12)
        self.assertFalse(tool.include_model_comparison)

    @patch('observability_agent.tools.llm_observability_metrics.firestore.Client')
    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_efficiency_metrics_calculation(self, mock_env, mock_firestore):
        """Test calculation of cost efficiency metrics."""
        # Setup mocks
        mock_firestore.return_value = self.mock_firestore_client
        mock_env.return_value = 'test-project'

        self.mock_query.stream.return_value = iter(self.sample_llm_usage)

        tool = LLMObservabilityMetrics(include_cost_breakdown=True)

        result = tool.run()
        result_data = json.loads(result)

        # Should include efficiency metrics
        cost_analysis = result_data['cost_analysis']
        if 'cost_efficiency' in cost_analysis:
            efficiency = cost_analysis['cost_efficiency']
            self.assertIn('cost_per_token', efficiency)
            self.assertIn('tokens_per_dollar', efficiency)

            # Values should be reasonable
            self.assertGreater(efficiency['cost_per_token'], 0)
            self.assertGreater(efficiency['tokens_per_dollar'], 0)


if __name__ == '__main__':
    unittest.main()