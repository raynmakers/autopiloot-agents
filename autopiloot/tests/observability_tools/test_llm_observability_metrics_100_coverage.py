"""
Comprehensive test suite for llm_observability_metrics.py targeting 100% coverage.
Focuses on missing lines: 93-129, 150-173, 295-325, 341-342, 358-363, 386-396, 417-461, 465-479, 486-491, 497, 499, 507-515, 522, 534-547, 552-567, 571-578, 589
"""

import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timezone, timedelta

# Mock external dependencies before imports
mock_modules = {
    'google': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'dotenv': MagicMock(),
}

for module_name, mock_module in mock_modules.items():
    sys.modules[module_name] = mock_module

# Mock BaseTool and Field
class MockBaseTool:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

def mock_field(*args, **kwargs):
    return kwargs.get('default', None)

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
sys.modules['pydantic'].Field = mock_field

# Now import the tool
from observability_agent.tools.llm_observability_metrics import LLMObservabilityMetrics


class TestLLMObservabilityMetrics100Coverage(unittest.TestCase):
    """Test LLMObservabilityMetrics to achieve 100% coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()
        self.mock_firestore_client = MagicMock()

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    @patch('observability_agent.tools.llm_observability_metrics.audit_logger')
    def test_successful_run_with_all_options(self, mock_audit, mock_get_env):
        """Test successful run with all options enabled (lines 93-129)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(
            time_window_hours=24,
            include_prompt_analysis=True,
            include_cost_breakdown=True,
            emit_to_langfuse=True
        )

        # Mock Firestore initialization
        with patch.object(tool, '_initialize_firestore', return_value=self.mock_db):
            # Mock all private methods
            with patch.object(tool, '_collect_usage_metrics', return_value={
                'total_requests': 100,
                'requests_per_hour': 4.2,
                'requests_by_model': {'gpt-4o': 60, 'gpt-3.5-turbo': 40},
                'requests_by_task': {'summarization': 100},
                'average_response_time_ms': 1500,
                'response_time_p95_ms': 2500,
                'duration_hours': 24
            }):
                with patch.object(tool, '_analyze_token_usage', return_value={
                    'total_tokens': 350000,
                    'input_tokens': 200000,
                    'output_tokens': 150000,
                    'average_tokens_per_request': 3500
                }):
                    with patch.object(tool, '_calculate_cost_metrics', return_value={
                        'total_cost': 12.50,
                        'cost_per_request': 0.125
                    }):
                        with patch.object(tool, '_analyze_prompt_performance', return_value={
                            'analyzed_prompts': 2,
                            'prompt_performance': {}
                        }):
                            with patch.object(tool, '_analyze_model_performance', return_value={
                                'models_analyzed': 2
                            }):
                                with patch.object(tool, '_calculate_efficiency_metrics', return_value={
                                    'efficiency_scores': {'overall_efficiency': 85.0}
                                }):
                                    with patch.object(tool, '_generate_llm_insights', return_value=[]):
                                        with patch.object(tool, '_emit_to_langfuse', return_value={'status': 'success'}):
                                            result = tool.run()

        # Verify result
        self.assertIsInstance(result, str)
        data = json.loads(result)
        self.assertIn('usage_metrics', data)
        self.assertIn('token_metrics', data)
        self.assertIn('cost_metrics', data)
        self.assertIn('prompt_analysis', data)
        self.assertIn('langfuse_export', data)

        # Verify audit logger called (lines 121-127)
        mock_audit.log_llm_metrics_collected.assert_called_once()

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_collect_usage_metrics_with_data(self, mock_get_env):
        """Test _collect_usage_metrics with actual data (lines 150-173)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Mock Firestore query
        mock_log_1 = MagicMock()
        mock_log_1.to_dict.return_value = {
            'timestamp': datetime.now(timezone.utc),
            'action': 'llm_request',
            'details': {
                'model': 'gpt-4o',
                'task_type': 'summarization',
                'response_time_ms': 1200
            }
        }

        mock_log_2 = MagicMock()
        mock_log_2.to_dict.return_value = {
            'timestamp': datetime.now(timezone.utc),
            'action': 'summary_generated',
            'details': {
                'model': 'gpt-3.5-turbo',
                'task_type': 'translation',
                'response_time_ms': 800
            }
        }

        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_log_1, mock_log_2]

        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_collection
        mock_collection.limit.return_value = mock_query

        self.mock_db.collection.return_value = mock_collection

        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        end_time = datetime.now(timezone.utc)

        result = tool._collect_usage_metrics(self.mock_db, start_time, end_time)

        # Verify result structure (lines 150-173)
        self.assertEqual(result['total_requests'], 2)
        self.assertIn('requests_by_model', result)
        self.assertIn('requests_by_task', result)
        self.assertIn('average_response_time_ms', result)
        self.assertEqual(result['requests_by_model']['gpt-4o'], 1)
        self.assertEqual(result['requests_by_model']['gpt-3.5-turbo'], 1)

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    @patch('observability_agent.tools.llm_observability_metrics.load_app_config')
    def test_analyze_prompt_performance_with_data(self, mock_config, mock_get_env):
        """Test _analyze_prompt_performance with actual prompt data (lines 295-325)."""
        mock_get_env.return_value = "test-project"
        mock_config.return_value = {
            'llm': {
                'tasks': {
                    'summarizer_generate_short': {
                        'prompt_id': 'prompt_v2_summarizer',
                        'prompt_version': 'v2'
                    }
                }
            }
        }

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Mock Firestore summaries query
        mock_summary_1 = MagicMock()
        mock_summary_1.to_dict.return_value = {
            'created_at': datetime.now(timezone.utc),
            'prompt_id': 'prompt_v2_summarizer',
            'summary_text': 'This is a comprehensive summary with more than 100 characters to be considered successful and high quality.'
        }

        mock_summary_2 = MagicMock()
        mock_summary_2.to_dict.return_value = {
            'created_at': datetime.now(timezone.utc),
            'prompt_id': 'prompt_v2_summarizer',
            'summary_text': 'Short summary'  # Less than 100 chars - not successful
        }

        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_summary_1, mock_summary_2]

        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_collection
        mock_collection.limit.return_value = mock_query

        self.mock_db.collection.return_value = mock_collection

        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        end_time = datetime.now(timezone.utc)

        result = tool._analyze_prompt_performance(self.mock_db, start_time, end_time)

        # Verify prompt analysis (lines 295-325)
        self.assertIn('analyzed_prompts', result)
        self.assertIn('prompt_performance', result)
        self.assertEqual(result['analyzed_prompts'], 1)
        self.assertIn('prompt_v2_summarizer', result['prompt_performance'])

        prompt_perf = result['prompt_performance']['prompt_v2_summarizer']
        self.assertEqual(prompt_perf['usage_count'], 2)
        self.assertEqual(prompt_perf['success_rate'], 50.0)  # 1 out of 2 successful
        self.assertIn('effectiveness_score', prompt_perf)

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_analyze_prompt_performance_exception(self, mock_get_env):
        """Test _analyze_prompt_performance exception handling (lines 341-342)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Mock exception in config loading
        with patch('observability_agent.tools.llm_observability_metrics.load_app_config', side_effect=Exception("Config error")):
            start_time = datetime.now(timezone.utc) - timedelta(hours=24)
            end_time = datetime.now(timezone.utc)

            result = tool._analyze_prompt_performance(self.mock_db, start_time, end_time)

            # Should return empty result (lines 341-347)
            self.assertEqual(result['analyzed_prompts'], 0)
            self.assertEqual(result['prompt_performance'], {})
            self.assertIsNone(result['top_performing_prompt'])
            self.assertEqual(result['recommendations'], [])

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_analyze_model_performance(self, mock_get_env):
        """Test _analyze_model_performance with multiple models (lines 358-363)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        usage_metrics = {
            'total_requests': 100,
            'requests_by_model': {
                'gpt-4o': 60,
                'gpt-3.5-turbo': 30,
                'claude-3': 10
            },
            'average_response_time_ms': 2000
        }

        result = tool._analyze_model_performance(usage_metrics)

        # Verify model analysis (lines 358-363)
        self.assertEqual(result['models_analyzed'], 3)
        self.assertEqual(result['primary_model'], 'gpt-4o')
        self.assertEqual(result['model_diversity'], 3)

        # Check individual model analysis
        gpt4_analysis = result['model_analysis']['gpt-4o']
        self.assertEqual(gpt4_analysis['request_count'], 60)
        self.assertEqual(gpt4_analysis['usage_percentage'], 60.0)
        self.assertIn('estimated_performance_score', gpt4_analysis)
        self.assertIn('recommendation', gpt4_analysis)

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_calculate_efficiency_metrics(self, mock_get_env):
        """Test _calculate_efficiency_metrics comprehensive calculation (lines 386-396)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        usage_metrics = {
            'total_requests': 100,
            'duration_hours': 24,
            'average_response_time_ms': 1500
        }

        token_metrics = {
            'total_tokens': 350000,
            'average_tokens_per_request': 3500
        }

        cost_metrics = {
            'total_cost': 12.50,
            'cost_per_request': 0.125
        }

        result = tool._calculate_efficiency_metrics(usage_metrics, token_metrics, cost_metrics)

        # Verify efficiency calculations (lines 386-396)
        self.assertIn('throughput', result)
        self.assertIn('efficiency_scores', result)
        self.assertIn('resource_utilization', result)

        # Check throughput metrics
        self.assertAlmostEqual(result['throughput']['requests_per_hour'], 100/24, places=2)
        self.assertAlmostEqual(result['throughput']['tokens_per_hour'], 350000/24, places=0)
        self.assertAlmostEqual(result['throughput']['cost_per_hour'], 12.50/24, places=4)

        # Check efficiency scores
        efficiency = result['efficiency_scores']
        self.assertIn('cost_efficiency', efficiency)
        self.assertIn('token_efficiency', efficiency)
        self.assertIn('speed_efficiency', efficiency)
        self.assertIn('overall_efficiency', efficiency)

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_generate_llm_insights_all_scenarios(self, mock_get_env):
        """Test _generate_llm_insights with all insight types (lines 417-461)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Scenario 1: High monthly cost warning (lines 423-429)
        usage_metrics_high_cost = {
            'average_response_time_ms': 1000,
            'requests_by_model': {'gpt-4o': 100}
        }
        token_metrics_high_cost = {'average_tokens_per_request': 3000}
        cost_metrics_high_cost = {
            'total_cost': 50.0,
            'estimated_monthly_cost': 150.0  # > 100 threshold
        }

        insights = tool._generate_llm_insights(usage_metrics_high_cost, token_metrics_high_cost, cost_metrics_high_cost, {})

        # Should have cost alert (lines 423-429)
        cost_alerts = [i for i in insights if i['type'] == 'cost_alert']
        self.assertGreater(len(cost_alerts), 0)
        self.assertEqual(cost_alerts[0]['severity'], 'warning')

        # Scenario 2: Slow response time warning (lines 432-439)
        usage_metrics_slow = {
            'average_response_time_ms': 6000,  # > 5000 threshold
            'requests_by_model': {'gpt-4o': 100}
        }
        token_metrics_slow = {'average_tokens_per_request': 2000}
        cost_metrics_slow = {
            'total_cost': 10.0,
            'estimated_monthly_cost': 30.0
        }

        insights = tool._generate_llm_insights(usage_metrics_slow, token_metrics_slow, cost_metrics_slow, {})

        # Should have performance concern (lines 432-439)
        perf_alerts = [i for i in insights if i['type'] == 'performance_concern']
        self.assertGreater(len(perf_alerts), 0)
        self.assertEqual(perf_alerts[0]['severity'], 'warning')

        # Scenario 3: High token usage (lines 442-449)
        usage_metrics_tokens = {
            'average_response_time_ms': 1000,
            'requests_by_model': {'gpt-4o': 100}
        }
        token_metrics_high = {'average_tokens_per_request': 5000}  # > 4000 threshold
        cost_metrics_tokens = {
            'total_cost': 10.0,
            'estimated_monthly_cost': 30.0
        }

        insights = tool._generate_llm_insights(usage_metrics_tokens, token_metrics_high, cost_metrics_tokens, {})

        # Should have token efficiency insight (lines 442-449)
        token_alerts = [i for i in insights if i['type'] == 'token_efficiency']
        self.assertGreater(len(token_alerts), 0)
        self.assertEqual(token_alerts[0]['severity'], 'info')

        # Scenario 4: Single model usage (lines 452-459)
        usage_metrics_single = {
            'average_response_time_ms': 1000,
            'requests_by_model': {'gpt-4o': 100}  # Only 1 model
        }
        token_metrics_single = {'average_tokens_per_request': 2000}
        cost_metrics_single = {
            'total_cost': 10.0,
            'estimated_monthly_cost': 30.0
        }

        insights = tool._generate_llm_insights(usage_metrics_single, token_metrics_single, cost_metrics_single, {})

        # Should have model optimization insight (lines 452-459)
        model_alerts = [i for i in insights if i['type'] == 'model_optimization']
        self.assertGreater(len(model_alerts), 0)
        self.assertEqual(model_alerts[0]['severity'], 'info')

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    @patch('observability_agent.tools.llm_observability_metrics.get_optional_env_var')
    def test_emit_to_langfuse_scenarios(self, mock_get_optional, mock_get_required):
        """Test _emit_to_langfuse success and failure scenarios (lines 465-479)."""
        mock_get_required.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Scenario 1: No API key configured (lines 466-468)
        mock_get_optional.return_value = None

        result = tool._emit_to_langfuse({'test': 'metrics'})
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'No Langfuse API key configured')

        # Scenario 2: API key configured (lines 470-476)
        mock_get_optional.return_value = "test-api-key"

        result = tool._emit_to_langfuse({'test': 'metrics'})
        self.assertEqual(result['status'], 'success')
        self.assertIn('exported_metrics', result)
        self.assertIn('export_timestamp', result)

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_calculate_percentile(self, mock_get_env):
        """Test _calculate_percentile with various inputs (lines 486-491)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Empty list (line 487)
        result = tool._calculate_percentile([], 95)
        self.assertEqual(result, 0)

        # Single value (line 490)
        result = tool._calculate_percentile([100], 95)
        self.assertEqual(result, 100)

        # Multiple values (lines 489-491)
        values = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        result = tool._calculate_percentile(values, 95)
        self.assertGreaterEqual(result, 900)  # 95th percentile should be near top

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_calculate_cost_efficiency_score(self, mock_get_env):
        """Test _calculate_cost_efficiency_score with all thresholds (lines 497, 499)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Very cheap (line 503)
        score = tool._calculate_cost_efficiency_score(0.005)
        self.assertEqual(score, 100)

        # Moderate cost (line 501)
        score = tool._calculate_cost_efficiency_score(0.03)
        self.assertEqual(score, 80)

        # High cost (line 499)
        score = tool._calculate_cost_efficiency_score(0.08)
        self.assertEqual(score, 50)

        # Very expensive (line 497)
        score = tool._calculate_cost_efficiency_score(0.15)
        self.assertEqual(score, 0)

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_calculate_prompt_effectiveness(self, mock_get_env):
        """Test _calculate_prompt_effectiveness calculation (lines 507-515)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Zero count (line 507-508)
        score = tool._calculate_prompt_effectiveness(0, 0, 0)
        self.assertEqual(score, 0)

        # Perfect success rate, good length (lines 510-515)
        score = tool._calculate_prompt_effectiveness(10, 10, 5000)
        self.assertGreater(score, 80)  # Should be high score

        # Partial success (lines 510-515)
        score = tool._calculate_prompt_effectiveness(5, 10, 2500)
        self.assertLess(score, 80)  # Should be lower

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_get_top_performing_prompt(self, mock_get_env):
        """Test _get_top_performing_prompt selection (line 522)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Empty performance data (line 519-520)
        result = tool._get_top_performing_prompt({})
        self.assertIsNone(result)

        # Multiple prompts (lines 522-523)
        prompt_performance = {
            'prompt_a': {'effectiveness_score': 85.0},
            'prompt_b': {'effectiveness_score': 92.0},
            'prompt_c': {'effectiveness_score': 78.0}
        }

        result = tool._get_top_performing_prompt(prompt_performance)
        self.assertEqual(result, 'prompt_b')  # Highest score

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_generate_prompt_recommendations(self, mock_get_env):
        """Test _generate_prompt_recommendations with various scenarios (lines 534-547)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # No data (lines 529-531)
        recommendations = tool._generate_prompt_recommendations({})
        self.assertGreater(len(recommendations), 0)
        self.assertIn("No prompt performance data", recommendations[0])

        # Significant performance difference (lines 534-540)
        prompt_performance_diff = {
            'prompt_good': {'effectiveness_score': 90.0, 'success_rate': 95.0},
            'prompt_bad': {'effectiveness_score': 65.0, 'success_rate': 70.0}
        }

        recommendations = tool._generate_prompt_recommendations(prompt_performance_diff)
        migration_recs = [r for r in recommendations if 'migrating from' in r]
        self.assertGreater(len(migration_recs), 0)

        # Low success rate (lines 543-545)
        prompt_performance_low = {
            'prompt_low_success': {'effectiveness_score': 75.0, 'success_rate': 70.0}  # < 80%
        }

        recommendations = tool._generate_prompt_recommendations(prompt_performance_low)
        success_recs = [r for r in recommendations if 'success rate below 80%' in r]
        self.assertGreater(len(success_recs), 0)

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_estimate_model_performance(self, mock_get_env):
        """Test _estimate_model_performance with response time adjustments (lines 552-567)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Fast response (no penalty)
        score = tool._estimate_model_performance('gpt-4o', 2000)
        self.assertEqual(score, 90)  # Base score

        # Moderate response (line 564-565)
        score = tool._estimate_model_performance('gpt-4o', 4000)
        self.assertEqual(score, 80)  # Base 90 - 10 penalty

        # Slow response (line 562-563)
        score = tool._estimate_model_performance('gpt-4o', 6000)
        self.assertEqual(score, 70)  # Base 90 - 20 penalty

        # Unknown model (line 559)
        score = tool._estimate_model_performance('unknown-model', 2000)
        self.assertEqual(score, 70)  # Default base score

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_get_model_recommendation(self, mock_get_env):
        """Test _get_model_recommendation with different scenarios (lines 571-578)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Low performance (line 571-572)
        rec = tool._get_model_recommendation('gpt-3.5-turbo', 50.0, 55.0)
        self.assertIn("higher-performance", rec)

        # High usage (line 573-574)
        rec = tool._get_model_recommendation('gpt-4o', 85.0, 90.0)
        self.assertIn("Dominant model", rec)

        # Low usage (line 575-576)
        rec = tool._get_model_recommendation('claude-3', 5.0, 80.0)
        self.assertIn("Low usage", rec)

        # Optimal usage (line 577-578)
        rec = tool._get_model_recommendation('gpt-4o', 45.0, 85.0)
        self.assertIn("optimal", rec)

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    @patch('observability_agent.tools.llm_observability_metrics.firestore')
    def test_initialize_firestore_success(self, mock_firestore_module, mock_get_env):
        """Test _initialize_firestore successful initialization (line 589)."""
        mock_get_env.side_effect = lambda var, desc=None: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/credentials.json"
        }.get(var, None)

        # Mock file exists
        with patch('os.path.exists', return_value=True):
            tool = LLMObservabilityMetrics(time_window_hours=24)

            mock_client = MagicMock()
            mock_firestore_module.Client.return_value = mock_client

            result = tool._initialize_firestore()

            # Verify Firestore client created (line 589)
            mock_firestore_module.Client.assert_called_once_with(project="test-project")
            self.assertEqual(result, mock_client)

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_initialize_firestore_missing_credentials(self, mock_get_env):
        """Test _initialize_firestore with missing credentials file."""
        mock_get_env.side_effect = lambda var, desc=None: {
            "GCP_PROJECT_ID": "test-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/nonexistent/credentials.json"
        }.get(var, None)

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Mock file does not exist
        with patch('os.path.exists', return_value=False):
            with self.assertRaises(RuntimeError) as context:
                tool._initialize_firestore()

            self.assertIn("Failed to initialize Firestore", str(context.exception))


    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_run_exception_handling(self, mock_get_env):
        """Test run() exception handling (lines 131-132)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Force exception in _initialize_firestore
        with patch.object(tool, '_initialize_firestore', side_effect=Exception("Firestore init failed")):
            result = tool.run()

        # Should return error JSON (lines 131-135)
        data = json.loads(result)
        self.assertIn('error', data)
        self.assertIn('Failed to collect LLM metrics', data['error'])
        self.assertIsNone(data['metrics'])

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_collect_usage_metrics_exception(self, mock_get_env):
        """Test _collect_usage_metrics exception handling (lines 183-184)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        # Mock Firestore query that raises exception
        mock_collection = MagicMock()
        mock_collection.where.side_effect = Exception("Firestore query failed")
        self.mock_db.collection.return_value = mock_collection

        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        end_time = datetime.now(timezone.utc)

        result = tool._collect_usage_metrics(self.mock_db, start_time, end_time)

        # Should return empty metrics (lines 183-192)
        self.assertEqual(result['total_requests'], 0)
        self.assertEqual(result['requests_per_hour'], 0)
        self.assertEqual(result['requests_by_model'], {})
        self.assertEqual(result['requests_by_task'], {})
        self.assertEqual(result['average_response_time_ms'], 0)
        self.assertEqual(result['response_time_p95_ms'], 0)
        self.assertEqual(result['duration_hours'], 0)

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_analyze_token_usage_complete(self, mock_get_env):
        """Test _analyze_token_usage with comprehensive model coverage (lines 199-230)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        usage_metrics = {
            'total_requests': 150,
            'requests_by_model': {
                'gpt-4o': 50,
                'gpt-4.1': 30,
                'gpt-3.5-turbo': 40,
                'claude-3': 20,
                'unknown-model': 10
            }
        }

        result = tool._analyze_token_usage(usage_metrics)

        # Verify all models processed (lines 214-226)
        self.assertEqual(len(result['tokens_by_model']), 5)
        self.assertIn('gpt-4o', result['tokens_by_model'])
        self.assertIn('gpt-4.1', result['tokens_by_model'])
        self.assertIn('gpt-3.5-turbo', result['tokens_by_model'])
        self.assertIn('claude-3', result['tokens_by_model'])
        self.assertIn('unknown-model', result['tokens_by_model'])

        # Verify token calculations (lines 210-228)
        gpt4o_tokens = result['tokens_by_model']['gpt-4o']
        self.assertEqual(gpt4o_tokens['input_tokens'], 50 * 2000)
        self.assertEqual(gpt4o_tokens['output_tokens'], 50 * 1500)
        self.assertEqual(gpt4o_tokens['total_tokens'], 50 * 3500)

        # Verify aggregates (lines 228-236)
        self.assertGreater(result['total_tokens'], 0)
        self.assertEqual(result['input_tokens'] + result['output_tokens'], result['total_tokens'])
        self.assertGreater(result['average_tokens_per_request'], 0)

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    def test_calculate_cost_metrics_complete(self, mock_get_env):
        """Test _calculate_cost_metrics with all models and calculations (lines 241-276)."""
        mock_get_env.return_value = "test-project"

        tool = LLMObservabilityMetrics(time_window_hours=24)

        usage_metrics = {
            'total_requests': 120,
            'requests_by_model': {
                'gpt-4o': 40,
                'gpt-4.1': 30,
                'gpt-3.5-turbo': 30,
                'claude-3': 15,
                'unknown-model': 5
            }
        }

        result = tool._calculate_cost_metrics(usage_metrics)

        # Verify costs by model (lines 254-270)
        self.assertEqual(len(result['costs_by_model']), 5)
        self.assertIn('gpt-4o', result['costs_by_model'])
        self.assertIn('gpt-4.1', result['costs_by_model'])
        self.assertIn('gpt-3.5-turbo', result['costs_by_model'])
        self.assertIn('claude-3', result['costs_by_model'])
        self.assertIn('unknown-model', result['costs_by_model'])

        # Verify cost structure for each model (lines 266-270)
        for model, costs in result['costs_by_model'].items():
            self.assertIn('input_cost', costs)
            self.assertIn('output_cost', costs)
            self.assertIn('total_cost', costs)
            self.assertGreater(costs['total_cost'], 0)

        # Verify aggregates and efficiency (lines 273-281)
        self.assertGreater(result['total_cost'], 0)
        self.assertGreater(result['cost_per_request'], 0)
        self.assertGreater(result['estimated_monthly_cost'], 0)
        self.assertIn(result['cost_efficiency_score'], [0, 50, 80, 100])

    @patch('observability_agent.tools.llm_observability_metrics.get_required_env_var')
    @patch('observability_agent.tools.llm_observability_metrics.get_optional_env_var')
    def test_emit_to_langfuse_exception(self, mock_get_optional, mock_get_required):
        """Test _emit_to_langfuse exception handling (lines 478-479)."""
        mock_get_required.return_value = "test-project"
        mock_get_optional.side_effect = Exception("Environment error")

        tool = LLMObservabilityMetrics(time_window_hours=24)

        result = tool._emit_to_langfuse({'test': 'metrics'})

        # Should return failure status (lines 478-482)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('error', result)


if __name__ == '__main__':
    unittest.main()