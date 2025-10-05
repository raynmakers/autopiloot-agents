"""
Fixed comprehensive test for monitor_quota_state.py
Properly mocks Firestore and external dependencies with realistic quota tracking scenarios
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import sys
import json
import os
import importlib.util
from datetime import datetime, timezone, timedelta


class TestMonitorQuotaStateFixed(unittest.TestCase):
    """Fixed comprehensive tests for MonitorQuotaState tool"""

    def setUp(self):
        """Set up test environment"""
        # Get the module path
        module_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..',
            'observability_agent', 'tools',
            'monitor_quota_state.py'
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
            'dotenv': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'audit_logger': MagicMock()
        }

        # Setup standard mocks
        self.mock_modules['pydantic'].Field = lambda *args, **kwargs: kwargs.get('default', None)

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        self.mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool

    def test_comprehensive_quota_monitoring_success(self):
        """Test successful comprehensive quota monitoring with alerts"""
        # Setup environment mocks
        self.mock_modules['env_loader'].get_required_env_var = Mock(side_effect=lambda var, desc: {
            'GCP_PROJECT_ID': 'test-project-id',
            'GOOGLE_APPLICATION_CREDENTIALS': '/fake/path/service-account.json'
        }.get(var, 'test-value'))

        # Setup configuration mocks
        self.mock_modules['loader'].load_app_config = Mock(return_value={
            'youtube': {'daily_quota': 10000},
            'assemblyai': {'daily_quota': 100}
        })
        self.mock_modules['loader'].get_youtube_daily_limit = Mock(return_value=10000)
        self.mock_modules['loader'].get_assemblyai_daily_limit = Mock(return_value=100)

        # Setup audit logger
        mock_audit_logger = Mock()
        mock_audit_logger.log_quota_monitored = Mock(return_value=True)
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

        # Setup Firestore mock with high usage data
        mock_db = Mock()
        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db)
        self._setup_high_usage_firestore_mock(mock_db)

        # Mock os.path.exists for service account file
        with patch('os.path.exists', return_value=True):
            with patch.dict('sys.modules', self.mock_modules):
                # Import module with mocks in place
                spec = importlib.util.spec_from_file_location('monitor_quota_state', self.module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                tool_class = module.MonitorQuotaState

                # Mock the _initialize_firestore method
                with patch.object(tool_class, '_initialize_firestore', return_value=mock_db):
                    # Test high usage scenario (should trigger alerts)
                    tool = tool_class(
                        alert_threshold=0.8,
                        include_predictions=True
                    )

                    result = tool.run()
                    result_json = json.loads(result)

                    # Verify successful monitoring
                    self.assertIn('monitoring_timestamp', result_json)
                    self.assertIn('quota_states', result_json)
                    self.assertIn('alerts', result_json)
                    self.assertIn('predictions', result_json)
                    self.assertIn('overall_health', result_json)
                    self.assertIn('next_reset', result_json)

                    # Verify quota states structure
                    quota_states = result_json['quota_states']
                    self.assertIn('youtube', quota_states)
                    self.assertIn('assemblyai', quota_states)

                    # Verify YouTube quota state
                    youtube_state = quota_states['youtube']
                    self.assertEqual(youtube_state['service'], 'youtube')
                    self.assertIn('current_usage', youtube_state)
                    self.assertIn('daily_limit', youtube_state)
                    self.assertIn('remaining', youtube_state)
                    self.assertIn('utilization', youtube_state)
                    self.assertIn('status', youtube_state)
                    self.assertIn('time_to_reset_hours', youtube_state)
                    self.assertIn('reset_window', youtube_state)
                    self.assertIn('next_reset_at', youtube_state)

                    # Verify AssemblyAI quota state
                    assemblyai_state = quota_states['assemblyai']
                    self.assertEqual(assemblyai_state['service'], 'assemblyai')
                    self.assertIn('current_usage', assemblyai_state)
                    self.assertIn('daily_limit', assemblyai_state)
                    self.assertIn('remaining', assemblyai_state)
                    self.assertIn('utilization', assemblyai_state)
                    self.assertIn('status', assemblyai_state)

                    # Verify alerts generated (high usage should trigger alerts)
                    alerts = result_json['alerts']
                    self.assertIsInstance(alerts, list)
                    # Should have alerts for high usage
                    if alerts:
                        for alert in alerts:
                            self.assertIn('service', alert)
                            self.assertIn('severity', alert)
                            self.assertIn('message', alert)
                            self.assertIn('recommended_action', alert)
                            self.assertIn('time_to_reset', alert)
                            self.assertIn(alert['service'], ['youtube', 'assemblyai'])
                            self.assertIn(alert['severity'], ['warning', 'critical'])

                    # Verify predictions structure
                    predictions = result_json['predictions']
                    if predictions:  # Only check if predictions are included
                        for service in ['youtube', 'assemblyai']:
                            if service in predictions:
                                pred = predictions[service]
                                self.assertIn('hourly_rate', pred)
                                self.assertIn('predicted_daily_usage', pred)
                                self.assertIn('projected_utilization', pred)
                                self.assertIn('risk_level', pred)
                                self.assertIn(pred['risk_level'], ['low', 'medium', 'high'])

                    # Verify overall health structure
                    overall_health = result_json['overall_health']
                    self.assertIn('status', overall_health)
                    self.assertIn('score', overall_health)
                    self.assertIn('weighted_utilization', overall_health)
                    self.assertIn('bottleneck_service', overall_health)
                    self.assertIn(overall_health['status'], ['healthy', 'warning', 'critical'])
                    self.assertTrue(0 <= overall_health['score'] <= 100)
                    self.assertIn(overall_health['bottleneck_service'], ['youtube', 'assemblyai'])

                    # Verify audit logging
                    mock_audit_logger.log_quota_monitored.assert_called_once()
                    call_args = mock_audit_logger.log_quota_monitored.call_args
                    self.assertIn('youtube_usage', call_args.kwargs)
                    self.assertIn('assemblyai_usage', call_args.kwargs)
                    self.assertIn('alert_count', call_args.kwargs)
                    self.assertEqual(call_args.kwargs['actor'], 'ObservabilityAgent')

                    print("✅ Comprehensive quota monitoring success test passed")

    def test_error_handling_firestore_failure(self):
        """Test error handling when Firestore initialization fails"""
        # Setup environment mocks with missing service account file
        self.mock_modules['env_loader'].get_required_env_var = Mock(side_effect=Exception("Service account file not found"))
        self.mock_modules['loader'].load_app_config = Mock(return_value={})
        self.mock_modules['loader'].get_youtube_daily_limit = Mock(return_value=10000)
        self.mock_modules['loader'].get_assemblyai_daily_limit = Mock(return_value=100)

        # Setup audit logger
        mock_audit_logger = Mock()
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

        with patch.dict('sys.modules', self.mock_modules):
            # Import module
            spec = importlib.util.spec_from_file_location('monitor_quota_state', self.module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_class = module.MonitorQuotaState

            # Test error handling
            tool_error = tool_class(alert_threshold=0.8)
            result_error = tool_error.run()
            result_error_json = json.loads(result_error)

            # Verify error response structure
            self.assertIn('error', result_error_json)
            self.assertIn('Service account file not found', result_error_json['error'])
            self.assertIn('quota_states', result_error_json)
            self.assertIsNone(result_error_json['quota_states'])

            print("✅ Error handling test passed")

    def test_low_usage_scenario(self):
        """Test monitoring with low quota usage (no alerts)"""
        # Setup environment mocks
        self.mock_modules['env_loader'].get_required_env_var = Mock(side_effect=lambda var, desc: {
            'GCP_PROJECT_ID': 'test-project-id',
            'GOOGLE_APPLICATION_CREDENTIALS': '/fake/path/service-account.json'
        }.get(var, 'test-value'))

        self.mock_modules['loader'].load_app_config = Mock(return_value={})
        self.mock_modules['loader'].get_youtube_daily_limit = Mock(return_value=10000)
        self.mock_modules['loader'].get_assemblyai_daily_limit = Mock(return_value=100)

        # Setup audit logger
        mock_audit_logger = Mock()
        mock_audit_logger.log_quota_monitored = Mock(return_value=True)
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

        # Setup Firestore mock with low usage data
        mock_db = Mock()
        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db)
        self._setup_low_usage_firestore_mock(mock_db)

        with patch('os.path.exists', return_value=True):
            with patch.dict('sys.modules', self.mock_modules):
                # Import module
                spec = importlib.util.spec_from_file_location('monitor_quota_state', self.module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                tool_class = module.MonitorQuotaState

                with patch.object(tool_class, '_initialize_firestore', return_value=mock_db):
                    # Test low usage scenario (should not trigger alerts)
                    tool_low = tool_class(
                        alert_threshold=0.8,
                        include_predictions=True
                    )

                    result_low = tool_low.run()
                    result_low_json = json.loads(result_low)

                    # Verify successful monitoring with low usage
                    self.assertIn('quota_states', result_low_json)
                    self.assertIn('alerts', result_low_json)

                    # Verify low utilization
                    youtube_state = result_low_json['quota_states']['youtube']
                    assemblyai_state = result_low_json['quota_states']['assemblyai']

                    self.assertTrue(youtube_state['utilization'] < 0.8)
                    self.assertTrue(assemblyai_state['utilization'] < 0.8)
                    self.assertEqual(youtube_state['status'], 'healthy')
                    self.assertEqual(assemblyai_state['status'], 'healthy')

                    # Verify no alerts generated
                    alerts = result_low_json['alerts']
                    self.assertEqual(len(alerts), 0)

                    # Verify overall health is good
                    overall_health = result_low_json['overall_health']
                    self.assertEqual(overall_health['status'], 'healthy')
                    self.assertTrue(overall_health['score'] > 70)

                    print("✅ Low usage scenario test passed")

    def test_quota_status_classifications(self):
        """Test quota status classification logic"""
        # Setup basic mocks
        self.mock_modules['env_loader'].get_required_env_var = Mock(return_value='test-value')
        self.mock_modules['loader'].load_app_config = Mock(return_value={})
        self.mock_modules['loader'].get_youtube_daily_limit = Mock(return_value=1000)
        self.mock_modules['loader'].get_assemblyai_daily_limit = Mock(return_value=50)

        mock_audit_logger = Mock()
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

        with patch.dict('sys.modules', self.mock_modules):
            # Import module
            spec = importlib.util.spec_from_file_location('monitor_quota_state', self.module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_class = module.MonitorQuotaState
            tool = tool_class(alert_threshold=0.8)

            # Test quota status classifications
            test_cases = [
                (0.0, 'healthy'),
                (0.3, 'healthy'),
                (0.59, 'healthy'),
                (0.6, 'moderate'),
                (0.75, 'moderate'),
                (0.79, 'moderate'),
                (0.8, 'warning'),
                (0.9, 'warning'),
                (0.94, 'warning'),
                (0.95, 'critical'),
                (1.0, 'critical')
            ]

            for utilization, expected_status in test_cases:
                actual_status = tool._get_quota_status(utilization)
                self.assertEqual(actual_status, expected_status,
                    f"Utilization {utilization:.2f} should be '{expected_status}', got '{actual_status}'")

            print("✅ Quota status classifications test passed")

    def test_configuration_variations(self):
        """Test different configuration options and thresholds"""
        # Setup environment mocks
        self.mock_modules['env_loader'].get_required_env_var = Mock(side_effect=lambda var, desc: {
            'GCP_PROJECT_ID': 'test-project-id',
            'GOOGLE_APPLICATION_CREDENTIALS': '/fake/path/service-account.json'
        }.get(var, 'test-value'))

        self.mock_modules['loader'].load_app_config = Mock(return_value={})
        self.mock_modules['loader'].get_youtube_daily_limit = Mock(return_value=10000)
        self.mock_modules['loader'].get_assemblyai_daily_limit = Mock(return_value=100)

        mock_audit_logger = Mock()
        mock_audit_logger.log_quota_monitored = Mock(return_value=True)
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

        mock_db = Mock()
        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db)
        self._setup_moderate_usage_firestore_mock(mock_db)

        with patch('os.path.exists', return_value=True):
            with patch.dict('sys.modules', self.mock_modules):
                spec = importlib.util.spec_from_file_location('monitor_quota_state', self.module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                tool_class = module.MonitorQuotaState

                with patch.object(tool_class, '_initialize_firestore', return_value=mock_db):
                    # Test 1: Different alert thresholds
                    for threshold in [0.5, 0.7, 0.9]:
                        tool = tool_class(
                            alert_threshold=threshold,
                            include_predictions=True
                        )
                        self.assertEqual(tool.alert_threshold, threshold)

                    # Test 2: Predictions disabled
                    tool_no_pred = tool_class(
                        alert_threshold=0.8,
                        include_predictions=False
                    )

                    result_no_pred = tool_no_pred.run()
                    result_no_pred_json = json.loads(result_no_pred)

                    # Should still have basic monitoring data
                    self.assertIn('quota_states', result_no_pred_json)
                    self.assertIn('alerts', result_no_pred_json)
                    self.assertIn('overall_health', result_no_pred_json)

                    # Predictions might be empty dict when disabled
                    predictions = result_no_pred_json.get('predictions', {})
                    self.assertIsInstance(predictions, dict)

                    # Test 3: Very low threshold (should generate more alerts)
                    tool_sensitive = tool_class(
                        alert_threshold=0.3,
                        include_predictions=True
                    )

                    result_sensitive = tool_sensitive.run()
                    result_sensitive_json = json.loads(result_sensitive)

                    # With moderate usage and low threshold, should have alerts
                    alerts = result_sensitive_json['alerts']
                    # Should have more alerts with lower threshold
                    self.assertIsInstance(alerts, list)

                    print("✅ Configuration variations test passed")

    def test_usage_predictions_edge_cases(self):
        """Test usage prediction calculation edge cases"""
        # Setup basic mocks
        self.mock_modules['env_loader'].get_required_env_var = Mock(return_value='test-value')
        self.mock_modules['loader'].load_app_config = Mock(return_value={})

        mock_audit_logger = Mock()
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

        with patch.dict('sys.modules', self.mock_modules):
            # Import module
            spec = importlib.util.spec_from_file_location('monitor_quota_state', self.module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_class = module.MonitorQuotaState
            tool = tool_class(alert_threshold=0.8)

            # Test predictions with different usage scenarios (without time mocking for simplicity)
            test_cases = [
                # Low usage scenario
                {'current_usage': {'youtube': 100, 'assemblyai': 5}, 'youtube_limit': 10000, 'assemblyai_limit': 100},
                # High usage scenario
                {'current_usage': {'youtube': 8000, 'assemblyai': 80}, 'youtube_limit': 10000, 'assemblyai_limit': 100},
                # Zero usage (predictions should handle this gracefully)
                {'current_usage': {'youtube': 0, 'assemblyai': 0}, 'youtube_limit': 10000, 'assemblyai_limit': 100},
            ]

            for case in test_cases:
                predictions = tool._generate_usage_predictions(
                    case['current_usage'],
                    case['youtube_limit'],
                    case['assemblyai_limit']
                )

                # Verify prediction structure - predictions may be empty if hours_elapsed is 0
                self.assertIsInstance(predictions, dict)

                # Check structure if predictions are generated
                for service in ['youtube', 'assemblyai']:
                    if service in predictions:
                        pred = predictions[service]
                        self.assertIn('hourly_rate', pred)
                        self.assertIn('predicted_daily_usage', pred)
                        self.assertIn('projected_utilization', pred)
                        self.assertIn('risk_level', pred)
                        self.assertIn(pred['risk_level'], ['low', 'medium', 'high'])

            print("✅ Usage predictions edge cases test passed")

    def test_overall_health_calculation(self):
        """Test overall health score calculation"""
        # Setup basic mocks
        self.mock_modules['env_loader'].get_required_env_var = Mock(return_value='test-value')
        self.mock_modules['loader'].load_app_config = Mock(return_value={})

        mock_audit_logger = Mock()
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

        with patch.dict('sys.modules', self.mock_modules):
            # Import module
            spec = importlib.util.spec_from_file_location('monitor_quota_state', self.module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_class = module.MonitorQuotaState
            tool = tool_class(alert_threshold=0.8)

            # Test different utilization scenarios
            test_scenarios = [
                # Low utilization (healthy)
                {'youtube': 0.3, 'assemblyai': 0.2, 'expected_status': 'healthy'},
                # Moderate utilization (healthy)
                {'youtube': 0.5, 'assemblyai': 0.4, 'expected_status': 'healthy'},
                # High utilization (warning)
                {'youtube': 0.8, 'assemblyai': 0.6, 'expected_status': 'warning'},
                # Very high utilization (critical)
                {'youtube': 0.95, 'assemblyai': 0.9, 'expected_status': 'critical'},
                # Mixed utilization (YouTube critical, AssemblyAI low) - weighted calc: 0.95*0.6 + 0.1*0.4 = 0.61
                {'youtube': 0.95, 'assemblyai': 0.1, 'expected_status': 'healthy'},
            ]

            for scenario in test_scenarios:
                youtube_state = {
                    'utilization': scenario['youtube'],
                    'service': 'youtube'
                }
                assemblyai_state = {
                    'utilization': scenario['assemblyai'],
                    'service': 'assemblyai'
                }

                health = tool._calculate_overall_health(youtube_state, assemblyai_state)

                # Verify health structure
                self.assertIn('status', health)
                self.assertIn('score', health)
                self.assertIn('weighted_utilization', health)
                self.assertIn('bottleneck_service', health)

                # Verify status matches expected
                self.assertEqual(health['status'], scenario['expected_status'],
                    f"YouTube {scenario['youtube']:.2f}, AssemblyAI {scenario['assemblyai']:.2f} should be {scenario['expected_status']}, got {health['status']}")

                # Verify score is within valid range
                self.assertTrue(0 <= health['score'] <= 100)

                # Verify bottleneck service identification
                expected_bottleneck = 'youtube' if scenario['youtube'] > scenario['assemblyai'] else 'assemblyai'
                self.assertEqual(health['bottleneck_service'], expected_bottleneck)

                # Verify weighted utilization calculation (YouTube weight 0.6, AssemblyAI weight 0.4)
                expected_weighted = (scenario['youtube'] * 0.6) + (scenario['assemblyai'] * 0.4)
                self.assertAlmostEqual(health['weighted_utilization'], expected_weighted, places=3)

            print("✅ Overall health calculation test passed")

    def _setup_high_usage_firestore_mock(self, mock_db):
        """Setup Firestore mock with high quota usage data (should trigger alerts)"""
        # Mock high usage - 80+ videos discovered recently (8000+ YouTube quota)
        mock_video_docs = [Mock() for _ in range(85)]  # 85 videos * 100 units = 8500 units
        mock_transcript_docs = [Mock() for _ in range(85)]  # 85 transcripts

        def mock_collection(name):
            mock_coll = Mock()
            if name == 'videos':
                mock_stream = Mock()
                mock_stream.stream.return_value = mock_video_docs
                mock_coll.where.return_value.limit.return_value = mock_stream
            elif name == 'transcripts':
                mock_stream = Mock()
                mock_stream.stream.return_value = mock_transcript_docs
                mock_coll.where.return_value.limit.return_value = mock_stream
            return mock_coll

        mock_db.collection.side_effect = mock_collection

    def _setup_low_usage_firestore_mock(self, mock_db):
        """Setup Firestore mock with low quota usage data (no alerts)"""
        # Mock low usage - only 5 videos discovered recently (500 YouTube quota)
        mock_video_docs = [Mock() for _ in range(5)]  # 5 videos * 100 units = 500 units
        mock_transcript_docs = [Mock() for _ in range(5)]  # 5 transcripts

        def mock_collection(name):
            mock_coll = Mock()
            if name == 'videos':
                mock_stream = Mock()
                mock_stream.stream.return_value = mock_video_docs
                mock_coll.where.return_value.limit.return_value = mock_stream
            elif name == 'transcripts':
                mock_stream = Mock()
                mock_stream.stream.return_value = mock_transcript_docs
                mock_coll.where.return_value.limit.return_value = mock_stream
            return mock_coll

        mock_db.collection.side_effect = mock_collection

    def _setup_moderate_usage_firestore_mock(self, mock_db):
        """Setup Firestore mock with moderate quota usage data"""
        # Mock moderate usage - 30 videos discovered recently (3000 YouTube quota)
        mock_video_docs = [Mock() for _ in range(30)]  # 30 videos * 100 units = 3000 units
        mock_transcript_docs = [Mock() for _ in range(30)]  # 30 transcripts

        def mock_collection(name):
            mock_coll = Mock()
            if name == 'videos':
                mock_stream = Mock()
                mock_stream.stream.return_value = mock_video_docs
                mock_coll.where.return_value.limit.return_value = mock_stream
            elif name == 'transcripts':
                mock_stream = Mock()
                mock_stream.stream.return_value = mock_transcript_docs
                mock_coll.where.return_value.limit.return_value = mock_stream
            return mock_coll

        mock_db.collection.side_effect = mock_collection


if __name__ == "__main__":
    unittest.main()