#!/usr/bin/env python3
"""
Test suite for drive_agent/__init__.py
Tests package initialization, imports, and exports
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path for imports

class TestDriveAgentInit(unittest.TestCase):
    """Test cases for drive_agent package initialization."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing drive_agent imports to ensure fresh testing
        modules_to_clear = [k for k in list(sys.modules.keys()) if 'drive_agent' in k]
        for module in modules_to_clear:
            del sys.modules[module]

    def test_package_imports_successfully(self):
        """Test that the drive_agent package can be imported without errors."""
        # Mock agency_swarm to prevent actual agent initialization during import
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            try:
                import drive_agent
                self.assertIsNotNone(drive_agent)
            except ImportError as e:
                self.fail(f"Failed to import drive_agent package: {e}")

    def test_drive_agent_attribute_available(self):
        """Test that the drive_agent attribute is available after import."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            import drive_agent

            # Check that drive_agent attribute exists
            self.assertTrue(hasattr(drive_agent, 'drive_agent'))
            self.assertIsNotNone(drive_agent.drive_agent)

    def test_all_exports_defined(self):
        """Test that __all__ is properly defined and contains expected exports."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            import drive_agent

            # Check that __all__ is defined
            self.assertTrue(hasattr(drive_agent, '__all__'))
            self.assertIsInstance(drive_agent.__all__, list)

            # Check that it contains the expected export
            self.assertIn('drive_agent', drive_agent.__all__)
            self.assertEqual(len(drive_agent.__all__), 1)

    def test_all_exports_are_accessible(self):
        """Test that all items in __all__ are actually accessible."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            import drive_agent

            # Check that all items in __all__ are accessible
            for item in drive_agent.__all__:
                self.assertTrue(hasattr(drive_agent, item),
                               f"Item '{item}' in __all__ is not accessible")

    def test_from_import_works(self):
        """Test that 'from drive_agent import drive_agent' works correctly."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            # Test direct import of drive_agent from package
            from drive_agent import drive_agent as imported_agent
            self.assertIsNotNone(imported_agent)

    def test_star_import_works(self):
        """Test that 'from drive_agent import *' works and imports expected items."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            # Get the current globals before import
            globals_before = set(globals().keys())

            # Perform star import
            exec('from drive_agent import *', globals())

            # Check that drive_agent was imported
            self.assertIn('drive_agent', globals())

            # Check that only expected items were imported (those in __all__)
            globals_after = set(globals().keys())
            new_items = globals_after - globals_before

            # Should only import items from __all__
            expected_imports = {'drive_agent'}
            self.assertEqual(new_items, expected_imports)

    def test_package_docstring_exists(self):
        """Test that the package has a proper docstring."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            import drive_agent

            # Check that package has a docstring
            self.assertIsNotNone(drive_agent.__doc__)
            self.assertIsInstance(drive_agent.__doc__, str)
            self.assertTrue(len(drive_agent.__doc__.strip()) > 0)

            # Check that docstring contains relevant keywords
            docstring_lower = drive_agent.__doc__.lower()
            self.assertIn('google drive', docstring_lower)
            self.assertIn('agent', docstring_lower)

    def test_package_structure_integrity(self):
        """Test that the package structure is correct."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            import drive_agent

            # Check package name
            self.assertEqual(drive_agent.__name__, 'drive_agent')

            # Check that it's a package (has __path__)
            self.assertTrue(hasattr(drive_agent, '__path__'))

    def test_import_with_config_loading_failure(self):
        """Test that package imports correctly even when config loading fails."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            # Mock config loading to fail
            with patch('drive_agent.drive_agent.load_app_config', side_effect=Exception("Config failed")):
                try:
                    import drive_agent
                    self.assertIsNotNone(drive_agent.drive_agent)
                except Exception as e:
                    self.fail(f"Package import failed with config error: {e}")

    def test_import_with_agency_swarm_issues(self):
        """Test package behavior when agency_swarm has issues."""
        # Test with missing agency_swarm
        with patch.dict('sys.modules', {'agency_swarm': None}):
            try:
                import drive_agent
                # Should fail gracefully or handle the missing dependency
                self.assertIsNotNone(drive_agent)
            except ImportError:
                # This is acceptable - missing dependencies should cause ImportError
                pass

    def test_multiple_imports_same_instance(self):
        """Test that multiple imports return the same instance."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            import drive_agent as first_import
            import drive_agent as second_import

            # Should be the same module object
            self.assertIs(first_import, second_import)
            self.assertIs(first_import.drive_agent, second_import.drive_agent)

    def test_relative_import_structure(self):
        """Test that the relative import in __init__.py works correctly."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            # Import the package
            import drive_agent

            # Verify that the imported drive_agent is from the drive_agent module
            from drive_agent.drive_agent import drive_agent as direct_import

            # They should be the same object
            self.assertIs(drive_agent.drive_agent, direct_import)


if __name__ == '__main__':
    unittest.main()