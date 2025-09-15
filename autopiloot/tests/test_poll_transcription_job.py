"""
Unit tests for PollTranscriptionJob tool
Tests TASK-TRN-0022 polling implementation with exponential backoff
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
    'transcriber_agent', 'tools', 'poll_transcription_job.py'
)
spec = importlib.util.spec_from_file_location("poll_transcription_job", tool_path)
poll_job_module = importlib.util.module_from_spec(spec)

# Mock dependencies before loading the module
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'assemblyai': MagicMock(),
    'assemblyai.exceptions': MagicMock(),
    'dotenv': MagicMock()
}):
    spec.loader.exec_module(poll_job_module)
    PollTranscriptionJob = poll_job_module.PollTranscriptionJob


class TestPollTranscriptionJob(unittest.TestCase):
    """Test cases for PollTranscriptionJob tool."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_job_id = "test_job_12345"
        
        # Set up environment variables
        os.environ["ASSEMBLYAI_API_KEY"] = "test_api_key"
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove test environment variables
        if "ASSEMBLYAI_API_KEY" in os.environ:
            del os.environ["ASSEMBLYAI_API_KEY"]
    
    def test_parameter_validation_success(self):
        """Test successful parameter validation with valid inputs."""
        # Should not raise error for valid parameters
        tool = PollTranscriptionJob(
            job_id=self.test_job_id,
            max_attempts=5,
            base_delay_sec=30,
            timeout_sec=1800
        )
        self.assertEqual(tool.job_id, self.test_job_id)
        self.assertEqual(tool.max_attempts, 5)
        self.assertEqual(tool.base_delay_sec, 30)
        self.assertEqual(tool.timeout_sec, 1800)
    
    def test_parameter_validation_max_attempts_too_low(self):
        """Test max_attempts validation fails for values below 1."""
        with self.assertRaises(ValueError) as context:
            PollTranscriptionJob(
                job_id=self.test_job_id,
                max_attempts=0  # Below minimum
            )
        self.assertIn("must be at least 1", str(context.exception))
    
    def test_parameter_validation_max_attempts_too_high(self):
        """Test max_attempts validation fails for values above 10."""
        with self.assertRaises(ValueError) as context:
            PollTranscriptionJob(
                job_id=self.test_job_id,
                max_attempts=15  # Above maximum
            )
        self.assertIn("cannot exceed 10", str(context.exception))
    
    def test_parameter_validation_base_delay_too_low(self):
        """Test base_delay_sec validation fails for values below 10."""
        with self.assertRaises(ValueError) as context:
            PollTranscriptionJob(
                job_id=self.test_job_id,
                base_delay_sec=5  # Below minimum
            )
        self.assertIn("must be at least 10", str(context.exception))
    
    def test_parameter_validation_base_delay_too_high(self):
        """Test base_delay_sec validation fails for values above 300."""
        with self.assertRaises(ValueError) as context:
            PollTranscriptionJob(
                job_id=self.test_job_id,
                base_delay_sec=400  # Above maximum
            )
        self.assertIn("cannot exceed 300", str(context.exception))
    
    def test_parameter_validation_timeout_too_low(self):
        """Test timeout_sec validation fails for values below 300."""
        with self.assertRaises(ValueError) as context:
            PollTranscriptionJob(
                job_id=self.test_job_id,
                timeout_sec=100  # Below minimum
            )
        self.assertIn("must be at least 300", str(context.exception))
    
    def test_parameter_validation_timeout_too_high(self):
        """Test timeout_sec validation fails for values above 7200."""
        with self.assertRaises(ValueError) as context:
            PollTranscriptionJob(
                job_id=self.test_job_id,
                timeout_sec=8000  # Above maximum
            )
        self.assertIn("cannot exceed 7200", str(context.exception))
    
    @patch('poll_transcription_job.aai')
    def test_successful_polling_completion(self, mock_aai):
        """Test successful polling when transcript completes."""
        # Mock completed transcript response
        mock_transcript = Mock()
        mock_transcript.status = mock_aai.TranscriptStatus.completed
        mock_transcript.id = self.test_job_id
        mock_transcript.text = "This is a test transcript with multiple sentences."
        mock_transcript.confidence = 0.95
        mock_transcript.audio_duration = 300
        mock_transcript.language_code = "en"
        mock_transcript.audio_url = "https://example.com/audio.mp3"
        mock_transcript.words = [
            Mock(text="This", start=0, end=400, confidence=0.96),
            Mock(text="is", start=500, end=700, confidence=0.98)
        ]
        
        mock_transcriber = Mock()
        mock_transcriber.get_transcript.return_value = mock_transcript
        mock_aai.Transcriber.return_value = mock_transcriber
        mock_aai.TranscriptStatus.completed = "completed"
        
        tool = PollTranscriptionJob(
            job_id=self.test_job_id,
            max_attempts=3,
            base_delay_sec=10,
            timeout_sec=300
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Verify successful completion
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["job_id"], self.test_job_id)
        self.assertEqual(data["polling_attempts"], 1)
        self.assertIn("transcript_text", data)
        self.assertIn("transcript_json", data)
        self.assertEqual(data["transcript_text"], "This is a test transcript with multiple sentences.")
    
    @patch('poll_transcription_job.aai')
    def test_polling_transcription_error(self, mock_aai):
        """Test polling when transcription fails."""
        # Mock error transcript response
        mock_transcript = Mock()
        mock_transcript.status = mock_aai.TranscriptStatus.error
        mock_transcript.error = "Audio file format not supported"
        
        mock_transcriber = Mock()
        mock_transcriber.get_transcript.return_value = mock_transcript
        mock_aai.Transcriber.return_value = mock_transcriber
        mock_aai.TranscriptStatus.error = "error"
        
        tool = PollTranscriptionJob(
            job_id=self.test_job_id,
            max_attempts=3,
            base_delay_sec=10,
            timeout_sec=300
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Verify error handling
        self.assertEqual(data["error"], "transcription_error")
        self.assertIn("AssemblyAI transcription failed", data["message"])
        self.assertEqual(data["job_id"], self.test_job_id)
        self.assertEqual(data["polling_attempts"], 1)
    
    @patch('poll_transcription_job.time.sleep')
    @patch('poll_transcription_job.aai')
    def test_polling_with_exponential_backoff(self, mock_aai, mock_sleep):
        """Test polling uses exponential backoff for processing status."""
        # Mock processing transcript that eventually completes
        mock_transcript_processing = Mock()
        mock_transcript_processing.status = mock_aai.TranscriptStatus.processing
        
        mock_transcript_completed = Mock()
        mock_transcript_completed.status = mock_aai.TranscriptStatus.completed
        mock_transcript_completed.id = self.test_job_id
        mock_transcript_completed.text = "Completed transcript"
        
        mock_transcriber = Mock()
        # First call returns processing, second call returns completed
        mock_transcriber.get_transcript.side_effect = [
            mock_transcript_processing,
            mock_transcript_completed
        ]
        mock_aai.Transcriber.return_value = mock_transcriber
        mock_aai.TranscriptStatus.processing = "processing"
        mock_aai.TranscriptStatus.completed = "completed"
        
        tool = PollTranscriptionJob(
            job_id=self.test_job_id,
            max_attempts=3,
            base_delay_sec=20,
            timeout_sec=300
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Verify completion and backoff was used
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["polling_attempts"], 2)
        
        # Verify sleep was called with exponential backoff
        # First attempt: 20 * (2^0) = 20 seconds
        mock_sleep.assert_called_once_with(20)
    
    @patch('poll_transcription_job.time.sleep')
    @patch('poll_transcription_job.aai')
    def test_polling_max_attempts_exceeded(self, mock_aai, mock_sleep):
        """Test polling stops after max_attempts with processing status."""
        # Mock transcript that stays in processing
        mock_transcript = Mock()
        mock_transcript.status = mock_aai.TranscriptStatus.processing
        
        mock_transcriber = Mock()
        mock_transcriber.get_transcript.return_value = mock_transcript
        mock_aai.Transcriber.return_value = mock_transcriber
        mock_aai.TranscriptStatus.processing = "processing"
        
        tool = PollTranscriptionJob(
            job_id=self.test_job_id,
            max_attempts=2,  # Low number for quick test
            base_delay_sec=10,
            timeout_sec=300
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Verify max attempts error
        self.assertEqual(data["error"], "max_attempts_exceeded")
        self.assertIn("not completed after 2 polling attempts", data["message"])
        self.assertEqual(data["polling_attempts"], 2)
        self.assertEqual(data["last_status"], "processing")
    
    @patch('poll_transcription_job.time.time')
    @patch('poll_transcription_job.aai')
    def test_polling_timeout_exceeded(self, mock_aai, mock_time):
        """Test polling stops when timeout is exceeded."""
        # Mock time progression
        mock_time.side_effect = [0, 400]  # Start at 0, then jump to 400 seconds
        
        # Mock processing transcript
        mock_transcript = Mock()
        mock_transcript.status = mock_aai.TranscriptStatus.processing
        
        mock_transcriber = Mock()
        mock_transcriber.get_transcript.return_value = mock_transcript
        mock_aai.Transcriber.return_value = mock_transcriber
        mock_aai.TranscriptStatus.processing = "processing"
        
        tool = PollTranscriptionJob(
            job_id=self.test_job_id,
            max_attempts=5,
            base_delay_sec=10,
            timeout_sec=300  # 5 minutes timeout
        )
        
        result = tool.run()
        data = json.loads(result)
        
        # Verify timeout error
        self.assertEqual(data["error"], "timeout_error")
        self.assertIn("Polling timeout exceeded 300 seconds", data["message"])
        self.assertEqual(data["elapsed_sec"], 400)
    
    def test_missing_api_key(self):
        """Test handling of missing API key."""
        # Remove API key
        del os.environ["ASSEMBLYAI_API_KEY"]
        
        tool = PollTranscriptionJob(
            job_id=self.test_job_id,
            max_attempts=3,
            base_delay_sec=10,
            timeout_sec=300
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "configuration_error")
        self.assertIn("ASSEMBLYAI_API_KEY", data["message"])
    
    @patch('poll_transcription_job.aai')
    def test_authentication_error(self, mock_aai):
        """Test handling of authentication errors."""
        # Create mock exception
        mock_auth_error = type('AuthenticationError', (Exception,), {})
        mock_aai.exceptions.AuthenticationError = mock_auth_error
        
        # Configure mock to raise authentication error
        mock_aai.Transcriber.return_value.get_transcript.side_effect = mock_auth_error("Invalid API key")
        
        tool = PollTranscriptionJob(
            job_id=self.test_job_id,
            max_attempts=3,
            base_delay_sec=10,
            timeout_sec=300
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "authentication_error")
        self.assertIn("Invalid AssemblyAI API key", data["message"])
        self.assertEqual(data["job_id"], self.test_job_id)
    
    @patch('poll_transcription_job.aai')
    def test_transcript_error(self, mock_aai):
        """Test handling of transcript retrieval errors."""
        # Create mock exception
        mock_transcript_error = type('TranscriptError', (Exception,), {})
        mock_aai.exceptions.TranscriptError = mock_transcript_error
        
        # Configure mock to raise transcript error
        mock_aai.Transcriber.return_value.get_transcript.side_effect = mock_transcript_error("Transcript not found")
        
        tool = PollTranscriptionJob(
            job_id=self.test_job_id,
            max_attempts=3,
            base_delay_sec=10,
            timeout_sec=300
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "transcript_error")
        self.assertIn("Failed to retrieve transcript", data["message"])
        self.assertEqual(data["job_id"], self.test_job_id)
    
    def test_json_string_return_format(self):
        """Test that tool returns valid JSON string per Agency Swarm v1.0.0."""
        with patch('poll_transcription_job.aai') as mock_aai:
            mock_transcript = Mock()
            mock_transcript.status = mock_aai.TranscriptStatus.completed
            mock_transcript.id = self.test_job_id
            mock_transcript.text = "Test transcript"
            
            mock_aai.Transcriber.return_value.get_transcript.return_value = mock_transcript
            mock_aai.TranscriptStatus.completed = "completed"
            
            tool = PollTranscriptionJob(
                job_id=self.test_job_id,
                max_attempts=3,
                base_delay_sec=10,
                timeout_sec=300
            )
            
            result = tool.run()
            
            # Should return string, not dict
            self.assertIsInstance(result, str)
            
            # Should be valid JSON
            try:
                data = json.loads(result)
                self.assertIsInstance(data, dict)
                self.assertIn("job_id", data)
                self.assertIn("status", data)
            except json.JSONDecodeError:
                self.fail("Tool did not return valid JSON string")


if __name__ == '__main__':
    unittest.main()