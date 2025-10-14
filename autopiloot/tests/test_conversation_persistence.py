"""
Tests for Agency Swarm v1.2.0 Conversation Persistence Feature (TASK-AGS-0097)

Tests cover:
1. Thread saving to Firestore
2. Thread loading from Firestore
3. Thread cleanup after retention period
4. Persistence enable/disable toggle
5. AutopilootAgency initialization with callbacks
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta, timezone
import json


class TestThreadPersistence(unittest.TestCase):
    """Test conversation persistence callbacks in AutopilootAgency"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_config = {
            'agency': {
                'persistence': {
                    'enabled': True,
                    'collection': 'agency_threads_test',
                    'retention_days': 30
                }
            },
            'enabled_agents': ['orchestrator_agent'],
            'communication_flows': []
        }

    @patch('agency.firestore')
    @patch('agency.load_app_config')
    @patch('agency.create_agent_registry')
    def test_save_threads_to_firestore_success(self, mock_registry, mock_config, mock_firestore):
        """Test successful thread saving to Firestore"""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock config
        mock_config.return_value = self.mock_config

        # Mock agent registry
        mock_registry_instance = Mock()
        mock_registry_instance.loaded_agents = {'orchestrator_agent': Mock()}
        mock_registry_instance.get_agent.return_value = Mock()
        mock_registry.return_value = mock_registry_instance

        # Import after mocking
        from agency import AutopilootAgency

        # Create agency instance
        agency = AutopilootAgency(config=self.mock_config)

        # Test data
        threads = {
            'thread_123': {'messages': [{'role': 'user', 'content': 'test'}]},
            'thread_456': {'messages': [{'role': 'assistant', 'content': 'response'}]}
        }

        # Call save callback
        agency._save_threads_to_firestore(threads)

        # Verify Firestore client was created
        mock_firestore.Client.assert_called_once()

        # Verify set was called for each thread
        assert mock_db.collection.call_count == 2

    @patch('agency.firestore')
    @patch('agency.load_app_config')
    @patch('agency.create_agent_registry')
    def test_load_threads_from_firestore_success(self, mock_registry, mock_config, mock_firestore):
        """Test successful thread loading from Firestore"""
        # Mock Firestore client and documents
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock document snapshots
        mock_doc1 = Mock()
        mock_doc1.id = 'thread_123'
        mock_doc1.to_dict.return_value = {
            'thread_id': 'thread_123',
            'messages': [{'role': 'user', 'content': 'test'}]
        }

        mock_doc2 = Mock()
        mock_doc2.id = 'thread_456'
        mock_doc2.to_dict.return_value = {
            'thread_id': 'thread_456',
            'messages': [{'role': 'assistant', 'content': 'response'}]
        }

        mock_db.collection.return_value.stream.return_value = [mock_doc1, mock_doc2]

        # Mock config
        mock_config.return_value = self.mock_config

        # Mock agent registry
        mock_registry_instance = Mock()
        mock_registry_instance.loaded_agents = {'orchestrator_agent': Mock()}
        mock_registry_instance.get_agent.return_value = Mock()
        mock_registry.return_value = mock_registry_instance

        # Import after mocking
        from agency import AutopilootAgency

        # Create agency instance
        agency = AutopilootAgency(config=self.mock_config)

        # Call load callback
        threads = agency._load_threads_from_firestore()

        # Verify results
        self.assertEqual(len(threads), 2)
        self.assertIn('thread_123', threads)
        self.assertIn('thread_456', threads)
        self.assertEqual(threads['thread_123'], [{'role': 'user', 'content': 'test'}])

    @patch('agency.load_app_config')
    @patch('agency.create_agent_registry')
    def test_persistence_disabled_no_callbacks(self, mock_registry, mock_config):
        """Test that callbacks are not set when persistence is disabled"""
        # Create config with persistence disabled
        disabled_config = self.mock_config.copy()
        disabled_config['agency']['persistence']['enabled'] = False

        mock_config.return_value = disabled_config

        # Mock agent registry
        mock_registry_instance = Mock()
        mock_registry_instance.loaded_agents = {'orchestrator_agent': Mock()}
        mock_registry_instance.get_agent.return_value = Mock()
        mock_registry.return_value = mock_registry_instance

        # Import after mocking
        with patch('agency.Agency.__init__', return_value=None) as mock_agency_init:
            from agency import AutopilootAgency

            agency = AutopilootAgency(config=disabled_config)

            # Verify Agency init was called without callbacks
            call_kwargs = mock_agency_init.call_args[1]
            self.assertNotIn('save_threads_callback', call_kwargs)
            self.assertNotIn('load_threads_callback', call_kwargs)


