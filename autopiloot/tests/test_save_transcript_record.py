"""
Unit tests for SaveTranscriptRecord tool
Tests TASK-TRN-0022 Firestore metadata persistence implementation
"""

import unittest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Mock agency_swarm for testing
import sys
import importlib.util

# Import the tool module directly
tool_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'transcriber_agent', 'tools', 'save_transcript_record.py'
)
spec = importlib.util.spec_from_file_location("save_transcript_record", tool_path)
save_record_module = importlib.util.module_from_spec(spec)

# Mock dependencies before loading the module
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
    'google.oauth2': MagicMock(),
    'google.oauth2.service_account': MagicMock(),
    'dotenv': MagicMock()
}):
    spec.loader.exec_module(save_record_module)
    SaveTranscriptRecord = save_record_module.SaveTranscriptRecord


class TestSaveTranscriptRecord(unittest.TestCase):
    """Test cases for SaveTranscriptRecord tool."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_video_id = "test_video_123"
        self.test_drive_ids = {
            "drive_id_txt": "1AbC2defGhIJkLmNoPqRSTuVwxyz0123456789",
            "drive_id_json": "1XyZ9876543210abcDEFghiJKLmnOpQrStuVwx"
        }
        self.test_transcript_digest = "a1b2c3d4e5f67890"
        self.test_costs = {
            "transcription_usd": 0.6875
        }
        
        # Set up environment variables
        os.environ["GCP_PROJECT_ID"] = "test-project-123"
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/service-account.json"
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove test environment variables
        env_vars = ["GCP_PROJECT_ID", "GOOGLE_APPLICATION_CREDENTIALS"]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]
    
    def test_parameter_validation_success(self):
        """Test successful parameter validation with valid inputs."""
        # Should not raise error for valid parameters
        tool = SaveTranscriptRecord(
            video_id=self.test_video_id,
            drive_ids=self.test_drive_ids,
            transcript_digest=self.test_transcript_digest,
            costs=self.test_costs
        )
        self.assertEqual(tool.video_id, self.test_video_id)
        self.assertEqual(tool.drive_ids, self.test_drive_ids)
        self.assertEqual(tool.transcript_digest, self.test_transcript_digest)
        self.assertEqual(tool.costs, self.test_costs)
    
    def test_parameter_validation_empty_video_id(self):
        """Test video_id validation fails for empty string."""
        with self.assertRaises(ValueError) as context:
            SaveTranscriptRecord(
                video_id="",  # Empty video ID
                drive_ids=self.test_drive_ids,
                transcript_digest=self.test_transcript_digest,
                costs=self.test_costs
            )
        self.assertIn("cannot be empty", str(context.exception))
    
    def test_parameter_validation_long_video_id(self):
        """Test video_id validation fails for excessively long string."""
        with self.assertRaises(ValueError) as context:
            SaveTranscriptRecord(
                video_id="x" * 60,  # Too long
                drive_ids=self.test_drive_ids,
                transcript_digest=self.test_transcript_digest,
                costs=self.test_costs
            )
        self.assertIn("too long", str(context.exception))
    
    def test_parameter_validation_invalid_drive_ids_type(self):
        """Test drive_ids validation fails for non-dict type."""
        with self.assertRaises(ValueError) as context:
            SaveTranscriptRecord(
                video_id=self.test_video_id,
                drive_ids="not_a_dict",  # Wrong type
                transcript_digest=self.test_transcript_digest,
                costs=self.test_costs
            )
        self.assertIn("must be a dictionary", str(context.exception))
    
    def test_parameter_validation_missing_drive_id_keys(self):
        """Test drive_ids validation fails for missing required keys."""
        incomplete_drive_ids = {"drive_id_txt": "test_txt"}  # Missing drive_id_json
        
        with self.assertRaises(ValueError) as context:
            SaveTranscriptRecord(
                video_id=self.test_video_id,
                drive_ids=incomplete_drive_ids,
                transcript_digest=self.test_transcript_digest,
                costs=self.test_costs
            )
        self.assertIn("missing required keys", str(context.exception))
        self.assertIn("drive_id_json", str(context.exception))
    
    def test_parameter_validation_empty_drive_id_value(self):
        """Test drive_ids validation fails for empty values."""
        empty_drive_ids = {"drive_id_txt": "", "drive_id_json": "test_json"}  # Empty txt ID
        
        with self.assertRaises(ValueError) as context:
            SaveTranscriptRecord(
                video_id=self.test_video_id,
                drive_ids=empty_drive_ids,
                transcript_digest=self.test_transcript_digest,
                costs=self.test_costs
            )
        self.assertIn("cannot be empty", str(context.exception))
    
    def test_parameter_validation_empty_transcript_digest(self):
        """Test transcript_digest validation fails for empty string."""
        with self.assertRaises(ValueError) as context:
            SaveTranscriptRecord(
                video_id=self.test_video_id,
                drive_ids=self.test_drive_ids,
                transcript_digest="",  # Empty digest
                costs=self.test_costs
            )
        self.assertIn("cannot be empty", str(context.exception))
    
    def test_parameter_validation_invalid_transcript_digest_hex(self):
        """Test transcript_digest validation fails for non-hex string."""
        with self.assertRaises(ValueError) as context:
            SaveTranscriptRecord(
                video_id=self.test_video_id,
                drive_ids=self.test_drive_ids,
                transcript_digest="invalid_hex_123xyz",  # Contains non-hex characters
                costs=self.test_costs
            )
        self.assertIn("must be a valid hex string", str(context.exception))
    
    def test_parameter_validation_invalid_costs_type(self):
        """Test costs validation fails for non-dict type."""
        with self.assertRaises(ValueError) as context:
            SaveTranscriptRecord(
                video_id=self.test_video_id,
                drive_ids=self.test_drive_ids,
                transcript_digest=self.test_transcript_digest,
                costs="not_a_dict"  # Wrong type
            )
        self.assertIn("must be a dictionary", str(context.exception))
    
    def test_parameter_validation_missing_transcription_cost(self):
        """Test costs validation fails for missing transcription_usd key."""
        incomplete_costs = {"other_cost": 1.0}  # Missing transcription_usd
        
        with self.assertRaises(ValueError) as context:
            SaveTranscriptRecord(
                video_id=self.test_video_id,
                drive_ids=self.test_drive_ids,
                transcript_digest=self.test_transcript_digest,
                costs=incomplete_costs
            )
        self.assertIn("must include 'transcription_usd'", str(context.exception))
    
    def test_parameter_validation_negative_transcription_cost(self):
        """Test costs validation fails for negative transcription cost."""
        negative_costs = {"transcription_usd": -0.5}  # Negative cost
        
        with self.assertRaises(ValueError) as context:
            SaveTranscriptRecord(
                video_id=self.test_video_id,
                drive_ids=self.test_drive_ids,
                transcript_digest=self.test_transcript_digest,
                costs=negative_costs
            )
        self.assertIn("cannot be negative", str(context.exception))
    
    @patch('save_transcript_record.service_account')
    @patch('save_transcript_record.firestore')
    def test_successful_record_creation(self, mock_firestore, mock_service_account):
        """Test successful creation of transcript record and video status update."""
        # Mock service account credentials
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_credentials
        
        # Mock Firestore client and documents
        mock_db = Mock()
        mock_firestore.Client.return_value = mock_db
        
        # Mock existing video document
        mock_video_doc = Mock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {
            'status': 'transcription_queued',
            'title': 'Test Video Title',
            'channel_title': 'Test Channel',
            'published_at': '2024-01-01T00:00:00Z',
            'duration_sec': 300
        }
        
        mock_video_ref = Mock()
        mock_video_ref.get.return_value = mock_video_doc
        
        # Mock transcript document reference
        mock_transcript_ref = Mock()
        
        # Mock collections
        mock_db.collection.side_effect = lambda name: Mock(document=Mock(return_value={
            'videos': mock_video_ref,
            'transcripts': mock_transcript_ref
        }[name]))
        
        # Mock transaction
        mock_transaction = Mock()
        mock_db.transaction.return_value = mock_transaction
        
        tool = SaveTranscriptRecord(
            video_id=self.test_video_id,
            drive_ids=self.test_drive_ids,
            transcript_digest=self.test_transcript_digest,
            costs=self.test_costs
        )
        
        with patch('save_transcript_record.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.timezone = timezone
            
            result = tool.run()
            data = json.loads(result)
        
        # Verify successful record creation
        self.assertEqual(data["transcript_doc_ref"], f"transcripts/{self.test_video_id}")
        self.assertEqual(data["video_status"], "transcribed")
        self.assertEqual(data["video_id"], self.test_video_id)
        self.assertIn("created_at", data)
        self.assertEqual(data["drive_ids"], self.test_drive_ids)
        self.assertEqual(data["transcript_digest"], self.test_transcript_digest)
        self.assertEqual(data["costs"], self.test_costs)
        self.assertIn("status_change", data)
        self.assertEqual(data["status_change"]["from"], "transcription_queued")
        self.assertEqual(data["status_change"]["to"], "transcribed")
    
    def test_missing_gcp_project_id_env_var(self):
        """Test handling of missing GCP_PROJECT_ID."""
        # Remove project ID environment variable
        del os.environ["GCP_PROJECT_ID"]
        
        tool = SaveTranscriptRecord(
            video_id=self.test_video_id,
            drive_ids=self.test_drive_ids,
            transcript_digest=self.test_transcript_digest,
            costs=self.test_costs
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "configuration_error")
        self.assertIn("GCP_PROJECT_ID", data["message"])
    
    def test_missing_google_credentials_env_var(self):
        """Test handling of missing GOOGLE_APPLICATION_CREDENTIALS."""
        # Remove credentials environment variable
        del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        
        tool = SaveTranscriptRecord(
            video_id=self.test_video_id,
            drive_ids=self.test_drive_ids,
            transcript_digest=self.test_transcript_digest,
            costs=self.test_costs
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "configuration_error")
        self.assertIn("GOOGLE_APPLICATION_CREDENTIALS", data["message"])
    
    @patch('save_transcript_record.service_account')
    @patch('save_transcript_record.firestore')
    def test_video_document_not_found(self, mock_firestore, mock_service_account):
        """Test handling when video document doesn't exist."""
        # Mock service account credentials
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_credentials
        
        # Mock Firestore client
        mock_db = Mock()
        mock_firestore.Client.return_value = mock_db
        
        # Mock non-existent video document
        mock_video_doc = Mock()
        mock_video_doc.exists = False
        
        mock_video_ref = Mock()
        mock_video_ref.get.return_value = mock_video_doc
        
        mock_db.collection.return_value.document.return_value = mock_video_ref
        
        tool = SaveTranscriptRecord(
            video_id=self.test_video_id,
            drive_ids=self.test_drive_ids,
            transcript_digest=self.test_transcript_digest,
            costs=self.test_costs
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "document_not_found")
        self.assertIn("does not exist in Firestore", data["message"])
        self.assertEqual(data["video_id"], self.test_video_id)
    
    @patch('save_transcript_record.service_account')
    @patch('save_transcript_record.firestore')
    def test_invalid_video_status(self, mock_firestore, mock_service_account):
        """Test handling when video has invalid status for transcription completion."""
        # Mock service account credentials
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_credentials
        
        # Mock Firestore client
        mock_db = Mock()
        mock_firestore.Client.return_value = mock_db
        
        # Mock video document with invalid status
        mock_video_doc = Mock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {
            'status': 'invalid_status',  # Not expected status
            'title': 'Test Video'
        }
        
        mock_video_ref = Mock()
        mock_video_ref.get.return_value = mock_video_doc
        
        mock_db.collection.return_value.document.return_value = mock_video_ref
        
        tool = SaveTranscriptRecord(
            video_id=self.test_video_id,
            drive_ids=self.test_drive_ids,
            transcript_digest=self.test_transcript_digest,
            costs=self.test_costs
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "invalid_status")
        self.assertIn("has status 'invalid_status'", data["message"])
        self.assertEqual(data["current_status"], "invalid_status")
    
    @patch('save_transcript_record.service_account')
    def test_invalid_service_account_credentials(self, mock_service_account):
        """Test handling of invalid service account credentials."""
        # Create mock exception
        mock_creds_error = type('ServiceAccountCredentialsError', (Exception,), {})
        mock_service_account.exceptions.ServiceAccountCredentialsError = mock_creds_error
        
        # Configure mock to raise credentials error
        mock_service_account.Credentials.from_service_account_file.side_effect = mock_creds_error("Invalid credentials")
        
        tool = SaveTranscriptRecord(
            video_id=self.test_video_id,
            drive_ids=self.test_drive_ids,
            transcript_digest=self.test_transcript_digest,
            costs=self.test_costs
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "credentials_error")
        self.assertIn("Invalid Google service account credentials", data["message"])
    
    @patch('save_transcript_record.service_account')
    @patch('save_transcript_record.firestore')
    def test_firestore_operation_error(self, mock_firestore, mock_service_account):
        """Test handling of Firestore operation errors."""
        # Mock service account credentials
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_credentials
        
        # Mock Firestore client that raises exception
        mock_db = Mock()
        mock_firestore.Client.return_value = mock_db
        mock_db.collection.side_effect = Exception("Firestore connection error")
        
        tool = SaveTranscriptRecord(
            video_id=self.test_video_id,
            drive_ids=self.test_drive_ids,
            transcript_digest=self.test_transcript_digest,
            costs=self.test_costs
        )
        
        result = tool.run()
        data = json.loads(result)
        
        self.assertEqual(data["error"], "firestore_error")
        self.assertIn("Failed to save transcript record", data["message"])
        self.assertEqual(data["video_id"], self.test_video_id)
    
    def test_json_string_return_format(self):
        """Test that tool returns valid JSON string per Agency Swarm v1.0.0."""
        with patch('save_transcript_record.service_account') as mock_service_account:
            with patch('save_transcript_record.firestore') as mock_firestore:
                # Mock successful operation
                mock_credentials = Mock()
                mock_service_account.Credentials.from_service_account_file.return_value = mock_credentials
                
                mock_db = Mock()
                mock_firestore.Client.return_value = mock_db
                
                mock_video_doc = Mock()
                mock_video_doc.exists = True
                mock_video_doc.to_dict.return_value = {
                    'status': 'transcription_queued',
                    'title': 'Test Video'
                }
                
                mock_video_ref = Mock()
                mock_video_ref.get.return_value = mock_video_doc
                
                mock_db.collection.return_value.document.return_value = mock_video_ref
                mock_db.transaction.return_value = Mock()
                
                tool = SaveTranscriptRecord(
                    video_id=self.test_video_id,
                    drive_ids=self.test_drive_ids,
                    transcript_digest=self.test_transcript_digest,
                    costs=self.test_costs
                )
                
                with patch('save_transcript_record.datetime'):
                    result = tool.run()
                
                # Should return string, not dict
                self.assertIsInstance(result, str)
                
                # Should be valid JSON
                try:
                    data = json.loads(result)
                    self.assertIsInstance(data, dict)
                    self.assertIn("transcript_doc_ref", data)
                    self.assertIn("video_status", data)
                except json.JSONDecodeError:
                    self.fail("Tool did not return valid JSON string")


if __name__ == '__main__':
    unittest.main()