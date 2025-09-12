"""
Integration tests for environment loader.
Tests environment variable loading and validation.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add config directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'config'))
from env_loader import (
    load_environment, validate_environment, get_required_env_var,
    get_optional_env_var, get_api_key, get_google_credentials_path,
    get_langfuse_config, EnvironmentError
)


class TestEnvironmentLoader(unittest.TestCase):
    """Test cases for the environment loader."""
    
    def setUp(self):
        """Set up test by clearing environment variables."""
        self.original_env = os.environ.copy()
        # Clear environment variables that might interfere with tests
        env_vars_to_clear = [
            'OPENAI_API_KEY', 'ASSEMBLYAI_API_KEY', 'YOUTUBE_API_KEY',
            'SLACK_BOT_TOKEN', 'GOOGLE_APPLICATION_CREDENTIALS',
            'GOOGLE_DRIVE_FOLDER_ID_TRANSCRIPTS', 'GOOGLE_DRIVE_FOLDER_ID_SUMMARIES',
            'ZEP_API_KEY', 'ZEP_COLLECTION', 'TIMEZONE'
        ]
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_get_required_env_var_success(self):
        """Test successful retrieval of required environment variable."""
        os.environ['TEST_VAR'] = 'test_value'
        result = get_required_env_var('TEST_VAR', 'Test variable')
        self.assertEqual(result, 'test_value')
    
    def test_get_required_env_var_missing(self):
        """Test error when required environment variable is missing."""
        with self.assertRaises(EnvironmentError) as cm:
            get_required_env_var('MISSING_VAR', 'Missing variable')
        self.assertIn('MISSING_VAR', str(cm.exception))
        self.assertIn('Missing variable', str(cm.exception))
    
    def test_get_required_env_var_empty(self):
        """Test error when required environment variable is empty."""
        os.environ['EMPTY_VAR'] = ''
        with self.assertRaises(EnvironmentError) as cm:
            get_required_env_var('EMPTY_VAR', 'Empty variable')
        self.assertIn('EMPTY_VAR', str(cm.exception))
    
    def test_get_optional_env_var_with_value(self):
        """Test optional environment variable with set value."""
        os.environ['OPTIONAL_VAR'] = 'optional_value'
        result = get_optional_env_var('OPTIONAL_VAR', 'default_value')
        self.assertEqual(result, 'optional_value')
    
    def test_get_optional_env_var_with_default(self):
        """Test optional environment variable using default value."""
        result = get_optional_env_var('MISSING_OPTIONAL', 'default_value')
        self.assertEqual(result, 'default_value')
    
    def test_get_api_key_success(self):
        """Test successful API key retrieval."""
        os.environ['OPENAI_API_KEY'] = 'test_openai_key'
        result = get_api_key('openai')
        self.assertEqual(result, 'test_openai_key')
    
    def test_get_api_key_unknown_service(self):
        """Test error for unknown service."""
        with self.assertRaises(EnvironmentError) as cm:
            get_api_key('unknown_service')
        self.assertIn('Unknown service', str(cm.exception))
    
    def test_get_api_key_missing(self):
        """Test error when API key is missing."""
        with self.assertRaises(EnvironmentError) as cm:
            get_api_key('openai')
        self.assertIn('OPENAI_API_KEY', str(cm.exception))
    
    def test_get_langfuse_config_complete(self):
        """Test Langfuse configuration with all values set."""
        os.environ['LANGFUSE_PUBLIC_KEY'] = 'test_public'
        os.environ['LANGFUSE_SECRET_KEY'] = 'test_secret'
        os.environ['LANGFUSE_HOST'] = 'https://test.langfuse.com'
        
        config = get_langfuse_config()
        
        self.assertEqual(config['public_key'], 'test_public')
        self.assertEqual(config['secret_key'], 'test_secret')
        self.assertEqual(config['host'], 'https://test.langfuse.com')
    
    def test_get_langfuse_config_partial(self):
        """Test Langfuse configuration with default values."""
        config = get_langfuse_config()
        
        self.assertEqual(config['public_key'], '')
        self.assertEqual(config['secret_key'], '')
        self.assertEqual(config['host'], 'https://cloud.langfuse.com')
    
    def test_validate_environment_missing_required(self):
        """Test validation failure when required variables are missing."""
        with self.assertRaises(EnvironmentError) as cm:
            validate_environment()
        
        error_msg = str(cm.exception)
        self.assertIn('Missing required environment variables', error_msg)
        self.assertIn('OPENAI_API_KEY', error_msg)
        self.assertIn('env.template', error_msg)
    
    def test_validate_environment_success(self):
        """Test successful environment validation."""
        # Set all required environment variables
        required_vars = {
            'OPENAI_API_KEY': 'test_openai_key',
            'ASSEMBLYAI_API_KEY': 'test_assemblyai_key',
            'YOUTUBE_API_KEY': 'test_youtube_key',
            'SLACK_BOT_TOKEN': 'test_slack_token',
            'GOOGLE_APPLICATION_CREDENTIALS': '/tmp/test_creds.json',
            'GOOGLE_DRIVE_FOLDER_ID_TRANSCRIPTS': 'test_transcript_folder',
            'GOOGLE_DRIVE_FOLDER_ID_SUMMARIES': 'test_summary_folder',
            'ZEP_API_KEY': 'test_zep_key',
        }
        
        for var, value in required_vars.items():
            os.environ[var] = value
        
        env_values = validate_environment()
        
        # Check that all required variables are present
        for var in required_vars:
            self.assertIn(var, env_values)
            self.assertEqual(env_values[var], required_vars[var])
        
        # Check optional variables get defaults
        self.assertEqual(env_values['ZEP_COLLECTION'], 'autopiloot_guidelines')
        self.assertEqual(env_values['TIMEZONE'], 'Europe/Amsterdam')
    
    def test_get_google_credentials_path_missing_env(self):
        """Test error when Google credentials environment variable is missing."""
        with self.assertRaises(EnvironmentError) as cm:
            get_google_credentials_path()
        self.assertIn('GOOGLE_APPLICATION_CREDENTIALS', str(cm.exception))
    
    def test_get_google_credentials_path_file_not_found(self):
        """Test error when Google credentials file doesn't exist."""
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/nonexistent/path.json'
        with self.assertRaises(EnvironmentError) as cm:
            get_google_credentials_path()
        self.assertIn('Google credentials file not found', str(cm.exception))
    
    def test_get_google_credentials_path_success(self):
        """Test successful Google credentials path retrieval."""
        # Create a temporary file to simulate credentials
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"type": "service_account"}')
            temp_path = f.name
        
        try:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_path
            result = get_google_credentials_path()
            self.assertEqual(result, temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_load_environment_missing_file(self):
        """Test load_environment with missing .env file."""
        # This should not raise an error, just print a warning
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_env = os.path.join(temp_dir, 'nonexistent.env')
            load_environment(non_existent_env)  # Should not raise exception
    
    def test_load_environment_with_file(self):
        """Test load_environment with existing .env file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('TEST_ENV_VAR=test_value\n')
            f.write('ANOTHER_VAR=another_value\n')
            temp_path = f.name
        
        try:
            load_environment(temp_path)
            # Check that variables were loaded
            self.assertEqual(os.environ.get('TEST_ENV_VAR'), 'test_value')
            self.assertEqual(os.environ.get('ANOTHER_VAR'), 'another_value')
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
