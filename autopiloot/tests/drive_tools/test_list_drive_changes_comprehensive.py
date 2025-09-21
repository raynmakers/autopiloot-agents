#!/usr/bin/env python3
"""
Comprehensive tests for ListDriveChanges tool
Tests Google Drive service initialization, pattern matching, and timestamp parsing
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock
import importlib.util
from datetime import datetime, timezone

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


class TestListDriveChangesComprehensive(unittest.TestCase):
    """Comprehensive tests for ListDriveChanges tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing imports to ensure clean state
        modules_to_clear = [k for k in list(sys.modules.keys())
                           if 'list_drive_changes' in k]
        for module in modules_to_clear:
            del sys.modules[module]

    def test_drive_service_initialization_success(self):
        """Test successful Google Drive service initialization."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock(),
            'datetime': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock environment variable
            mock_env = MagicMock()
            mock_env.return_value = "/path/to/credentials.json"
            sys.modules['env_loader'].get_required_env_var = mock_env

            # Mock Google services
            mock_credentials = MagicMock()
            mock_service = MagicMock()
            sys.modules['google.oauth2.service_account'].Credentials.from_service_account_file.return_value = mock_credentials
            sys.modules['googleapiclient.discovery'].build.return_value = mock_service

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool
            tool = ListDriveChanges(file_ids=["test_file_id"])

            # Test service initialization
            service = tool._get_drive_service()

            # Verify service creation
            self.assertEqual(service, mock_service)
            mock_env.assert_called_with("GOOGLE_APPLICATION_CREDENTIALS")

    def test_drive_service_initialization_failure(self):
        """Test Google Drive service initialization failure."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock(),
            'datetime': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock environment variable failure
            mock_env = MagicMock()
            mock_env.side_effect = Exception("Credentials file not found")
            sys.modules['env_loader'].get_required_env_var = mock_env

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool
            tool = ListDriveChanges(file_ids=["test_file_id"])

            # Test service initialization failure
            with self.assertRaises(Exception) as context:
                tool._get_drive_service()

            self.assertIn("Failed to initialize Drive service", str(context.exception))
            self.assertIn("Credentials file not found", str(context.exception))

    def test_pattern_matching_include_patterns(self):
        """Test file name pattern matching with include patterns."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock fnmatch behavior
            def mock_fnmatch(name, pattern):
                if pattern == "*.pdf" and name.lower().endswith('.pdf'):
                    return True
                if pattern == "*.docx" and name.lower().endswith('.docx'):
                    return True
                return False

            sys.modules['fnmatch'].fnmatch = mock_fnmatch

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool with include patterns
            tool = ListDriveChanges(
                file_ids=["test_file_id"],
                include_patterns=["*.pdf", "*.docx"],
                exclude_patterns=[]
            )

            # Test matching files
            self.assertTrue(tool._matches_patterns("document.pdf"))
            self.assertTrue(tool._matches_patterns("report.docx"))
            self.assertTrue(tool._matches_patterns("DOCUMENT.PDF"))  # Case insensitive

            # Test non-matching files
            self.assertFalse(tool._matches_patterns("document.txt"))
            self.assertFalse(tool._matches_patterns("image.png"))

    def test_pattern_matching_exclude_patterns(self):
        """Test file name pattern matching with exclude patterns."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock fnmatch behavior
            def mock_fnmatch(name, pattern):
                if pattern == "~*" and name.lower().startswith('~'):
                    return True
                if pattern == "*.tmp" and name.lower().endswith('.tmp'):
                    return True
                return False

            sys.modules['fnmatch'].fnmatch = mock_fnmatch

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool with exclude patterns
            tool = ListDriveChanges(
                file_ids=["test_file_id"],
                include_patterns=[],  # Empty means include all
                exclude_patterns=["~*", "*.tmp"]
            )

            # Test excluded files
            self.assertFalse(tool._matches_patterns("~backup.txt"))
            self.assertFalse(tool._matches_patterns("temp.tmp"))

            # Test included files
            self.assertTrue(tool._matches_patterns("document.pdf"))
            self.assertTrue(tool._matches_patterns("report.docx"))

    def test_pattern_matching_no_patterns(self):
        """Test file name pattern matching with no patterns (include all)."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'fnmatch': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool with no patterns
            tool = ListDriveChanges(
                file_ids=["test_file_id"],
                include_patterns=[],
                exclude_patterns=[]
            )

            # Test that all files are included
            self.assertTrue(tool._matches_patterns("document.pdf"))
            self.assertTrue(tool._matches_patterns("report.docx"))
            self.assertTrue(tool._matches_patterns("image.png"))
            self.assertTrue(tool._matches_patterns("any_file.xyz"))

    def test_iso_timestamp_parsing_with_z_suffix(self):
        """Test ISO timestamp parsing with Z suffix."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'googleapiclient': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool
            tool = ListDriveChanges(file_ids=["test_file_id"])

            # Test Z suffix parsing
            result = tool._parse_iso_timestamp("2025-01-01T12:00:00Z")
            expected = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            self.assertEqual(result, expected)

    def test_iso_timestamp_parsing_with_timezone(self):
        """Test ISO timestamp parsing with timezone offset."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'googleapiclient': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool
            tool = ListDriveChanges(file_ids=["test_file_id"])

            # Test timezone offset parsing
            result = tool._parse_iso_timestamp("2025-01-01T12:00:00+02:00")
            self.assertIsInstance(result, datetime)
            self.assertIsNotNone(result.tzinfo)

    def test_iso_timestamp_parsing_no_timezone(self):
        """Test ISO timestamp parsing without timezone (assumes UTC)."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'googleapiclient': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool
            tool = ListDriveChanges(file_ids=["test_file_id"])

            # Test no timezone parsing (should assume UTC)
            result = tool._parse_iso_timestamp("2025-01-01T12:00:00")
            expected = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            self.assertEqual(result, expected)

    def test_iso_timestamp_parsing_invalid_format(self):
        """Test ISO timestamp parsing with invalid format."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'googleapiclient': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Import tool
            spec = importlib.util.spec_from_file_location(
                "list_drive_changes",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_drive_changes.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            ListDriveChanges = module.ListDriveChanges

            # Create tool
            tool = ListDriveChanges(file_ids=["test_file_id"])

            # Test invalid format
            with self.assertRaises(ValueError) as context:
                tool._parse_iso_timestamp("invalid-timestamp")

            self.assertIn("Invalid ISO timestamp format", str(context.exception))


if __name__ == '__main__':
    unittest.main(verbosity=2)