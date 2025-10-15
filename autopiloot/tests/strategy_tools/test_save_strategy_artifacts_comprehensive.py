"""
Additional comprehensive tests for save_strategy_artifacts.py - targeting remaining missing lines
"""
import unittest
from unittest.mock import patch, MagicMock, call
import sys
import json
import os
from datetime import datetime, timezone

# Set up path

class TestSaveStrategyArtifactsComprehensive(unittest.TestCase):
    """Additional comprehensive tests for missing coverage lines"""

    def setUp(self):
        """Set up test environment with comprehensive mocking."""
        # Mock all external dependencies
        self.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'google': MagicMock(),
            'google.cloud': MagicMock(),
            'google.cloud.firestore': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'zep_python': MagicMock(),
            'zep_python.client': MagicMock()
        }

        # Mock pydantic Field properly
        def mock_field(*args, **kwargs):
            return kwargs.get('default', None)

        self.mock_modules['pydantic'].Field = mock_field

        # Mock BaseTool with Agency Swarm v1.0.0 pattern
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        self.mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool

        # Mock environment and config functions
        self.mock_modules['env_loader'].get_required_env_var = MagicMock(return_value='test-value')
        self.mock_modules['env_loader'].load_environment = MagicMock()
        self.mock_modules['loader'].load_app_config = MagicMock(return_value={'test': 'config'})
        self.mock_modules['loader'].get_config_value = MagicMock(return_value='test-config-value')

    def test_validation_empty_urn_direct(self):
        """Test validation error for empty URN (line 206)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="",  # Empty URN
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_drive=True
            )

            result = tool._validate_inputs()
            self.assertIsNotNone(result)
            self.assertEqual(result['error'], 'invalid_urn')

    def test_validation_whitespace_urn_direct(self):
        """Test validation error for whitespace-only URN (line 206)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="   ",  # Whitespace-only URN
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_drive=True
            )

            result = tool._validate_inputs()
            self.assertIsNotNone(result)
            self.assertEqual(result['error'], 'invalid_urn')

    def test_validation_empty_playbook_md_direct(self):
        """Test validation error for empty playbook_md (line 212)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="",  # Empty playbook
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_drive=True
            )

            result = tool._validate_inputs()
            self.assertIsNotNone(result)
            self.assertEqual(result['error'], 'missing_playbook_md')

    def test_validation_whitespace_playbook_md_direct(self):
        """Test validation error for whitespace-only playbook_md (line 212)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="   ",  # Whitespace-only playbook
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_drive=True
            )

            result = tool._validate_inputs()
            self.assertIsNotNone(result)
            self.assertEqual(result['error'], 'missing_playbook_md')

    def test_validation_empty_playbook_json_direct(self):
        """Test validation error for empty playbook_json (line 218)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="# Test",
                playbook_json={},  # Empty JSON
                briefs=[{"test": "brief"}],
                save_to_drive=True
            )

            result = tool._validate_inputs()
            self.assertIsNotNone(result)
            self.assertEqual(result['error'], 'invalid_playbook_json')

    def test_validation_non_dict_playbook_json_direct(self):
        """Test validation error for non-dict playbook_json (line 218)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="# Test",
                playbook_json="not a dict",  # String instead of dict
                briefs=[{"test": "brief"}],
                save_to_drive=True
            )

            result = tool._validate_inputs()
            self.assertIsNotNone(result)
            self.assertEqual(result['error'], 'invalid_playbook_json')

    def test_validation_empty_briefs_direct(self):
        """Test validation error for empty briefs (line 224)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs=[],  # Empty list
                save_to_drive=True
            )

            result = tool._validate_inputs()
            self.assertIsNotNone(result)
            self.assertEqual(result['error'], 'invalid_briefs')

    def test_validation_non_list_briefs_direct(self):
        """Test validation error for non-list briefs (line 224)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs="not a list",  # String instead of list
                save_to_drive=True
            )

            result = tool._validate_inputs()
            self.assertIsNotNone(result)
            self.assertEqual(result['error'], 'invalid_briefs')

    def test_validation_no_storage_enabled_direct(self):
        """Test validation error for no storage enabled (line 231)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_drive=False,  # All storage disabled
                save_to_firestore=False,
                save_to_zep=False
            )

            result = tool._validate_inputs()
            self.assertIsNotNone(result)
            self.assertEqual(result['error'], 'no_storage_enabled')

    def test_drive_client_initialization_exception(self):
        """Test drive client initialization exception handling (lines 280-294)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_drive=True
            )

            # Mock exception during drive client initialization
            with patch('googleapiclient.discovery.build', side_effect=Exception("Drive init failed")):
                client = tool._initialize_drive_client()
                self.assertIsNone(client)  # Should return None on exception

    def test_firestore_client_initialization_exception(self):
        """Test firestore client initialization exception handling (lines 304-318)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_firestore=True
            )

            # Mock exception during firestore client initialization
            with patch('google.cloud.firestore.Client', side_effect=Exception("Firestore init failed")):
                client = tool._initialize_firestore_client()
                self.assertIsNone(client)  # Should return None on exception

    def test_zep_client_initialization_exception(self):
        """Test zep client initialization exception handling (lines 329-335)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_zep=True
            )

            # Mock exception during zep client initialization
            with patch('zep_python.client.ZepClient', side_effect=Exception("Zep init failed")):
                client = tool._initialize_zep_client()
                self.assertIsNone(client)  # Should return None on exception

    def test_drive_save_exception_handling(self):
        """Test drive save exception handling (lines 356-389)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_drive=True
            )

            mock_drive_client = MagicMock()
            mock_artifacts = {
                'urn': 'test_urn',
                'playbook_md': '# Test Playbook',
                'briefs': [{"test": "brief"}],
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Mock exception during drive save
            mock_drive_client.files.side_effect = Exception("Drive save failed")

            result = tool._save_to_drive(mock_drive_client, mock_artifacts)
            self.assertFalse(result.get('success', True))
            self.assertIn('error', result)

    def test_firestore_save_exception_handling(self):
        """Test firestore save exception handling (lines 416-434)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_firestore=True
            )

            mock_firestore_client = MagicMock()
            mock_artifacts = {
                'urn': 'test_urn',
                'playbook_json': {"test": "data"},
                'briefs': [{"test": "brief"}],
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Mock exception during firestore save
            mock_firestore_client.collection.side_effect = Exception("Firestore save failed")

            result = tool._save_to_firestore(mock_firestore_client, mock_artifacts)
            self.assertFalse(result.get('success', True))
            self.assertIn('error', result)

    def test_zep_save_exception_handling(self):
        """Test zep save exception handling (lines 464-479)."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_zep=True
            )

            mock_zep_client = MagicMock()
            mock_artifacts = {
                'urn': 'test_urn',
                'playbook_md': '# Test Playbook',
                'playbook_json': {"test": "data"},
                'briefs': [{"test": "brief"}],
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Mock exception during zep save
            mock_zep_client.document.add_document.side_effect = Exception("Zep save failed")

            result = tool._save_to_zep(mock_zep_client, mock_artifacts)
            self.assertFalse(result.get('success', True))
            self.assertIn('error', result)

    def test_end_to_end_validation_failures(self):
        """Test end-to-end validation failures through run method."""
        with patch.dict('sys.modules', self.mock_modules):
            from strategy_agent.tools.save_strategy_artifacts import SaveStrategyArtifacts

            # Test with empty URN
            tool = SaveStrategyArtifacts(
                urn="",
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_drive=True
            )

            result = tool.run()
            result_data = json.loads(result)
            self.assertEqual(result_data['error'], 'invalid_urn')

            # Test with no storage enabled
            tool = SaveStrategyArtifacts(
                urn="test_urn",
                playbook_md="# Test",
                playbook_json={"test": "data"},
                briefs=[{"test": "brief"}],
                save_to_drive=False,
                save_to_firestore=False,
                save_to_zep=False
            )

            result = tool.run()
            result_data = json.loads(result)
            self.assertEqual(result_data['error'], 'no_storage_enabled')


if __name__ == "__main__":
    unittest.main()