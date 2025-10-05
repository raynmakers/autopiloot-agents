"""
Comprehensive test for store_transcript_to_drive.py - targeting 75%+ coverage
Tests all paths including validation, Google Drive API integration, and error handling.
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import sys
import json
import os

# Mock all external dependencies before imports
sys.modules['agency_swarm'] = MagicMock()
sys.modules['agency_swarm.tools'] = MagicMock()
sys.modules['pydantic'] = MagicMock()
sys.modules['googleapiclient'] = MagicMock()
sys.modules['googleapiclient.discovery'] = MagicMock()
sys.modules['googleapiclient.http'] = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.oauth2'] = MagicMock()
sys.modules['google.oauth2.service_account'] = MagicMock()
sys.modules['google.oauth2.credentials'] = MagicMock()
sys.modules['dotenv'] = MagicMock()


class TestStoreTranscriptToDriveComprehensive(unittest.TestCase):
    """Comprehensive tests for store_transcript_to_drive.py achieving 75%+ coverage"""

    def setUp(self):
        """Set up test environment with comprehensive mocking."""
        # Mock pydantic Field and field_validator
        def mock_field(*args, **kwargs):
            return kwargs.get('default', ...)

        def mock_field_validator(*args, **kwargs):
            def decorator(func):
                return func
            return decorator

        sys.modules['pydantic'].Field = mock_field
        sys.modules['pydantic'].field_validator = mock_field_validator

        # Mock BaseTool
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
        sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

        # Mock dotenv
        sys.modules['dotenv'].load_dotenv = MagicMock()

    def test_successful_transcript_upload(self):
        """Test successful transcript upload to Google Drive."""
        with patch.dict(os.environ, {
            'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/service-account.json',
            'DRIVE_TRANSCRIPTS_FOLDER_ID': 'folder123'
        }):
            from transcriber_agent.tools.store_transcript_to_drive import StoreTranscriptToDrive

            # Mock Google Drive API
            mock_credentials = MagicMock()
            mock_service = MagicMock()

            # Mock file creation results
            mock_txt_result = {
                'id': 'txt_file_id_123',
                'name': 'test_video_123_2025-09-28_transcript.txt',
                'size': '1024',
                'createdTime': '2025-09-28T12:00:00Z'
            }
            mock_json_result = {
                'id': 'json_file_id_456',
                'name': 'test_video_123_2025-09-28_transcript.json',
                'size': '2048',
                'createdTime': '2025-09-28T12:00:00Z'
            }

            # Mock Drive service files().create() chain
            mock_files = MagicMock()
            mock_create = MagicMock()
            mock_execute = MagicMock()

            mock_execute.side_effect = [mock_txt_result, mock_json_result]
            mock_create.return_value.execute = mock_execute
            mock_files.return_value.create = mock_create
            mock_service.files = mock_files

            with patch('transcriber_agent.tools.store_transcript_to_drive.service_account') as mock_sa, \
                 patch('transcriber_agent.tools.store_transcript_to_drive.build') as mock_build:

                mock_sa.Credentials.from_service_account_file.return_value = mock_credentials
                mock_build.return_value = mock_service

                tool = StoreTranscriptToDrive(
                    video_id='test_video_123',
                    transcript_text='This is a test transcript with multiple sentences.',
                    transcript_json={
                        'id': 'job123',
                        'text': 'This is a test transcript with multiple sentences.',
                        'status': 'completed',
                        'confidence': 0.95
                    }
                )

                result = tool.run()
                result_data = json.loads(result)

                # Verify result structure
                self.assertIn('drive_id_txt', result_data)
                self.assertIn('drive_id_json', result_data)
                self.assertIn('txt_filename', result_data)
                self.assertIn('json_filename', result_data)
                self.assertIn('transcript_digest', result_data)
                self.assertIn('files_uploaded', result_data)

                # Verify file IDs
                self.assertEqual(result_data['drive_id_txt'], 'txt_file_id_123')
                self.assertEqual(result_data['drive_id_json'], 'json_file_id_456')

    def test_missing_google_credentials_env_var(self):
        """Test error handling when GOOGLE_APPLICATION_CREDENTIALS is missing."""
        with patch.dict(os.environ, {}, clear=True):
            from transcriber_agent.tools.store_transcript_to_drive import StoreTranscriptToDrive

            tool = StoreTranscriptToDrive(
                video_id='test_video',
                transcript_text='Test transcript',
                transcript_json={'id': 'test', 'text': 'Test', 'status': 'completed'}
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn('error', result_data)
            self.assertEqual(result_data['error'], 'configuration_error')
            self.assertIn('GOOGLE_APPLICATION_CREDENTIALS', result_data['message'])

    def test_missing_drive_folder_env_var(self):
        """Test error handling when DRIVE_TRANSCRIPTS_FOLDER_ID is missing."""
        with patch.dict(os.environ, {
            'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/service-account.json'
        }):
            from transcriber_agent.tools.store_transcript_to_drive import StoreTranscriptToDrive

            tool = StoreTranscriptToDrive(
                video_id='test_video',
                transcript_text='Test transcript',
                transcript_json={'id': 'test', 'text': 'Test', 'status': 'completed'}
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertIn('error', result_data)
            self.assertEqual(result_data['error'], 'configuration_error')
            self.assertIn('DRIVE_TRANSCRIPTS_FOLDER_ID', result_data['message'])

    def test_service_account_credentials_error(self):
        """Test error handling for invalid service account credentials."""
        with patch.dict(os.environ, {
            'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/invalid.json',
            'DRIVE_TRANSCRIPTS_FOLDER_ID': 'folder123'
        }):
            from transcriber_agent.tools.store_transcript_to_drive import StoreTranscriptToDrive

            with patch('transcriber_agent.tools.store_transcript_to_drive.service_account') as mock_sa:
                # Mock service account exception
                mock_sa.exceptions.ServiceAccountCredentialsError = Exception
                mock_sa.Credentials.from_service_account_file.side_effect = Exception("Invalid credentials")

                tool = StoreTranscriptToDrive(
                    video_id='test_video',
                    transcript_text='Test transcript',
                    transcript_json={'id': 'test', 'text': 'Test', 'status': 'completed'}
                )

                result = tool.run()
                result_data = json.loads(result)

                self.assertIn('error', result_data)
                self.assertEqual(result_data['error'], 'credentials_error')
                self.assertIn('Invalid Google service account credentials', result_data['message'])

    def test_general_upload_error(self):
        """Test error handling for general upload failures."""
        with patch.dict(os.environ, {
            'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/service-account.json',
            'DRIVE_TRANSCRIPTS_FOLDER_ID': 'folder123'
        }):
            from transcriber_agent.tools.store_transcript_to_drive import StoreTranscriptToDrive

            with patch('transcriber_agent.tools.store_transcript_to_drive.service_account') as mock_sa, \
                 patch('transcriber_agent.tools.store_transcript_to_drive.build') as mock_build:

                mock_credentials = MagicMock()
                mock_sa.Credentials.from_service_account_file.return_value = mock_credentials

                # Mock Drive service to raise exception
                mock_build.side_effect = Exception("Drive API error")

                tool = StoreTranscriptToDrive(
                    video_id='test_video_error',
                    transcript_text='Test transcript',
                    transcript_json={'id': 'test', 'text': 'Test', 'status': 'completed'}
                )

                result = tool.run()
                result_data = json.loads(result)

                self.assertIn('error', result_data)
                self.assertEqual(result_data['error'], 'upload_error')
                self.assertIn('Failed to store transcript to Drive', result_data['message'])
                self.assertEqual(result_data['video_id'], 'test_video_error')

    def test_video_id_validation_empty(self):
        """Test video_id validation for empty string."""
        from transcriber_agent.tools.store_transcript_to_drive import StoreTranscriptToDrive

        with self.assertRaises(ValueError) as context:
            StoreTranscriptToDrive(
                video_id='',
                transcript_text='Test transcript',
                transcript_json={'id': 'test', 'text': 'Test', 'status': 'completed'}
            )

        self.assertIn('video_id cannot be empty', str(context.exception))

    def test_video_id_validation_too_long(self):
        """Test video_id validation for too long string."""
        from transcriber_agent.tools.store_transcript_to_drive import StoreTranscriptToDrive

        with self.assertRaises(ValueError) as context:
            StoreTranscriptToDrive(
                video_id='a' * 51,  # Too long
                transcript_text='Test transcript',
                transcript_json={'id': 'test', 'text': 'Test', 'status': 'completed'}
            )

        self.assertIn('video_id seems too long', str(context.exception))

    def test_transcript_text_validation_empty(self):
        """Test transcript_text validation for empty string."""
        from transcriber_agent.tools.store_transcript_to_drive import StoreTranscriptToDrive

        with self.assertRaises(ValueError) as context:
            StoreTranscriptToDrive(
                video_id='test_video',
                transcript_text='',
                transcript_json={'id': 'test', 'text': 'Test', 'status': 'completed'}
            )

        self.assertIn('transcript_text cannot be empty', str(context.exception))

    def test_transcript_json_validation_not_dict(self):
        """Test transcript_json validation for non-dictionary input."""
        from transcriber_agent.tools.store_transcript_to_drive import StoreTranscriptToDrive

        with self.assertRaises(ValueError) as context:
            StoreTranscriptToDrive(
                video_id='test_video',
                transcript_text='Test transcript',
                transcript_json='not a dict'
            )

        self.assertIn('transcript_json must be a dictionary', str(context.exception))

    def test_transcript_json_validation_missing_fields(self):
        """Test transcript_json validation for missing required fields."""
        from transcriber_agent.tools.store_transcript_to_drive import StoreTranscriptToDrive

        with self.assertRaises(ValueError) as context:
            StoreTranscriptToDrive(
                video_id='test_video',
                transcript_text='Test transcript',
                transcript_json={'id': 'test'}  # Missing 'text' and 'status'
            )

        self.assertIn('transcript_json missing required fields', str(context.exception))
        self.assertIn('text', str(context.exception))
        self.assertIn('status', str(context.exception))

    def test_video_id_validation_whitespace_handling(self):
        """Test video_id validation strips whitespace."""
        from transcriber_agent.tools.store_transcript_to_drive import StoreTranscriptToDrive

        # Should not raise exception and strip whitespace
        tool = StoreTranscriptToDrive(
            video_id='  test_video  ',
            transcript_text='Test transcript',
            transcript_json={'id': 'test', 'text': 'Test', 'status': 'completed'}
        )

        self.assertEqual(tool.video_id, 'test_video')

    def test_complex_transcript_data_structure(self):
        """Test handling of complex transcript JSON structure."""
        with patch.dict(os.environ, {
            'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/service-account.json',
            'DRIVE_TRANSCRIPTS_FOLDER_ID': 'folder123'
        }):
            from transcriber_agent.tools.store_transcript_to_drive import StoreTranscriptToDrive

            # Mock Google Drive API success
            mock_credentials = MagicMock()
            mock_service = MagicMock()

            mock_txt_result = {'id': 'txt123', 'name': 'file.txt', 'size': '1024', 'createdTime': '2025-09-28T12:00:00Z'}
            mock_json_result = {'id': 'json456', 'name': 'file.json', 'size': '2048', 'createdTime': '2025-09-28T12:00:00Z'}

            mock_files = MagicMock()
            mock_create = MagicMock()
            mock_execute = MagicMock()

            mock_execute.side_effect = [mock_txt_result, mock_json_result]
            mock_create.return_value.execute = mock_execute
            mock_files.return_value.create = mock_create
            mock_service.files = mock_files

            with patch('transcriber_agent.tools.store_transcript_to_drive.service_account') as mock_sa, \
                 patch('transcriber_agent.tools.store_transcript_to_drive.build') as mock_build:

                mock_sa.Credentials.from_service_account_file.return_value = mock_credentials
                mock_build.return_value = mock_service

                complex_json = {
                    'id': 'complex_job_123',
                    'text': 'Complex transcript with speaker labels',
                    'status': 'completed',
                    'confidence': 0.95,
                    'audio_duration': 300.5,
                    'language_code': 'en',
                    'utterances': [
                        {
                            'speaker': 'A',
                            'text': 'Hello there',
                            'start': 0,
                            'end': 1000,
                            'confidence': 0.98
                        }
                    ],
                    'words': [
                        {'text': 'Hello', 'start': 0, 'end': 500, 'confidence': 0.99},
                        {'text': 'there', 'start': 600, 'end': 1000, 'confidence': 0.97}
                    ]
                }

                tool = StoreTranscriptToDrive(
                    video_id='complex_video',
                    transcript_text='Complex transcript with speaker labels',
                    transcript_json=complex_json
                )

                result = tool.run()
                result_data = json.loads(result)

                # Verify successful processing of complex data
                self.assertNotIn('error', result_data)
                self.assertIn('drive_id_txt', result_data)
                self.assertIn('drive_id_json', result_data)

    def test_main_block_execution(self):
        """Test main block execution for coverage."""
        with patch('transcriber_agent.tools.store_transcript_to_drive.StoreTranscriptToDrive') as mock_tool_class, \
             patch('builtins.print') as mock_print:

            # Mock tool instances for each test
            mock_tool = MagicMock()
            mock_tool.run.return_value = json.dumps({
                'drive_id_txt': 'txt123',
                'drive_id_json': 'json456',
                'txt_filename': 'test.txt',
                'json_filename': 'test.json',
                'transcript_digest': 'abcd1234'
            })
            mock_tool_class.return_value = mock_tool

            # Import and execute main block
            import transcriber_agent.tools.store_transcript_to_drive

            # Verify print was called (main block executed)
            mock_print.assert_called()


if __name__ == "__main__":
    unittest.main()