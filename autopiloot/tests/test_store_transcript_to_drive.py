"""
Unit tests for StoreTranscriptToDrive tool
Tests TASK-TRN-0022 Google Drive storage implementation
"""

import unittest
import json
import os
import hashlib
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Mock agency_swarm for testing
import sys
import importlib.util

# Import the tool module directly
tool_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'transcriber_agent', 'tools', 'store_transcript_to_drive.py'
)
spec = importlib.util.spec_from_file_location("store_transcript_to_drive", tool_path)
drive_store_module = importlib.util.module_from_spec(spec)

# Mock dependencies before loading the module
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'googleapiclient': MagicMock(),
    'googleapiclient.discovery': MagicMock(),
    'googleapiclient.http': MagicMock(),
    'google.oauth2': MagicMock(),
    'google.oauth2.service_account': MagicMock(),
    'dotenv': MagicMock()
}):
    spec.loader.exec_module(drive_store_module)
    StoreTranscriptToDrive = drive_store_module.StoreTranscriptToDrive


class TestStoreTranscriptToDrive(unittest.TestCase):
    """Test cases for StoreTranscriptToDrive tool."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_video_id = "test_video_123"
        self.test_transcript_text = "This is a comprehensive test transcript with multiple sentences."
        self.test_transcript_json = {
            "id": "test_job_12345",
            "status": "completed",
            "text": "This is a comprehensive test transcript with multiple sentences.",
            "confidence": 0.9234,
            "audio_duration": 156.7,
            "language_code": "en",
            "words": [
                {"text": "This", "start": 0, "end": 240, "confidence": 0.95},
                {"text": "is", "start": 250, "end": 400, "confidence": 0.98}
            ]
        }
        
        # Set up environment variables
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/service-account.json"
        os.environ["DRIVE_TRANSCRIPTS_FOLDER_ID"] = "1AbC2defGhIJkLmNoPqRSTuVwxyz0123456789"
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove test environment variables
        env_vars = ["GOOGLE_APPLICATION_CREDENTIALS", "DRIVE_TRANSCRIPTS_FOLDER_ID"]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]
    
    def test_parameter_validation_success(self):
        """Test successful parameter validation with valid inputs."""
        # Should not raise error for valid parameters
        tool = StoreTranscriptToDrive(
            video_id=self.test_video_id,
            transcript_text=self.test_transcript_text,
            transcript_json=self.test_transcript_json
        )
        self.assertEqual(tool.video_id, self.test_video_id)
        self.assertEqual(tool.transcript_text, self.test_transcript_text)
        self.assertEqual(tool.transcript_json, self.test_transcript_json)
    
    def test_parameter_validation_empty_video_id(self):
        """Test video_id validation fails for empty string."""
        with self.assertRaises(ValueError) as context:
            StoreTranscriptToDrive(
                video_id="",  # Empty video ID
                transcript_text=self.test_transcript_text,
                transcript_json=self.test_transcript_json
            )
        self.assertIn("cannot be empty", str(context.exception))
    
    def test_parameter_validation_long_video_id(self):
        """Test video_id validation fails for excessively long string."""
        with self.assertRaises(ValueError) as context:
            StoreTranscriptToDrive(
                video_id="x" * 60,  # Too long
                transcript_text=self.test_transcript_text,
                transcript_json=self.test_transcript_json
            )
        self.assertIn("too long", str(context.exception))
    
    def test_parameter_validation_empty_transcript_text(self):
        """Test transcript_text validation fails for empty string."""
        with self.assertRaises(ValueError) as context:
            StoreTranscriptToDrive(
                video_id=self.test_video_id,
                transcript_text="",  # Empty transcript
                transcript_json=self.test_transcript_json
            )
        self.assertIn("cannot be empty", str(context.exception))
    
    def test_parameter_validation_invalid_transcript_json_type(self):
        """Test transcript_json validation fails for non-dict type."""
        with self.assertRaises(ValueError) as context:
            StoreTranscriptToDrive(
                video_id=self.test_video_id,
                transcript_text=self.test_transcript_text,
                transcript_json="not_a_dict"  # Wrong type
            )
        self.assertIn("must be a dictionary", str(context.exception))
    
    def test_parameter_validation_missing_required_json_fields(self):
        """Test transcript_json validation fails for missing required fields."""
        incomplete_json = {"id": "test"}  # Missing 'text' and 'status'
        
        with self.assertRaises(ValueError) as context:
            StoreTranscriptToDrive(
                video_id=self.test_video_id,
                transcript_text=self.test_transcript_text,
                transcript_json=incomplete_json
            )
        self.assertIn("missing required fields", str(context.exception))
        self.assertIn("text", str(context.exception))
        self.assertIn("status", str(context.exception))
    
    @patch('store_transcript_to_drive.service_account')
    @patch('store_transcript_to_drive.build')
    def test_successful_file_upload(self, mock_build, mock_service_account):
        """Test successful upload of both TXT and JSON files."""
        # Mock service account credentials
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_credentials
        
        # Mock Google Drive service
        mock_drive = Mock()
        mock_build.return_value = mock_drive
        
        # Mock successful file creation responses
        txt_response = {
            'id': 'drive_txt_file_id_123',
            'name': f'{self.test_video_id}_2024-01-01_transcript.txt',
            'size': '1024',
            'createdTime': '2024-01-01T12:00:00.000Z'
        }
        json_response = {
            'id': 'drive_json_file_id_456',
            'name': f'{self.test_video_id}_2024-01-01_transcript.json',
            'size': '2048',
            'createdTime': '2024-01-01T12:00:00.000Z'
        }
        
        # Mock files().create().execute() chain
        mock_drive.files.return_value.create.return_value.execute.side_effect = [
            txt_response, json_response
        ]
        
        tool = StoreTranscriptToDrive(
            video_id=self.test_video_id,
            transcript_text=self.test_transcript_text,
            transcript_json=self.test_transcript_json
        )
        
        with patch('store_transcript_to_drive.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value.strftime.return_value = '2024-01-01'
            mock_datetime.utcnow.return_value.isoformat.return_value = '2024-01-01T12:00:00'
            
            result = tool.run()
            data = json.loads(result)
        
        # Verify successful upload
        self.assertEqual(data["drive_id_txt"], "drive_txt_file_id_123")
        self.assertEqual(data["drive_id_json"], "drive_json_file_id_456")
        self.assertIn("transcript_digest", data)
        self.assertIn("files_uploaded", data)
        
        # Verify both files were attempted to be created
        self.assertEqual(mock_drive.files.return_value.create.call_count, 2)
    
    def test_missing_google_credentials_env_var(self):
        """Test handling of missing GOOGLE_APPLICATION_CREDENTIALS."""
        # Remove credentials environment variable
        del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        
        tool = StoreTranscriptToDrive(
            video_id=self.test_video_id,
            transcript_text=self.test_transcript_text,
            transcript_json=self.test_transcript_json
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "configuration_error")
        self.assertIn("GOOGLE_APPLICATION_CREDENTIALS", data["message"])
    
    def test_missing_drive_folder_id_env_var(self):
        """Test handling of missing DRIVE_TRANSCRIPTS_FOLDER_ID."""
        # Remove folder ID environment variable
        del os.environ["DRIVE_TRANSCRIPTS_FOLDER_ID"]
        
        tool = StoreTranscriptToDrive(
            video_id=self.test_video_id,
            transcript_text=self.test_transcript_text,
            transcript_json=self.test_transcript_json
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "configuration_error")
        self.assertIn("DRIVE_TRANSCRIPTS_FOLDER_ID", data["message"])
    
    @patch('store_transcript_to_drive.service_account')
    def test_invalid_service_account_credentials(self, mock_service_account):
        """Test handling of invalid service account credentials."""
        # Create mock exception
        mock_creds_error = type('ServiceAccountCredentialsError', (Exception,), {})
        mock_service_account.exceptions.ServiceAccountCredentialsError = mock_creds_error
        
        # Configure mock to raise credentials error
        mock_service_account.Credentials.from_service_account_file.side_effect = mock_creds_error("Invalid credentials")
        
        tool = StoreTranscriptToDrive(
            video_id=self.test_video_id,
            transcript_text=self.test_transcript_text,
            transcript_json=self.test_transcript_json
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "credentials_error")
        self.assertIn("Invalid Google service account credentials", data["message"])
    
    @patch('store_transcript_to_drive.service_account')
    @patch('store_transcript_to_drive.build')
    def test_drive_api_upload_error(self, mock_build, mock_service_account):
        """Test handling of Google Drive API upload errors."""
        # Mock service account credentials
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_credentials
        
        # Mock Google Drive service that raises exception
        mock_drive = Mock()
        mock_build.return_value = mock_drive
        mock_drive.files.return_value.create.return_value.execute.side_effect = Exception("Drive API error")
        
        tool = StoreTranscriptToDrive(
            video_id=self.test_video_id,
            transcript_text=self.test_transcript_text,
            transcript_json=self.test_transcript_json
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "upload_error")
        self.assertIn("Failed to store transcript to Drive", data["message"])
        self.assertEqual(data["video_id"], self.test_video_id)
    
    @patch('store_transcript_to_drive.service_account')
    @patch('store_transcript_to_drive.build')
    def test_transcript_digest_generation(self, mock_build, mock_service_account):
        """Test that transcript digest is correctly generated."""
        # Mock service account credentials
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_credentials
        
        # Mock Google Drive service
        mock_drive = Mock()
        mock_build.return_value = mock_drive
        
        # Mock file creation responses
        mock_drive.files.return_value.create.return_value.execute.side_effect = [
            {'id': 'txt_id', 'name': 'txt_file', 'size': '100', 'createdTime': '2024-01-01T00:00:00Z'},
            {'id': 'json_id', 'name': 'json_file', 'size': '200', 'createdTime': '2024-01-01T00:00:00Z'}
        ]
        
        tool = StoreTranscriptToDrive(
            video_id=self.test_video_id,
            transcript_text=self.test_transcript_text,
            transcript_json=self.test_transcript_json
        )
        
        with patch('store_transcript_to_drive.datetime'):
            result = tool.run()
            data = json.loads(result)
        
        # Calculate expected digest
        expected_digest = hashlib.sha256(self.test_transcript_text.encode('utf-8')).hexdigest()[:16]
        
        self.assertEqual(data["transcript_digest"], expected_digest)
        self.assertIn("transcript_digest", data)
    
    @patch('store_transcript_to_drive.service_account')
    @patch('store_transcript_to_drive.build')
    def test_enhanced_json_metadata(self, mock_build, mock_service_account):
        """Test that JSON file is enhanced with metadata."""
        # Mock service account credentials
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_credentials
        
        # Mock Google Drive service
        mock_drive = Mock()
        mock_build.return_value = mock_drive
        
        # Capture the JSON content that gets uploaded
        uploaded_json_content = None
        
        def capture_json_upload(*args, **kwargs):
            nonlocal uploaded_json_content
            # Extract the media body content from the call
            media_arg = None
            for arg in args:
                if hasattr(arg, 'getvalue'):  # MediaInMemoryUpload object
                    media_arg = arg
                    break
            if media_arg:
                uploaded_json_content = media_arg._stream.read().decode('utf-8')
                media_arg._stream.seek(0)  # Reset stream position
            return {'id': 'json_id', 'name': 'json_file', 'size': '200', 'createdTime': '2024-01-01T00:00:00Z'}
        
        mock_drive.files.return_value.create.return_value.execute.side_effect = [
            {'id': 'txt_id', 'name': 'txt_file', 'size': '100', 'createdTime': '2024-01-01T00:00:00Z'},
            capture_json_upload
        ]
        
        tool = StoreTranscriptToDrive(
            video_id=self.test_video_id,
            transcript_text=self.test_transcript_text,
            transcript_json=self.test_transcript_json
        )
        
        with patch('store_transcript_to_drive.datetime'):
            result = tool.run()
        
        # Verify enhanced JSON was created (would need to examine the upload call)
        # This is a simplified test - in practice, we'd inspect the MediaInMemoryUpload content
        self.assertIsNotNone(result)
        data = json.loads(result)
        self.assertIn("drive_id_json", data)
    
    def test_json_string_return_format(self):
        """Test that tool returns valid JSON string per Agency Swarm v1.0.0."""
        with patch('store_transcript_to_drive.service_account') as mock_service_account:
            with patch('store_transcript_to_drive.build') as mock_build:
                # Mock successful upload
                mock_credentials = Mock()
                mock_service_account.Credentials.from_service_account_file.return_value = mock_credentials
                
                mock_drive = Mock()
                mock_build.return_value = mock_drive
                mock_drive.files.return_value.create.return_value.execute.side_effect = [
                    {'id': 'txt_id', 'name': 'txt_file', 'size': '100', 'createdTime': '2024-01-01T00:00:00Z'},
                    {'id': 'json_id', 'name': 'json_file', 'size': '200', 'createdTime': '2024-01-01T00:00:00Z'}
                ]
                
                tool = StoreTranscriptToDrive(
                    video_id=self.test_video_id,
                    transcript_text=self.test_transcript_text,
                    transcript_json=self.test_transcript_json
                )
                
                with patch('store_transcript_to_drive.datetime'):
                    result = tool.run()
                
                # Should return string, not dict
                self.assertIsInstance(result, str)
                
                # Should be valid JSON
                try:
                    data = json.loads(result)
                    self.assertIsInstance(data, dict)
                    self.assertIn("drive_id_txt", data)
                    self.assertIn("drive_id_json", data)
                except json.JSONDecodeError:
                    self.fail("Tool did not return valid JSON string")


if __name__ == '__main__':
    unittest.main()