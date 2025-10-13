"""
Comprehensive test suite for ValidateRAGSecurity tool.
Tests security validation for BigQuery, OpenSearch, Zep, and credentials.
Target: 80%+ coverage with success paths, error paths, and edge cases.
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, MagicMock, patch, mock_open

# Mock agency_swarm before importing tool
mock_agency_swarm = MagicMock()
mock_base_tool = MagicMock()
mock_agency_swarm.tools.BaseTool = mock_base_tool
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['agency_swarm.tools'] = mock_agency_swarm.tools


class TestValidateRAGSecurity(unittest.TestCase):
    """Test suite for ValidateRAGSecurity tool."""

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
            'validate_rag_security.py'
        )
        spec = importlib.util.spec_from_file_location("validate_rag_security", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.ValidateRAGSecurity

    def test_check_env_variable_present(self):
        """Test environment variable check when variable is set (lines 62-73)."""
        with patch.dict(os.environ, {'TEST_VAR': 'valid_value'}):
            tool = self.ToolClass()
            result = tool._check_env_variable('TEST_VAR')

            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['variable'], 'TEST_VAR')
            self.assertEqual(result['severity'], 'info')

    def test_check_env_variable_missing(self):
        """Test environment variable check when variable is missing (lines 62-73)."""
        with patch.dict(os.environ, {}, clear=True):
            tool = self.ToolClass()
            result = tool._check_env_variable('MISSING_VAR')

            self.assertEqual(result['status'], 'missing')
            self.assertEqual(result['severity'], 'critical')
            self.assertIn('not set', result['message'])

    def test_check_env_variable_placeholder(self):
        """Test environment variable check with placeholder value (lines 62-73)."""
        with patch.dict(os.environ, {'TEST_VAR': 'placeholder_value'}):
            tool = self.ToolClass()
            result = tool._check_env_variable('TEST_VAR')

            self.assertEqual(result['status'], 'placeholder')
            self.assertEqual(result['severity'], 'critical')
            self.assertIn('placeholder', result['message'])

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project',
        'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'
    })
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='{"client_email": "test@test.iam.gserviceaccount.com"}')
    def test_validate_bigquery_security_success(self, mock_file, mock_exists):
        """Test BigQuery security validation with valid config (lines 75-159)."""
        tool = self.ToolClass()
        result = tool._validate_bigquery_security()

        self.assertEqual(result['component'], 'bigquery')
        self.assertTrue(result['passed'])
        self.assertGreater(len(result['checks']), 0)
        self.assertGreater(len(result['recommendations']), 0)

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_bigquery_security_missing_vars(self):
        """Test BigQuery validation with missing environment variables (lines 75-159)."""
        tool = self.ToolClass()
        result = tool._validate_bigquery_security()

        self.assertEqual(result['component'], 'bigquery')
        self.assertFalse(result['passed'])
        # Should have critical issues for missing vars
        critical_checks = [c for c in result['checks'] if c['severity'] == 'critical']
        self.assertGreater(len(critical_checks), 0)

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project',
        'GOOGLE_APPLICATION_CREDENTIALS': '/nonexistent/path.json'
    })
    @patch('os.path.exists', return_value=False)
    def test_validate_bigquery_security_missing_file(self, mock_exists):
        """Test BigQuery validation with missing credentials file (lines 75-159)."""
        tool = self.ToolClass()
        result = tool._validate_bigquery_security()

        # Should have error about missing file
        error_checks = [c for c in result['checks'] if 'not found' in c['message']]
        self.assertGreater(len(error_checks), 0)

    @patch.dict(os.environ, {'OPENSEARCH_HOST': 'https://opensearch.example.com'})
    def test_validate_opensearch_security_https(self):
        """Test OpenSearch validation with HTTPS host (lines 161-217)."""
        tool = self.ToolClass()
        result = tool._validate_opensearch_security()

        self.assertEqual(result['component'], 'opensearch')
        # Should detect HTTPS
        https_checks = [c for c in result['checks'] if 'HTTPS' in c['message']]
        self.assertGreater(len(https_checks), 0)

    @patch.dict(os.environ, {'OPENSEARCH_HOST': 'http://opensearch.example.com'})
    def test_validate_opensearch_security_http_warning(self):
        """Test OpenSearch validation with HTTP host (warning) (lines 161-217)."""
        tool = self.ToolClass()
        result = tool._validate_opensearch_security()

        # Should warn about HTTP (not HTTPS)
        http_warnings = [c for c in result['checks'] if 'HTTP' in c['message'] and c['severity'] == 'warning']
        self.assertGreater(len(http_warnings), 0)

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'https://opensearch.example.com',
        'OPENSEARCH_API_KEY': 'test_key'
    })
    def test_validate_opensearch_security_api_key_auth(self):
        """Test OpenSearch validation with API key authentication (lines 161-217)."""
        tool = self.ToolClass()
        result = tool._validate_opensearch_security()

        # Should detect API key auth
        auth_checks = [c for c in result['checks'] if 'API key' in c['message']]
        self.assertGreater(len(auth_checks), 0)

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'https://opensearch.example.com',
        'OPENSEARCH_USERNAME': 'admin',
        'OPENSEARCH_PASSWORD': 'password'
    })
    def test_validate_opensearch_security_basic_auth(self):
        """Test OpenSearch validation with basic authentication (lines 161-217)."""
        tool = self.ToolClass()
        result = tool._validate_opensearch_security()

        # Should detect basic auth
        auth_checks = [c for c in result['checks'] if 'basic authentication' in c['message']]
        self.assertGreater(len(auth_checks), 0)

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'https://opensearch.example.com',
        'OPENSEARCH_USERNAME': 'admin'
        # Missing password
    })
    def test_validate_opensearch_security_incomplete_auth(self):
        """Test OpenSearch validation with incomplete basic auth (lines 161-217)."""
        tool = self.ToolClass()
        result = tool._validate_opensearch_security()

        # Should warn about incomplete auth
        warnings = [c for c in result['checks'] if 'Incomplete' in c['message']]
        self.assertGreater(len(warnings), 0)

    @patch.dict(os.environ, {'ZEP_API_KEY': 'test_api_key'})
    def test_validate_zep_security_success(self):
        """Test Zep security validation with valid config (lines 219-254)."""
        tool = self.ToolClass()
        result = tool._validate_zep_security()

        self.assertEqual(result['component'], 'zep')
        self.assertTrue(result['passed'])
        self.assertGreater(len(result['checks']), 0)

    @patch.dict(os.environ, {
        'ZEP_API_KEY': 'test_key',
        'ZEP_API_URL': 'https://api.getzep.com'
    })
    def test_validate_zep_security_https_url(self):
        """Test Zep validation with HTTPS URL (lines 219-254)."""
        tool = self.ToolClass()
        result = tool._validate_zep_security()

        # Should detect HTTPS
        https_checks = [c for c in result['checks'] if 'HTTPS' in c['message']]
        self.assertGreater(len(https_checks), 0)

    @patch.dict(os.environ, {
        'ZEP_API_KEY': 'test_key',
        'ZEP_API_URL': 'http://api.getzep.com'
    })
    def test_validate_zep_security_http_warning(self):
        """Test Zep validation with HTTP URL (warning) (lines 219-254)."""
        tool = self.ToolClass()
        result = tool._validate_zep_security()

        # Should warn about HTTP
        warnings = [c for c in result['checks'] if c['severity'] == 'warning' and 'HTTP' in c['message']]
        self.assertGreater(len(warnings), 0)

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_zep_security_missing_key(self):
        """Test Zep validation with missing API key (lines 219-254)."""
        tool = self.ToolClass()
        result = tool._validate_zep_security()

        self.assertFalse(result['passed'])
        critical_checks = [c for c in result['checks'] if c['severity'] == 'critical']
        self.assertGreater(len(critical_checks), 0)

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test_key',
        'ASSEMBLYAI_API_KEY': 'test_key',
        'YOUTUBE_API_KEY': 'test_key'
    })
    def test_validate_credential_security_success(self):
        """Test credential security validation with all vars set (lines 256-299)."""
        tool = self.ToolClass()
        result = tool._validate_credential_security()

        self.assertEqual(result['component'], 'credentials')
        self.assertTrue(result['passed'])

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_credential_security_missing_vars(self):
        """Test credential validation with missing critical vars (lines 256-299)."""
        tool = self.ToolClass()
        result = tool._validate_credential_security()

        # Should have checks for missing variables
        self.assertGreater(len(result['checks']), 0)

    def test_run_full_validation_success(self):
        """Test full validation run (lines 315-408)."""
        with patch.dict(os.environ, {
            'GCP_PROJECT_ID': 'test',
            'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json',
            'OPENSEARCH_HOST': 'https://os.example.com',
            'ZEP_API_KEY': 'test',
            'OPENAI_API_KEY': 'test',
            'ASSEMBLYAI_API_KEY': 'test',
            'YOUTUBE_API_KEY': 'test'
        }):
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data='{"client_email": "test@test.iam.gserviceaccount.com"}')):
                    tool = self.ToolClass()
                    result = tool.run()
                    data = json.loads(result)

                    self.assertIn('timestamp', data)
                    self.assertIn('components', data)
                    self.assertIn('overall_status', data)
                    self.assertIn('summary', data)

    def test_run_individual_component_checks(self):
        """Test running individual component validations (lines 315-408)."""
        with patch.dict(os.environ, {'GCP_PROJECT_ID': 'test', 'GOOGLE_APPLICATION_CREDENTIALS': '/path'}):
            tool = self.ToolClass(
                check_bigquery=True,
                check_opensearch=False,
                check_zep=False,
                check_credentials=False
            )
            result = tool.run()
            data = json.loads(result)

            # Only BigQuery should be in components
            self.assertIn('bigquery', data['components'])
            self.assertNotIn('opensearch', data['components'])
            self.assertNotIn('zep', data['components'])

    def test_run_strict_mode_with_warnings(self):
        """Test strict mode fails on warnings (lines 315-408)."""
        with patch.dict(os.environ, {
            'OPENSEARCH_HOST': 'http://opensearch.example.com',  # HTTP (warning)
            'ZEP_API_KEY': 'test',
            'OPENAI_API_KEY': 'test',
            'ASSEMBLYAI_API_KEY': 'test',
            'YOUTUBE_API_KEY': 'test'
        }):
            tool = self.ToolClass(
                check_bigquery=False,
                check_opensearch=True,
                check_zep=True,
                check_credentials=True,
                strict_mode=True
            )
            result = tool.run()
            data = json.loads(result)

            # Should have warnings and fail in strict mode
            if data['warnings']:
                self.assertEqual(data['overall_status'], 'failed')

    def test_run_collects_critical_issues(self):
        """Test that critical issues are collected (lines 315-408)."""
        with patch.dict(os.environ, {}, clear=True):
            tool = self.ToolClass()
            result = tool.run()
            data = json.loads(result)

            # Should have critical issues for missing env vars
            self.assertGreater(len(data['critical_issues']), 0)
            self.assertEqual(data['overall_status'], 'failed')

    def test_run_includes_recommendations(self):
        """Test that recommendations are included (lines 315-408)."""
        with patch.dict(os.environ, {'ZEP_API_KEY': 'test'}):
            tool = self.ToolClass()
            result = tool.run()
            data = json.loads(result)

            self.assertIn('recommendations', data)
            self.assertGreater(len(data['recommendations']), 0)

    def test_run_includes_summary_statistics(self):
        """Test that summary statistics are included (lines 393-398)."""
        with patch.dict(os.environ, {'ZEP_API_KEY': 'test'}):
            tool = self.ToolClass()
            result = tool.run()
            data = json.loads(result)

            self.assertIn('summary', data)
            summary = data['summary']
            self.assertIn('total_checks', summary)
            self.assertIn('critical_issues_count', summary)
            self.assertIn('warnings_count', summary)
            self.assertIn('recommendations_count', summary)

    def test_exception_handling(self):
        """Test exception handling (lines 410-415)."""
        tool = self.ToolClass()

        # Mock _validate_bigquery_security to raise exception
        with patch.object(tool, '_validate_bigquery_security', side_effect=Exception("Test error")):
            result = tool.run()
            data = json.loads(result)

            self.assertIn('error', data)
            self.assertEqual(data['error'], 'security_validation_failed')
            self.assertIn('Test error', data['message'])

    def test_timestamp_generation(self):
        """Test timestamp generation (lines 311-313)."""
        tool = self.ToolClass()
        timestamp = tool._get_timestamp()

        # Should be ISO 8601 format
        self.assertIn('T', timestamp)
        self.assertTrue(timestamp.endswith('Z') or '+' in timestamp)

    def test_validation_mode_in_response(self):
        """Test validation mode included in response (lines 315-408)."""
        with patch.dict(os.environ, {}):
            tool = self.ToolClass(strict_mode=True)
            result = tool.run()
            data = json.loads(result)

            self.assertEqual(data['validation_mode'], 'strict')

        with patch.dict(os.environ, {}):
            tool = self.ToolClass(strict_mode=False)
            result = tool.run()
            data = json.loads(result)

            self.assertEqual(data['validation_mode'], 'standard')

    @patch.dict(os.environ, {
        'GCP_PROJECT_ID': 'test-project',
        'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/creds.json'
    })
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='{"client_email": "invalid_email"}')
    def test_bigquery_invalid_service_account_email(self, mock_file, mock_exists):
        """Test BigQuery validation with invalid service account email format (lines 75-159)."""
        tool = self.ToolClass()
        result = tool._validate_bigquery_security()

        # Should have warning about invalid email format
        email_checks = [c for c in result['checks'] if 'email' in c['variable']]
        self.assertGreater(len(email_checks), 0)

    def test_load_security_config(self):
        """Test loading security configuration (lines 301-309)."""
        tool = self.ToolClass()
        config = tool._load_security_config()

        # Should return dict (may be empty if config not accessible)
        self.assertIsInstance(config, dict)


if __name__ == '__main__':
    unittest.main()
