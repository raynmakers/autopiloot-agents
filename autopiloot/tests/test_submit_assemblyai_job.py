"""
Unit tests for SubmitAssemblyAIJob tool
Tests TASK-TRN-0021 implementation
"""

import unittest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Mock agency_swarm for testing
import sys
import importlib.util

# Import the tool module directly
tool_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'transcriber_agent', 'tools', 'submit_assemblyai_job.py'
)
spec = importlib.util.spec_from_file_location("submit_assemblyai_job", tool_path)
submit_job_module = importlib.util.module_from_spec(spec)

# Mock dependencies before loading the module
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'assemblyai': MagicMock(),
    'assemblyai.exceptions': MagicMock()
}):
    spec.loader.exec_module(submit_job_module)
    SubmitAssemblyAIJob = submit_job_module.SubmitAssemblyAIJob
    ASSEMBLYAI_COST_PER_HOUR = submit_job_module.ASSEMBLYAI_COST_PER_HOUR


class TestSubmitAssemblyAIJob(unittest.TestCase):
    """Test cases for SubmitAssemblyAIJob tool."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_remote_url = "https://example.com/audio.mp3"
        self.test_video_id = "test_video_123"
        self.test_duration = 600  # 10 minutes
        
        # Set up environment variables
        os.environ["ASSEMBLYAI_API_KEY"] = "test_api_key"
        os.environ["ASSEMBLYAI_WEBHOOK_SECRET"] = "test_webhook_secret"
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove test environment variables
        if "ASSEMBLYAI_API_KEY" in os.environ:
            del os.environ["ASSEMBLYAI_API_KEY"]
        if "ASSEMBLYAI_WEBHOOK_SECRET" in os.environ:
            del os.environ["ASSEMBLYAI_WEBHOOK_SECRET"]
    
    def test_duration_validation_success(self):
        """Test successful duration validation within 70-minute limit."""
        # Should not raise error for valid duration
        tool = SubmitAssemblyAIJob(
            remote_url=self.test_remote_url,
            video_id=self.test_video_id,
            duration_sec=4200  # Exactly 70 minutes
        )
        self.assertEqual(tool.duration_sec, 4200)
    
    def test_duration_validation_exceeds_limit(self):
        """Test duration validation fails for videos over 70 minutes."""
        with self.assertRaises(ValueError) as context:
            SubmitAssemblyAIJob(
                remote_url=self.test_remote_url,
                video_id=self.test_video_id,
                duration_sec=4201  # 70 minutes + 1 second
            )
        self.assertIn("exceeds maximum 4200s", str(context.exception))
    
    def test_duration_validation_negative(self):
        """Test duration validation fails for negative duration."""
        with self.assertRaises(ValueError) as context:
            SubmitAssemblyAIJob(
                remote_url=self.test_remote_url,
                video_id=self.test_video_id,
                duration_sec=-1
            )
        self.assertIn("Duration must be positive", str(context.exception))
    
    def test_webhook_url_validation_valid(self):
        """Test webhook URL validation accepts valid URLs."""
        # HTTPS URL
        tool1 = SubmitAssemblyAIJob(
            remote_url=self.test_remote_url,
            video_id=self.test_video_id,
            duration_sec=self.test_duration,
            webhook_url="https://example.com/webhook"
        )
        self.assertEqual(tool1.webhook_url, "https://example.com/webhook")
        
        # HTTP URL
        tool2 = SubmitAssemblyAIJob(
            remote_url=self.test_remote_url,
            video_id=self.test_video_id,
            duration_sec=self.test_duration,
            webhook_url="http://localhost:8080/webhook"
        )
        self.assertEqual(tool2.webhook_url, "http://localhost:8080/webhook")
    
    def test_webhook_url_validation_invalid(self):
        """Test webhook URL validation rejects invalid URLs."""
        with self.assertRaises(ValueError) as context:
            SubmitAssemblyAIJob(
                remote_url=self.test_remote_url,
                video_id=self.test_video_id,
                duration_sec=self.test_duration,
                webhook_url="invalid-url"
            )
        self.assertIn("Must start with http://", str(context.exception))
    
    @patch('submit_assemblyai_job.aai')
    def test_successful_job_submission(self, mock_aai):
        """Test successful job submission to AssemblyAI."""
        # Mock transcript response
        mock_transcript = Mock()
        mock_transcript.id = "job_12345"
        
        mock_transcriber = Mock()
        mock_transcriber.submit.return_value = mock_transcript
        mock_aai.Transcriber.return_value = mock_transcriber
        
        tool = SubmitAssemblyAIJob(
            remote_url=self.test_remote_url,
            video_id=self.test_video_id,
            duration_sec=self.test_duration
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Verify response structure
        self.assertEqual(data["job_id"], "job_12345")
        self.assertEqual(data["video_id"], self.test_video_id)
        self.assertEqual(data["duration_sec"], self.test_duration)
        self.assertIn("estimated_cost_usd", data)
        self.assertFalse(data["webhook_enabled"])
        self.assertEqual(data["status"], "submitted")
    
    @patch('submit_assemblyai_job.aai')
    def test_job_submission_with_webhook(self, mock_aai):
        """Test job submission with webhook configuration."""
        mock_transcript = Mock()
        mock_transcript.id = "job_webhook_123"
        
        mock_transcriber = Mock()
        mock_transcriber.submit.return_value = mock_transcript
        mock_aai.Transcriber.return_value = mock_transcriber
        
        webhook_url = "https://example.com/webhook/callback"
        tool = SubmitAssemblyAIJob(
            remote_url=self.test_remote_url,
            video_id=self.test_video_id,
            duration_sec=self.test_duration,
            webhook_url=webhook_url
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Verify webhook configuration in response
        self.assertTrue(data["webhook_enabled"])
        self.assertEqual(data["webhook_url"], webhook_url)
        
        # Verify TranscriptionConfig was called with webhook params
        config_call = mock_aai.TranscriptionConfig.call_args
        self.assertIsNotNone(config_call)
        kwargs = config_call[1] if len(config_call) > 1 else config_call[0]
        self.assertEqual(kwargs.get("webhook_url"), webhook_url)
        self.assertEqual(kwargs.get("webhook_auth_header_name"), "X-AssemblyAI-Webhook-Secret")
        self.assertEqual(kwargs.get("webhook_auth_header_value"), "test_webhook_secret")
    
    def test_cost_estimation_basic(self):
        """Test cost estimation for basic transcription."""
        tool = SubmitAssemblyAIJob(
            remote_url=self.test_remote_url,
            video_id=self.test_video_id,
            duration_sec=3600  # 1 hour
        )
        
        # Calculate expected cost
        expected_cost = ASSEMBLYAI_COST_PER_HOUR  # $0.65 per hour
        
        with patch('submit_assemblyai_job.aai') as mock_aai:
            mock_transcript = Mock()
            mock_transcript.id = "job_cost_test"
            mock_aai.Transcriber.return_value.submit.return_value = mock_transcript
            
            result = tool.run()
            data = json.loads(result)
            
            self.assertEqual(data["estimated_cost_usd"], expected_cost)
    
    def test_cost_estimation_with_speaker_labels(self):
        """Test cost estimation with speaker labels enabled."""
        tool = SubmitAssemblyAIJob(
            remote_url=self.test_remote_url,
            video_id=self.test_video_id,
            duration_sec=3600,  # 1 hour
            enable_speaker_labels=True
        )
        
        # Calculate expected cost with 15% markup for speaker labels
        expected_cost = round(ASSEMBLYAI_COST_PER_HOUR * 1.15, 4)
        
        with patch('submit_assemblyai_job.aai') as mock_aai:
            mock_transcript = Mock()
            mock_transcript.id = "job_speaker_test"
            mock_aai.Transcriber.return_value.submit.return_value = mock_transcript
            
            result = tool.run()
            data = json.loads(result)
            
            self.assertEqual(data["estimated_cost_usd"], expected_cost)
            self.assertTrue(data["features"]["speaker_labels"])
    
    def test_missing_api_key(self):
        """Test handling of missing API key."""
        # Remove API key
        del os.environ["ASSEMBLYAI_API_KEY"]
        
        tool = SubmitAssemblyAIJob(
            remote_url=self.test_remote_url,
            video_id=self.test_video_id,
            duration_sec=self.test_duration
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "configuration_error")
        self.assertIn("ASSEMBLYAI_API_KEY", data["message"])
    
    @patch('submit_assemblyai_job.aai')
    def test_authentication_error(self, mock_aai):
        """Test handling of authentication errors."""
        # Create mock exception
        mock_auth_error = type('AuthenticationError', (Exception,), {})
        mock_aai.exceptions.AuthenticationError = mock_auth_error
        
        # Configure mock to raise authentication error
        mock_aai.Transcriber.return_value.submit.side_effect = mock_auth_error("Invalid API key")
        
        tool = SubmitAssemblyAIJob(
            remote_url=self.test_remote_url,
            video_id=self.test_video_id,
            duration_sec=self.test_duration
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "authentication_error")
        self.assertIn("Invalid AssemblyAI API key", data["message"])
    
    @patch('submit_assemblyai_job.aai')
    def test_transcript_error(self, mock_aai):
        """Test handling of transcript submission errors."""
        # Create mock exception
        mock_transcript_error = type('TranscriptError', (Exception,), {})
        mock_aai.exceptions.TranscriptError = mock_transcript_error
        
        # Configure mock to raise transcript error
        mock_aai.Transcriber.return_value.submit.side_effect = mock_transcript_error("Submission failed")
        
        tool = SubmitAssemblyAIJob(
            remote_url=self.test_remote_url,
            video_id=self.test_video_id,
            duration_sec=self.test_duration
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "transcript_error")
        self.assertIn("Failed to submit transcription job", data["message"])
    
    @patch('submit_assemblyai_job.aai')
    def test_language_code_configuration(self, mock_aai):
        """Test language code is properly configured."""
        mock_transcript = Mock()
        mock_transcript.id = "job_lang_test"
        mock_aai.Transcriber.return_value.submit.return_value = mock_transcript
        
        tool = SubmitAssemblyAIJob(
            remote_url=self.test_remote_url,
            video_id=self.test_video_id,
            duration_sec=self.test_duration,
            language_code="es"  # Spanish
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Verify language code in response
        self.assertEqual(data["features"]["language_code"], "es")
        
        # Verify TranscriptionConfig was called with language_code
        config_call = mock_aai.TranscriptionConfig.call_args
        kwargs = config_call[1] if len(config_call) > 1 else config_call[0]
        self.assertEqual(kwargs.get("language_code"), "es")
    
    def test_json_string_return_format(self):
        """Test that tool returns valid JSON string per Agency Swarm v1.0.0."""
        with patch('submit_assemblyai_job.aai') as mock_aai:
            mock_transcript = Mock()
            mock_transcript.id = "job_format_test"
            mock_aai.Transcriber.return_value.submit.return_value = mock_transcript
            
            tool = SubmitAssemblyAIJob(
                remote_url=self.test_remote_url,
                video_id=self.test_video_id,
                duration_sec=self.test_duration
            )
            
            result = tool.run()
            
            # Should return string, not dict
            self.assertIsInstance(result, str)
            
            # Should be valid JSON
            try:
                data = json.loads(result)
                self.assertIsInstance(data, dict)
                self.assertIn("job_id", data)
                self.assertIn("estimated_cost_usd", data)
            except json.JSONDecodeError:
                self.fail("Tool did not return valid JSON string")


if __name__ == '__main__':
    unittest.main()