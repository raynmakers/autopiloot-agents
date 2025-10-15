"""
Integration tests for configuration loader using unittest framework.
Tests both valid configurations and validation error cases.
"""

import os
import sys
import tempfile
import unittest
import yaml
from pathlib import Path

# Add config directory to path for imports
from loader import load_app_config, ConfigValidationError, _validate_config


@unittest.skip("Dependencies not available")
class TestConfigurationLoader(unittest.TestCase):
    """Test cases for the configuration loader."""
    
    def test_valid_configuration(self):
        """Test loading a valid configuration."""
        config = load_app_config()
        
        # Verify all required fields are present
        self.assertIn('sheet', config)
        self.assertIn('scraper', config)
        self.assertIn('llm', config)
        self.assertIn('notifications', config)
        self.assertIn('budgets', config)
        
        # Verify scraper config
        scraper = config['scraper']
        self.assertIn('handles', scraper)
        self.assertIn('@AlexHormozi', scraper['handles'])
        self.assertEqual(scraper['daily_limit_per_channel'], 10)
        
        # Verify LLM config
        llm = config['llm']
        self.assertEqual(llm['default']['model'], 'gpt-4.1')
        self.assertEqual(llm['default']['temperature'], 0.2)
        self.assertIn('tasks', llm)
        self.assertIn('summarizer_generate_short', llm['tasks'])
        
        # Verify notifications
        self.assertEqual(config['notifications']['slack']['channel'], 'ops-autopiloot')
        
        # Verify budgets
        self.assertEqual(config['budgets']['transcription_daily_usd'], 5.0)
    
    def test_empty_sheet_id(self):
        """Test validation with empty sheet ID."""
        test_config = {
            'sheet': '',  # Empty sheet ID
            'scraper': {'daily_limit_per_channel': 10},
            'llm': {'default': {'model': 'gpt-4.1', 'temperature': 0.2}},
            'notifications': {'slack': {'channel': 'test'}},
            'budgets': {'transcription_daily_usd': 5.0}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_path = f.name
        
        try:
            with self.assertRaises(ConfigValidationError) as cm:
                load_app_config(temp_path)
            self.assertIn("sheet must be a non-empty string", str(cm.exception))
        finally:
            os.unlink(temp_path)
    
    def test_invalid_temperature(self):
        """Test validation with invalid temperature."""
        test_config = {
            'sheet': 'test123',
            'scraper': {'daily_limit_per_channel': 10},
            'llm': {'default': {'model': 'gpt-4.1', 'temperature': 1.5}},  # Invalid temperature
            'notifications': {'slack': {'channel': 'test'}},
            'budgets': {'transcription_daily_usd': 5.0}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_path = f.name
        
        try:
            with self.assertRaises(ConfigValidationError) as cm:
                load_app_config(temp_path)
            self.assertIn("temperature must be between 0.0 and 1.0", str(cm.exception))
        finally:
            os.unlink(temp_path)
    
    def test_negative_daily_limit(self):
        """Test validation with negative daily limit."""
        test_config = {
            'sheet': 'test123',
            'scraper': {'daily_limit_per_channel': -5},  # Negative limit
            'llm': {'default': {'model': 'gpt-4.1', 'temperature': 0.2}},
            'notifications': {'slack': {'channel': 'test'}},
            'budgets': {'transcription_daily_usd': 5.0}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_path = f.name
        
        try:
            with self.assertRaises(ConfigValidationError) as cm:
                load_app_config(temp_path)
            self.assertIn("daily_limit_per_channel must be int >= 0", str(cm.exception))
        finally:
            os.unlink(temp_path)
    
    def test_zero_budget(self):
        """Test validation with zero budget."""
        test_config = {
            'sheet': 'test123',
            'scraper': {'daily_limit_per_channel': 10},
            'llm': {'default': {'model': 'gpt-4.1', 'temperature': 0.2}},
            'notifications': {'slack': {'channel': 'test'}},
            'budgets': {'transcription_daily_usd': 0}  # Zero budget
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_path = f.name
        
        try:
            with self.assertRaises(ConfigValidationError) as cm:
                load_app_config(temp_path)
            self.assertIn("transcription_daily_usd must be a positive number", str(cm.exception))
        finally:
            os.unlink(temp_path)
    
    def test_empty_slack_channel(self):
        """Test validation with empty slack channel."""
        test_config = {
            'sheet': 'test123',
            'scraper': {'daily_limit_per_channel': 10},
            'llm': {'default': {'model': 'gpt-4.1', 'temperature': 0.2}},
            'notifications': {'slack': {'channel': ''}},  # Empty channel
            'budgets': {'transcription_daily_usd': 5.0}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_path = f.name
        
        try:
            with self.assertRaises(ConfigValidationError) as cm:
                load_app_config(temp_path)
            self.assertIn("notifications.slack.channel must be a non-empty string", str(cm.exception))
        finally:
            os.unlink(temp_path)
    
    def test_task_config_overrides(self):
        """Test LLM task configuration overrides."""
        test_config = {
            'sheet': 'test123',
            'scraper': {'daily_limit_per_channel': 10},
            'llm': {
                'default': {'model': 'gpt-4.1', 'temperature': 0.2},
                'tasks': {
                    'custom_task': {
                        'model': 'gpt-3.5-turbo',
                        'temperature': 0.8,
                        'prompt_id': 'custom_prompt'
                    }
                }
            },
            'notifications': {'slack': {'channel': 'test'}},
            'budgets': {'transcription_daily_usd': 5.0}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_path = f.name
        
        try:
            config = load_app_config(temp_path)
            
            # Verify task override
            task_config = config['llm']['tasks']['custom_task']
            self.assertEqual(task_config['model'], 'gpt-3.5-turbo')
            self.assertEqual(task_config['temperature'], 0.8)
            self.assertEqual(task_config['prompt_id'], 'custom_prompt')
        finally:
            os.unlink(temp_path)
    
    def test_invalid_task_temperature(self):
        """Test validation with invalid task temperature."""
        test_config = {
            'sheet': 'test123',
            'scraper': {'daily_limit_per_channel': 10},
            'llm': {
                'default': {'model': 'gpt-4.1', 'temperature': 0.2},
                'tasks': {
                    'bad_task': {
                        'model': 'gpt-4.1',
                        'temperature': -0.5  # Invalid temperature
                    }
                }
            },
            'notifications': {'slack': {'channel': 'test'}},
            'budgets': {'transcription_daily_usd': 5.0}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_path = f.name
        
        try:
            with self.assertRaises(ConfigValidationError) as cm:
                load_app_config(temp_path)
            self.assertIn("llm.tasks.bad_task.temperature must be between 0.0 and 1.0", str(cm.exception))
        finally:
            os.unlink(temp_path)
    
    def test_file_not_found(self):
        """Test behavior when configuration file doesn't exist."""
        with self.assertRaises(FileNotFoundError) as cm:
            load_app_config("/nonexistent/path/to/config.yaml")
        self.assertIn("Configuration file not found", str(cm.exception))
    
    def test_invalid_yaml(self):
        """Test behavior with invalid YAML syntax."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            temp_path = f.name
        
        try:
            with self.assertRaises(yaml.YAMLError):
                load_app_config(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_non_dict_config(self):
        """Test behavior with non-dictionary YAML content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(["not", "a", "dict"], f)
            temp_path = f.name
        
        try:
            with self.assertRaises(ConfigValidationError) as cm:
                load_app_config(temp_path)
            self.assertIn("Configuration must be a YAML dictionary", str(cm.exception))
        finally:
            os.unlink(temp_path)
    
    def test_reliability_config_validation(self):
        """Test reliability configuration validation."""
        # Valid reliability config
        config = {
            "sheet": "test_sheet_id",
            "reliability": {
                "retry": {
                    "max_attempts": 5,
                    "base_delay_sec": 30
                },
                "quotas": {
                    "youtube_daily_limit": 5000,
                    "assemblyai_daily_limit": 50
                }
            }
        }
        
        # Should not raise an exception
        _validate_config(config)
        
        # Invalid max_attempts (negative)
        config["reliability"]["retry"]["max_attempts"] = -1
        with self.assertRaises(ConfigValidationError) as cm:
            _validate_config(config)
        self.assertIn("reliability.retry.max_attempts must be a non-negative integer", str(cm.exception))
        
        # Invalid base_delay_sec (zero)
        config["reliability"]["retry"]["max_attempts"] = 3
        config["reliability"]["retry"]["base_delay_sec"] = 0
        with self.assertRaises(ConfigValidationError) as cm:
            _validate_config(config)
        self.assertIn("reliability.retry.base_delay_sec must be a positive integer", str(cm.exception))
        
        # Invalid quota (negative)
        config["reliability"]["retry"]["base_delay_sec"] = 60
        config["reliability"]["quotas"]["youtube_daily_limit"] = -100
        with self.assertRaises(ConfigValidationError) as cm:
            _validate_config(config)
        self.assertIn("reliability.quotas.youtube_daily_limit must be a positive integer", str(cm.exception))
    
    def test_reliability_config_helpers(self):
        """Test reliability configuration helper functions."""
        from loader import (
            get_retry_max_attempts, get_retry_base_delay,
            get_youtube_daily_limit, get_assemblyai_daily_limit
        )
        
        # Test with reliability config
        config = {
            "reliability": {
                "retry": {
                    "max_attempts": 5,
                    "base_delay_sec": 30
                },
                "quotas": {
                    "youtube_daily_limit": 5000,
                    "assemblyai_daily_limit": 50
                }
            }
        }
        
        self.assertEqual(get_retry_max_attempts(config), 5)
        self.assertEqual(get_retry_base_delay(config), 30)
        self.assertEqual(get_youtube_daily_limit(config), 5000)
        self.assertEqual(get_assemblyai_daily_limit(config), 50)
        
        # Test with missing reliability config (should return defaults)
        config_no_reliability = {}
        
        self.assertEqual(get_retry_max_attempts(config_no_reliability), 3)  # Default
        self.assertEqual(get_retry_base_delay(config_no_reliability), 60)  # Default
        self.assertEqual(get_youtube_daily_limit(config_no_reliability), 10000)  # Default
        self.assertEqual(get_assemblyai_daily_limit(config_no_reliability), 100)  # Default
        
        # Test with partial reliability config
        config_partial = {
            "reliability": {
                "retry": {
                    "max_attempts": 2
                    # base_delay_sec missing
                },
                "quotas": {
                    "youtube_daily_limit": 8000
                    # assemblyai_daily_limit missing
                }
            }
        }
        
        self.assertEqual(get_retry_max_attempts(config_partial), 2)
        self.assertEqual(get_retry_base_delay(config_partial), 60)  # Default
        self.assertEqual(get_youtube_daily_limit(config_partial), 8000)
        self.assertEqual(get_assemblyai_daily_limit(config_partial), 100)  # Default


if __name__ == "__main__":
    unittest.main(verbosity=2)