class TestThreadCleanup(unittest.TestCase):
    """Test thread cleanup utility functions"""

    @patch('core.thread_cleanup.firestore')
    def test_cleanup_old_threads_success(self, mock_firestore):
        """Test successful cleanup of old threads"""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock old thread documents
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
        old_thread1 = Mock()
        old_thread1.reference = Mock()
        old_thread2 = Mock()
        old_thread2.reference = Mock()

        mock_db.collection.return_value.where.return_value.stream.return_value = [
            old_thread1,
            old_thread2
        ]

        # Import and test
        from core.thread_cleanup import cleanup_old_threads

        deleted_count = cleanup_old_threads(retention_days=30, collection='agency_threads_test')

        # Verify results
        self.assertEqual(deleted_count, 2)
        old_thread1.reference.delete.assert_called_once()
        old_thread2.reference.delete.assert_called_once()

    @patch('core.thread_cleanup.firestore')
    def test_get_thread_stats_with_threads(self, mock_firestore):
        """Test thread statistics when threads exist"""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock thread documents with different ages
        now = datetime.now(timezone.utc)
        thread1 = Mock()
        thread1.to_dict.return_value = {
            'updated_at': now - timedelta(days=5)
        }
        thread2 = Mock()
        thread2.to_dict.return_value = {
            'updated_at': now - timedelta(days=15)
        }
        thread3 = Mock()
        thread3.to_dict.return_value = {
            'updated_at': now - timedelta(days=25)
        }

        mock_db.collection.return_value.stream.return_value = [thread1, thread2, thread3]

        # Import and test
        from core.thread_cleanup import get_thread_stats

        stats = get_thread_stats(collection='agency_threads_test')

        # Verify stats
        self.assertEqual(stats['total_threads'], 3)
        self.assertEqual(stats['oldest_thread_age_days'], 25)
        self.assertEqual(stats['newest_thread_age_days'], 5)

    @patch('core.thread_cleanup.firestore')
    def test_get_thread_stats_empty(self, mock_firestore):
        """Test thread statistics when no threads exist"""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # No threads
        mock_db.collection.return_value.stream.return_value = []

        # Import and test
        from core.thread_cleanup import get_thread_stats

        stats = get_thread_stats(collection='agency_threads_test')

        # Verify stats for empty collection
        self.assertEqual(stats['total_threads'], 0)
        self.assertIsNone(stats['oldest_thread_age_days'])
        self.assertIsNone(stats['newest_thread_age_days'])


class TestFirebaseFunctionThreadCleanup(unittest.TestCase):
    """Test Firebase Function for thread cleanup"""

    @patch('services.firebase.functions.scheduler.db')
    @patch('services.firebase.functions.scheduler.get_config_value')
    @patch('services.firebase.functions.scheduler.do_cleanup')
    @patch('services.firebase.functions.scheduler.get_thread_stats')
    def test_cleanup_function_success(self, mock_stats, mock_cleanup, mock_config, mock_db):
        """Test successful execution of cleanup Firebase Function"""
        # Mock configuration
        mock_config.side_effect = lambda key, default=None: {
            'agency.persistence': {
                'enabled': True,
                'collection': 'agency_threads',
                'retention_days': 30
            }
        }.get(key, default)

        # Mock thread stats
        mock_stats.side_effect = [
            {'total_threads': 100, 'oldest_thread_age_days': 45, 'newest_thread_age_days': 1},  # before
            {'total_threads': 85, 'oldest_thread_age_days': 28, 'newest_thread_age_days': 1}    # after
        ]

        # Mock cleanup
        mock_cleanup.return_value = 15  # 15 threads deleted

        # Create mock event
        mock_event = Mock()
        mock_event.timestamp = '2025-10-14T02:00:00Z'
        mock_event.id = 'test_event_123'

        # Import and call function
        from services.firebase.functions.scheduler import cleanup_old_threads

        result = cleanup_old_threads(mock_event)

        # Verify result
        self.assertTrue(result['ok'])
        self.assertEqual(result['deleted_count'], 15)
        self.assertEqual(result['remaining_threads'], 85)
        self.assertEqual(result['retention_days'], 30)

        # Verify cleanup was called
        mock_cleanup.assert_called_once_with(retention_days=30, collection='agency_threads')

        # Verify audit log was written
        mock_db.collection.assert_called()

    @patch('services.firebase.functions.scheduler.db')
    @patch('services.firebase.functions.scheduler.get_config_value')
    def test_cleanup_function_persistence_disabled(self, mock_config, mock_db):
        """Test cleanup function when persistence is disabled"""
        # Mock configuration with persistence disabled
        mock_config.side_effect = lambda key, default=None: {
            'agency.persistence': {
                'enabled': False,
                'collection': 'agency_threads',
                'retention_days': 30
            }
        }.get(key, default)

        # Create mock event
        mock_event = Mock()
        mock_event.timestamp = '2025-10-14T02:00:00Z'

        # Import and call function
        from services.firebase.functions.scheduler import cleanup_old_threads

        result = cleanup_old_threads(mock_event)

        # Verify result indicates disabled
        self.assertTrue(result['ok'])
        self.assertEqual(result['message'], 'Thread persistence disabled')


if __name__ == '__main__':
    unittest.main()
