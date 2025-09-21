#!/usr/bin/env python3
"""
Comprehensive coverage tests for FetchFileContent tool
Targets 0% → 80%+ coverage using proven testing patterns
Focuses on Google Drive API integration, content processing, and error handling
"""

import unittest
import json
import sys
import os
import base64
import io
from unittest.mock import patch, MagicMock, mock_open
import importlib.util

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


class TestFetchFileContentComprehensive(unittest.TestCase):
    """Comprehensive coverage tests for FetchFileContent tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing imports to ensure clean state
        modules_to_clear = [k for k in list(sys.modules.keys())
                           if 'fetch_file_content' in k]
        for module in modules_to_clear:
            del sys.modules[module]

    def test_optional_imports_when_libraries_missing(self):
        """Test optional PDF/DOCX import handling when libraries are missing."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            # Force ImportError for optional libraries
            'PyPDF2': None,
            'docx': None
        }):
            # Setup basic mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Force ImportError by patching __import__
            import builtins
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name in ['PyPDF2', 'docx']:
                    raise ImportError(f"No module named '{name}'")
                return original_import(name, *args, **kwargs)

            with patch('builtins.__import__', side_effect=mock_import):
                # Import using direct file loading
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Verify the flags are set correctly
                self.assertFalse(module.PDF_AVAILABLE)
                self.assertFalse(module.DOCX_AVAILABLE)

    def test_optional_imports_when_libraries_available(self):
        """Test optional PDF/DOCX import handling when libraries are available."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'PyPDF2': MagicMock(),
            'docx': MagicMock()
        }):
            # Setup basic mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Import using direct file loading
            spec = importlib.util.spec_from_file_location(
                "fetch_file_content",
                "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Verify the flags are set correctly
            self.assertTrue(module.PDF_AVAILABLE)
            self.assertTrue(module.DOCX_AVAILABLE)

    def test_drive_service_initialization_success(self):
        """Test successful Google Drive service initialization."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock environment and Google APIs
            mock_env_loader = MagicMock()
            mock_env_loader.get_required_env_var.return_value = "/path/to/credentials.json"
            sys.modules['env_loader'] = mock_env_loader

            mock_credentials = MagicMock()
            sys.modules['google.oauth2.service_account'].Credentials.from_service_account_file.return_value = mock_credentials

            mock_service = MagicMock()
            sys.modules['googleapiclient.discovery'].build.return_value = mock_service

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="test_file_id",
                    max_size_mb=5.0
                )

                # Test _get_drive_service method
                service = tool._get_drive_service()
                self.assertIsNotNone(service)

                # Verify API calls were made successfully (service was created)
                mock_env_loader.get_required_env_var.assert_called_with("GOOGLE_APPLICATION_CREDENTIALS")
                self.assertEqual(service, mock_service)

    def test_drive_service_initialization_failure(self):
        """Test Google Drive service initialization failure."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock environment failure
            mock_env_loader = MagicMock()
            mock_env_loader.get_required_env_var.side_effect = Exception("Credentials not found")
            sys.modules['env_loader'] = mock_env_loader

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="test_file_id",
                    max_size_mb=5.0
                )

                # Test _get_drive_service method should raise exception
                with self.assertRaises(Exception) as context:
                    tool._get_drive_service()

                self.assertIn("Failed to initialize Drive service", str(context.exception))

    def test_size_limit_from_parameter(self):
        """Test size limit calculation when max_size_mb parameter is provided."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 20}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool with explicit max_size_mb
                tool = FetchFileContent(
                    file_id="test_file_id",
                    max_size_mb=5.0  # 5 MB should override config
                )

                # Test _get_size_limit method
                size_limit = tool._get_size_limit()
                expected_bytes = int(5.0 * 1024 * 1024)  # 5 MB in bytes
                self.assertEqual(size_limit, expected_bytes)

    def test_size_limit_from_config(self):
        """Test size limit calculation when max_size_mb is None (uses config)."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 15}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                FetchFileContent = module.FetchFileContent

                # Create tool with max_size_mb=None (should use config)
                tool = FetchFileContent(
                    file_id="test_file_id",
                    max_size_mb=None
                )

                # Test _get_size_limit method
                size_limit = tool._get_size_limit()
                expected_bytes = int(15 * 1024 * 1024)  # 15 MB from config
                self.assertEqual(size_limit, expected_bytes)

    def test_pdf_text_extraction_when_pypdf2_unavailable(self):
        """Test PDF text extraction when PyPDF2 is not available."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Force PDF_AVAILABLE to False
                module.PDF_AVAILABLE = False

                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="test_file_id",
                    max_size_mb=5.0
                )

                # Test _extract_text_from_pdf method
                result = tool._extract_text_from_pdf(b"fake_pdf_bytes")
                self.assertIn("PyPDF2 not installed", result)

    def test_pdf_text_extraction_with_mocked_pypdf2(self):
        """Test PDF text extraction with successful PyPDF2."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'PyPDF2': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock PyPDF2
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Sample PDF text content"

            mock_reader = MagicMock()
            mock_reader.pages = [mock_page]

            sys.modules['PyPDF2'].PdfReader.return_value = mock_reader

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Force PDF_AVAILABLE to True
                module.PDF_AVAILABLE = True

                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="test_file_id",
                    max_size_mb=5.0
                )

                # Test _extract_text_from_pdf method
                result = tool._extract_text_from_pdf(b"fake_pdf_bytes")
                self.assertIn("Sample PDF text content", result)
                self.assertIn("--- Page 1 ---", result)

    def test_pdf_text_extraction_with_error(self):
        """Test PDF text extraction with PyPDF2 error."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock(),
            'PyPDF2': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock PyPDF2 to raise an exception
            sys.modules['PyPDF2'].PdfReader.side_effect = Exception("PDF parsing failed")

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Force PDF_AVAILABLE to True
                module.PDF_AVAILABLE = True

                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="test_file_id",
                    max_size_mb=5.0
                )

                # Test _extract_text_from_pdf method should handle error
                result = tool._extract_text_from_pdf(b"fake_pdf_bytes")
                self.assertIn("Error processing PDF", result)

    def test_docx_text_extraction_when_python_docx_unavailable(self):
        """Test DOCX text extraction when python-docx is not available."""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'agency_swarm.tools.BaseTool': MagicMock(),
            'pydantic': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock(),
            'google.oauth2': MagicMock(),
            'google.oauth2.service_account': MagicMock(),
            'googleapiclient': MagicMock(),
            'googleapiclient.discovery': MagicMock(),
            'googleapiclient.errors': MagicMock()
        }):
            # Setup mocks
            sys.modules['pydantic'].Field = lambda *args, **kwargs: args[0] if args else kwargs

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            with patch('loader.get_config_value') as mock_config:
                def mock_get_config(key, default=None):
                    if key == "drive":
                        return {"tracking": {"max_file_size_mb": 10}}
                    return default
                mock_config.side_effect = mock_get_config

                # Import tool
                spec = importlib.util.spec_from_file_location(
                    "fetch_file_content",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/fetch_file_content.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Force DOCX_AVAILABLE to False
                module.DOCX_AVAILABLE = False

                FetchFileContent = module.FetchFileContent

                # Create tool
                tool = FetchFileContent(
                    file_id="test_file_id",
                    max_size_mb=5.0
                )

                # Test _extract_text_from_docx method
                result = tool._extract_text_from_docx(b"fake_docx_bytes")
                self.assertIn("python-docx not installed", result)


if __name__ == '__main__':
    unittest.main(verbosity=2)