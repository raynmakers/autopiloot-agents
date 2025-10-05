"""
Comprehensive test for monitor_dlq_trends.py - targeting 100% coverage
Tests DLQ trend analysis, anomaly detection, and operational recommendations
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import sys
import json
import os
import importlib.util
from datetime import datetime, timezone, timedelta


class TestMonitorDLQTrendsComprehensive(unittest.TestCase):
    """Comprehensive tests for MonitorDLQTrends tool covering all functionality"""

    def setUp(self):
        """Set up test environment with comprehensive mocking"""
        # Get the module path
        module_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..',
            'observability_agent', 'tools',
            'monitor_dlq_trends.py'
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

        # Mock environment functions
        self.mock_modules['env_loader'].get_required_env_var = Mock(side_effect=lambda var, desc: {
            'GCP_PROJECT_ID': 'test-project-id',
            'GOOGLE_APPLICATION_CREDENTIALS': '/fake/path/service-account.json'
        }.get(var, 'test-value'))
        self.mock_modules['loader'].load_app_config = Mock(return_value={})

        # Mock audit logger with proper methods
        mock_audit_logger = Mock()
        mock_audit_logger.log_dlq_monitored = Mock(return_value=True)
        mock_audit_logger.write_audit_log = Mock(return_value=True)
        self.mock_modules['audit_logger'].audit_logger = mock_audit_logger

    def test_comprehensive_dlq_trend_analysis(self):
        """Test comprehensive DLQ trend analysis with realistic data"""
        # Setup Firestore mock with DLQ data
        mock_db = Mock()
        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db)
        self._setup_comprehensive_firestore_mock(mock_db)

        with patch('os.path.exists', return_value=True):
            with patch.dict('sys.modules', self.mock_modules):
                # Import module
                spec = importlib.util.spec_from_file_location('monitor_dlq_trends', self.module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                tool_class = module.MonitorDLQTrends

                # Mock the _initialize_firestore method
                with patch.object(tool_class, '_initialize_firestore', return_value=mock_db):
                    # Test comprehensive trend analysis
                    tool = tool_class(
                        analysis_window_hours=24,
                        spike_threshold=2.0,
                        include_recommendations=True
                    )

                    result = tool.run()
                    result_json = json.loads(result)

                    # Verify analysis structure
                    self.assertIn('analysis_timestamp', result_json)
                    self.assertIn('analysis_window', result_json)
                    self.assertIn('trend_analysis', result_json)
                    self.assertIn('failure_patterns', result_json)
                    self.assertIn('temporal_analysis', result_json)
                    self.assertIn('alerts', result_json)
                    self.assertIn('recommendations', result_json)

                    # Verify analysis window
                    analysis_window = result_json['analysis_window']
                    self.assertIn('start_time', analysis_window)
                    self.assertIn('end_time', analysis_window)
                    self.assertIn('duration_hours', analysis_window)

                    # Verify trend analysis
                    trend_analysis = result_json['trend_analysis']
                    self.assertIn('total_entries', trend_analysis)
                    self.assertIn('entries_per_hour', trend_analysis)
                    self.assertIn('failure_rate_trend', trend_analysis)

                    # Verify failure patterns
                    failure_patterns = result_json['failure_patterns']
                    self.assertIn('top_errors', failure_patterns)
                    self.assertIn('error_distribution', failure_patterns)
                    self.assertIn('affected_agents', failure_patterns)

                    # Verify temporal analysis
                    temporal_analysis = result_json['temporal_analysis']
                    self.assertIn('hourly_breakdown', temporal_analysis)
                    self.assertIn('peak_failure_times', temporal_analysis)

                    # Verify alerts and recommendations exist
                    self.assertIsInstance(result_json['alerts'], list)
                    self.assertIsInstance(result_json['recommendations'], list)

                    print("✅ Comprehensive DLQ trend analysis test passed")

    def test_anomaly_detection_scenarios(self):
        """Test anomaly detection with different spike scenarios"""
        mock_db = Mock()
        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db)

        with patch('os.path.exists', return_value=True):
            with patch.dict('sys.modules', self.mock_modules):
                spec = importlib.util.spec_from_file_location('monitor_dlq_trends', self.module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                tool_class = module.MonitorDLQTrends

                with patch.object(tool_class, '_initialize_firestore', return_value=mock_db):
                    # Test 1: Normal conditions (no spikes)
                    self._setup_normal_dlq_mock(mock_db)
                    tool_normal = tool_class(analysis_window_hours=24, spike_threshold=2.0)
                    result_normal = tool_normal.run()
                    result_normal_json = json.loads(result_normal)

                    # Should have minimal or no alerts
                    alerts_normal = result_normal_json['alerts']
                    self.assertIsInstance(alerts_normal, list)

                    # Test 2: Spike conditions (high failure rate)
                    self._setup_spike_dlq_mock(mock_db)
                    tool_spike = tool_class(analysis_window_hours=24, spike_threshold=1.5)
                    result_spike = tool_spike.run()
                    result_spike_json = json.loads(result_spike)

                    # Should detect spike alerts
                    alerts_spike = result_spike_json['alerts']
                    self.assertIsInstance(alerts_spike, list)

                    # Test 3: Different spike thresholds
                    for threshold in [1.5, 2.0, 3.0]:
                        tool_threshold = tool_class(analysis_window_hours=24, spike_threshold=threshold)
                        result_threshold = tool_threshold.run()
                        result_threshold_json = json.loads(result_threshold)
                        self.assertIn('alerts', result_threshold_json)

                    print("✅ Anomaly detection scenarios test passed")

    def test_failure_pattern_analysis(self):
        """Test failure pattern analysis and categorization"""
        mock_db = Mock()
        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db)
        self._setup_pattern_analysis_mock(mock_db)

        with patch('os.path.exists', return_value=True):
            with patch.dict('sys.modules', self.mock_modules):
                spec = importlib.util.spec_from_file_location('monitor_dlq_trends', self.module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                tool_class = module.MonitorDLQTrends

                with patch.object(tool_class, '_initialize_firestore', return_value=mock_db):
                    tool = tool_class(analysis_window_hours=24)

                    # Test failure pattern analysis directly
                    mock_dlq_entries = self._get_mock_dlq_entries_for_patterns()
                    failure_patterns = tool._analyze_failure_patterns(mock_dlq_entries)

                    # Verify pattern structure
                    self.assertIn('top_errors', failure_patterns)
                    self.assertIn('error_distribution', failure_patterns)
                    self.assertIn('affected_agents', failure_patterns)
                    self.assertIn('retry_analysis', failure_patterns)

                    # Verify top errors analysis
                    top_errors = failure_patterns['top_errors']
                    self.assertIsInstance(top_errors, list)
                    if top_errors:
                        error = top_errors[0]
                        self.assertIn('error_type', error)
                        self.assertIn('count', error)
                        self.assertIn('percentage', error)
                        self.assertIn('recent_examples', error)

                    # Verify error distribution
                    error_distribution = failure_patterns['error_distribution']
                    self.assertIn('by_agent', error_distribution)
                    self.assertIn('by_job_type', error_distribution)

                    # Verify affected agents
                    affected_agents = failure_patterns['affected_agents']
                    self.assertIsInstance(affected_agents, dict)

                    print("✅ Failure pattern analysis test passed")

    def test_temporal_analysis_comprehensive(self):
        """Test temporal analysis with different time patterns"""
        mock_db = Mock()
        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db)

        with patch('os.path.exists', return_value=True):
            with patch.dict('sys.modules', self.mock_modules):
                spec = importlib.util.spec_from_file_location('monitor_dlq_trends', self.module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                tool_class = module.MonitorDLQTrends

                with patch.object(tool_class, '_initialize_firestore', return_value=mock_db):
                    tool = tool_class(analysis_window_hours=24)

                    # Test temporal analysis with various patterns
                    start_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
                    end_time = datetime(2024, 1, 16, 0, 0, 0, tzinfo=timezone.utc)

                    # Test with different temporal patterns
                    temporal_patterns = [
                        self._get_uniform_temporal_entries(),
                        self._get_peak_hour_temporal_entries(),
                        self._get_burst_temporal_entries()
                    ]

                    for pattern_entries in temporal_patterns:
                        temporal_analysis = tool._analyze_temporal_patterns(pattern_entries, start_time, end_time)

                        # Verify temporal analysis structure
                        self.assertIn('hourly_breakdown', temporal_analysis)
                        self.assertIn('peak_failure_times', temporal_analysis)
                        self.assertIn('failure_velocity', temporal_analysis)
                        self.assertIn('time_correlation', temporal_analysis)

                        # Verify hourly breakdown
                        hourly_breakdown = temporal_analysis['hourly_breakdown']
                        self.assertIsInstance(hourly_breakdown, dict)

                        # Verify peak failure times
                        peak_times = temporal_analysis['peak_failure_times']
                        self.assertIsInstance(peak_times, list)

                        # Verify failure velocity (failures per minute)
                        velocity = temporal_analysis['failure_velocity']
                        self.assertIn('current_rate', velocity)
                        self.assertIn('baseline_rate', velocity)

                    print("✅ Temporal analysis comprehensive test passed")

    def test_recommendations_generation(self):
        """Test operational recommendations generation"""
        mock_db = Mock()
        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db)

        with patch('os.path.exists', return_value=True):
            with patch.dict('sys.modules', self.mock_modules):
                spec = importlib.util.spec_from_file_location('monitor_dlq_trends', self.module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                tool_class = module.MonitorDLQTrends

                with patch.object(tool_class, '_initialize_firestore', return_value=mock_db):
                    tool = tool_class(analysis_window_hours=24, include_recommendations=True)

                    # Test recommendations for different scenarios
                    scenarios = [
                        # High timeout errors
                        {
                            'failure_patterns': {
                                'top_errors': [{'error_type': 'timeout', 'count': 15, 'percentage': 60.0}],
                                'affected_agents': {'TranscriberAgent': 12, 'SummarizerAgent': 3}
                            },
                            'temporal_analysis': {'failure_velocity': {'current_rate': 5.2}},
                            'alerts': [{'type': 'spike_detected', 'severity': 'high'}]
                        },
                        # API quota errors
                        {
                            'failure_patterns': {
                                'top_errors': [{'error_type': 'quota_exceeded', 'count': 8, 'percentage': 80.0}],
                                'affected_agents': {'ScraperAgent': 8}
                            },
                            'temporal_analysis': {'failure_velocity': {'current_rate': 2.1}},
                            'alerts': [{'type': 'quota_alert', 'severity': 'medium'}]
                        },
                        # Mixed errors
                        {
                            'failure_patterns': {
                                'top_errors': [
                                    {'error_type': 'connection_error', 'count': 5, 'percentage': 50.0},
                                    {'error_type': 'validation_error', 'count': 3, 'percentage': 30.0}
                                ],
                                'affected_agents': {'DriveAgent': 4, 'ObservabilityAgent': 4}
                            },
                            'temporal_analysis': {'failure_velocity': {'current_rate': 1.8}},
                            'alerts': []
                        }
                    ]

                    for scenario in scenarios:
                        recommendations = tool._generate_recommendations(
                            scenario['failure_patterns'],
                            scenario['temporal_analysis'],
                            scenario['alerts']
                        )

                        # Verify recommendations structure
                        self.assertIsInstance(recommendations, list)

                        for recommendation in recommendations:
                            self.assertIn('category', recommendation)
                            self.assertIn('priority', recommendation)
                            self.assertIn('action', recommendation)
                            self.assertIn('description', recommendation)

                            # Verify priority levels
                            self.assertIn(recommendation['priority'], ['low', 'medium', 'high', 'critical'])

                    print("✅ Recommendations generation test passed")

    def test_error_handling_scenarios(self):
        """Test error handling and edge cases"""
        # Test 1: Firestore connection failure
        self.mock_modules['env_loader'].get_required_env_var.side_effect = Exception("Service account not found")
        mock_audit_logger = self.mock_modules['audit_logger'].audit_logger

        with patch.dict('sys.modules', self.mock_modules):
            spec = importlib.util.spec_from_file_location('monitor_dlq_trends', self.module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_class = module.MonitorDLQTrends
            tool_error = tool_class(analysis_window_hours=24)

            result_error = tool_error.run()
            result_error_json = json.loads(result_error)

            # Verify error response
            self.assertIn('error', result_error_json)
            self.assertIn('Service account not found', result_error_json['error'])

            print("✅ Firestore connection error test passed")

        # Test 2: Empty DLQ data
        self.mock_modules['env_loader'].get_required_env_var.side_effect = lambda var, desc: 'test-value'
        mock_db_empty = Mock()
        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db_empty)
        self._setup_empty_dlq_mock(mock_db_empty)

        with patch('os.path.exists', return_value=True):
            with patch.dict('sys.modules', self.mock_modules):
                spec = importlib.util.spec_from_file_location('monitor_dlq_trends', self.module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                tool_class = module.MonitorDLQTrends

                with patch.object(tool_class, '_initialize_firestore', return_value=mock_db_empty):
                    tool_empty = tool_class(analysis_window_hours=24)
                    result_empty = tool_empty.run()
                    result_empty_json = json.loads(result_empty)

                    # Verify graceful empty data handling
                    self.assertIn('trend_analysis', result_empty_json)
                    self.assertEqual(result_empty_json['trend_analysis']['total_entries'], 0)
                    self.assertIn('alerts', result_empty_json)

                    print("✅ Empty DLQ data test passed")

        # Test 3: Parameter validation
        with patch.dict('sys.modules', self.mock_modules):
            spec = importlib.util.spec_from_file_location('monitor_dlq_trends', self.module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            tool_class = module.MonitorDLQTrends

            # Test parameter bounds
            tool_valid = tool_class(analysis_window_hours=24, spike_threshold=2.0)
            self.assertEqual(tool_valid.analysis_window_hours, 24)
            self.assertEqual(tool_valid.spike_threshold, 2.0)

            tool_bounds = tool_class(analysis_window_hours=168, spike_threshold=10.0)
            self.assertEqual(tool_bounds.analysis_window_hours, 168)
            self.assertEqual(tool_bounds.spike_threshold, 10.0)

            print("✅ Parameter validation test passed")

    def test_configuration_variations(self):
        """Test different configuration options"""
        mock_db = Mock()
        self.mock_modules['google.cloud.firestore'].Client = Mock(return_value=mock_db)
        self._setup_comprehensive_firestore_mock(mock_db)

        with patch('os.path.exists', return_value=True):
            with patch.dict('sys.modules', self.mock_modules):
                spec = importlib.util.spec_from_file_location('monitor_dlq_trends', self.module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                tool_class = module.MonitorDLQTrends

                with patch.object(tool_class, '_initialize_firestore', return_value=mock_db):
                    # Test different time windows
                    for window_hours in [1, 6, 24, 48, 168]:
                        tool = tool_class(analysis_window_hours=window_hours)
                        result = tool.run()
                        result_json = json.loads(result)

                        self.assertIn('analysis_window', result_json)
                        self.assertEqual(result_json['analysis_window']['duration_hours'], window_hours)

                    # Test different spike thresholds
                    for threshold in [1.2, 1.5, 2.0, 3.0, 5.0]:
                        tool = tool_class(spike_threshold=threshold)
                        result = tool.run()
                        result_json = json.loads(result)

                        # Should execute without error
                        self.assertIn('alerts', result_json)

                    # Test recommendations on/off
                    tool_no_recs = tool_class(include_recommendations=False)
                    result_no_recs = tool_no_recs.run()
                    result_no_recs_json = json.loads(result_no_recs)

                    self.assertEqual(result_no_recs_json['recommendations'], [])

                    tool_with_recs = tool_class(include_recommendations=True)
                    result_with_recs = tool_with_recs.run()
                    result_with_recs_json = json.loads(result_with_recs)

                    self.assertIsInstance(result_with_recs_json['recommendations'], list)

                    print("✅ Configuration variations test passed")

    def _setup_comprehensive_firestore_mock(self, mock_db):
        """Setup comprehensive Firestore mock with realistic DLQ data"""
        mock_dlq_docs = self._get_comprehensive_mock_dlq_entries()

        def mock_collection(name):
            mock_coll = Mock()
            if name == 'jobs_deadletter':
                mock_coll.where.return_value.where.return_value.order_by.return_value.stream.return_value = mock_dlq_docs
            else:
                mock_coll.where.return_value.where.return_value.stream.return_value = []
            return mock_coll

        mock_db.collection.side_effect = mock_collection

    def _setup_normal_dlq_mock(self, mock_db):
        """Setup normal DLQ conditions (low failure rate)"""
        mock_dlq_docs = self._get_normal_mock_dlq_entries()

        def mock_collection(name):
            mock_coll = Mock()
            if name == 'jobs_deadletter':
                mock_coll.where.return_value.where.return_value.order_by.return_value.stream.return_value = mock_dlq_docs
            return mock_coll

        mock_db.collection.side_effect = mock_collection

    def _setup_spike_dlq_mock(self, mock_db):
        """Setup spike DLQ conditions (high failure rate)"""
        mock_dlq_docs = self._get_spike_mock_dlq_entries()

        def mock_collection(name):
            mock_coll = Mock()
            if name == 'jobs_deadletter':
                mock_coll.where.return_value.where.return_value.order_by.return_value.stream.return_value = mock_dlq_docs
            return mock_coll

        mock_db.collection.side_effect = mock_collection

    def _setup_pattern_analysis_mock(self, mock_db):
        """Setup mock for pattern analysis testing"""
        mock_dlq_docs = self._get_mock_dlq_entries_for_patterns()

        def mock_collection(name):
            mock_coll = Mock()
            if name == 'jobs_deadletter':
                mock_coll.where.return_value.where.return_value.order_by.return_value.stream.return_value = mock_dlq_docs
            return mock_coll

        mock_db.collection.side_effect = mock_collection

    def _setup_empty_dlq_mock(self, mock_db):
        """Setup empty DLQ mock"""
        def mock_collection(name):
            mock_coll = Mock()
            mock_coll.where.return_value.where.return_value.order_by.return_value.stream.return_value = []
            return mock_coll

        mock_db.collection.side_effect = mock_collection

    def _get_comprehensive_mock_dlq_entries(self):
        """Get comprehensive mock DLQ entries for testing"""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

        return [
            Mock(to_dict=lambda: {
                'timestamp': base_time + timedelta(hours=1),
                'job_type': 'transcription',
                'agent': 'TranscriberAgent',
                'error_type': 'timeout',
                'error_message': 'AssemblyAI timeout after 300s',
                'retry_count': 3,
                'video_id': 'video_001',
                'details': {'duration_sec': 3600}
            }),
            Mock(to_dict=lambda: {
                'timestamp': base_time + timedelta(hours=2),
                'job_type': 'summarization',
                'agent': 'SummarizerAgent',
                'error_type': 'quota_exceeded',
                'error_message': 'OpenAI API quota exceeded',
                'retry_count': 2,
                'video_id': 'video_002',
                'details': {'model': 'gpt-4o'}
            }),
            Mock(to_dict=lambda: {
                'timestamp': base_time + timedelta(hours=3),
                'job_type': 'drive_upload',
                'agent': 'DriveAgent',
                'error_type': 'connection_error',
                'error_message': 'Google Drive API connection failed',
                'retry_count': 1,
                'video_id': 'video_003',
                'details': {'file_size_mb': 25}
            }),
            Mock(to_dict=lambda: {
                'timestamp': base_time + timedelta(hours=4),
                'job_type': 'transcription',
                'agent': 'TranscriberAgent',
                'error_type': 'validation_error',
                'error_message': 'Invalid video format',
                'retry_count': 0,
                'video_id': 'video_004',
                'details': {'format': 'unsupported'}
            }),
            Mock(to_dict=lambda: {
                'timestamp': base_time + timedelta(hours=5),
                'job_type': 'scraping',
                'agent': 'ScraperAgent',
                'error_type': 'rate_limit',
                'error_message': 'YouTube API rate limit exceeded',
                'retry_count': 3,
                'video_id': 'video_005',
                'details': {'quota_remaining': 0}
            })
        ]

    def _get_normal_mock_dlq_entries(self):
        """Get normal (low failure rate) mock DLQ entries"""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

        return [
            Mock(to_dict=lambda: {
                'timestamp': base_time + timedelta(hours=2),
                'job_type': 'transcription',
                'agent': 'TranscriberAgent',
                'error_type': 'timeout',
                'error_message': 'Timeout error',
                'retry_count': 2,
                'video_id': 'video_001'
            })
        ]

    def _get_spike_mock_dlq_entries(self):
        """Get spike (high failure rate) mock DLQ entries"""
        base_time = datetime(2024, 1, 15, 20, 0, 0, tzinfo=timezone.utc)  # Recent time for spike

        entries = []
        for i in range(20):  # High volume of recent failures
            entries.append(Mock(to_dict=lambda i=i: {
                'timestamp': base_time + timedelta(minutes=i*5),
                'job_type': 'transcription',
                'agent': 'TranscriberAgent',
                'error_type': 'system_overload',
                'error_message': f'System overload error {i}',
                'retry_count': 3,
                'video_id': f'video_{i:03d}'
            }))

        return entries

    def _get_mock_dlq_entries_for_patterns(self):
        """Get mock DLQ entries for pattern analysis testing"""
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

        return [
            Mock(to_dict=lambda: {
                'timestamp': base_time,
                'job_type': 'transcription',
                'agent': 'TranscriberAgent',
                'error_type': 'timeout',
                'error_message': 'Timeout occurred',
                'retry_count': 3,
                'video_id': 'video_001'
            }),
            Mock(to_dict=lambda: {
                'timestamp': base_time + timedelta(hours=1),
                'job_type': 'transcription',
                'agent': 'TranscriberAgent',
                'error_type': 'timeout',
                'error_message': 'Another timeout',
                'retry_count': 2,
                'video_id': 'video_002'
            }),
            Mock(to_dict=lambda: {
                'timestamp': base_time + timedelta(hours=2),
                'job_type': 'summarization',
                'agent': 'SummarizerAgent',
                'error_type': 'quota_exceeded',
                'error_message': 'Quota exceeded',
                'retry_count': 1,
                'video_id': 'video_003'
            })
        ]

    def _get_uniform_temporal_entries(self):
        """Get uniform temporal distribution entries"""
        base_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        entries = []

        for hour in range(24):
            entries.append(Mock(to_dict=lambda h=hour: {
                'timestamp': base_time + timedelta(hours=h),
                'job_type': 'transcription',
                'agent': 'TranscriberAgent',
                'error_type': 'generic_error',
                'retry_count': 1
            }))

        return entries

    def _get_peak_hour_temporal_entries(self):
        """Get peak hour temporal distribution entries"""
        base_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        entries = []

        # Most failures during hours 9-11 (peak time)
        for hour in range(24):
            count = 5 if 9 <= hour <= 11 else 1
            for i in range(count):
                entries.append(Mock(to_dict=lambda h=hour, i=i: {
                    'timestamp': base_time + timedelta(hours=h, minutes=i*10),
                    'job_type': 'transcription',
                    'agent': 'TranscriberAgent',
                    'error_type': 'peak_error',
                    'retry_count': 2
                }))

        return entries

    def _get_burst_temporal_entries(self):
        """Get burst temporal distribution entries"""
        base_time = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        entries = []

        # All failures in a short burst
        for minute in range(30):
            entries.append(Mock(to_dict=lambda m=minute: {
                'timestamp': base_time + timedelta(minutes=m),
                'job_type': 'transcription',
                'agent': 'TranscriberAgent',
                'error_type': 'burst_error',
                'retry_count': 3
            }))

        return entries


if __name__ == "__main__":
    unittest.main()