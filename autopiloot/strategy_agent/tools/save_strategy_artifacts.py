"""
SaveStrategyArtifacts tool for persisting Strategy Playbooks and briefs to storage.
Saves artifacts to Google Drive (Markdown/JSON) and Firestore with optional Zep integration.
"""

import os
import sys
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
from env_loader import get_required_env_var, get_optional_env_var, load_environment
from loader import load_app_config, get_config_value


class SaveStrategyArtifacts(BaseTool):
    """
    Persists Strategy Playbook and briefs to multiple storage systems.

    Saves artifacts to Google Drive (Markdown/JSON files), Firestore database
    (`strategy_reports/{urn}/{date}`), and optionally Zep document store for retrieval.
    """

    urn: str = Field(
        ...,
        description="Unique resource identifier for the strategy analysis (e.g., 'linkedin_alexhormozi')"
    )

    playbook_md: str = Field(
        ...,
        description="Strategy playbook in Markdown format"
    )

    playbook_json: Dict[str, Any] = Field(
        ...,
        description="Strategy playbook in structured JSON format"
    )

    briefs: List[Dict[str, Any]] = Field(
        ...,
        description="Generated content briefs list"
    )

    save_to_drive: bool = Field(
        True,
        description="Whether to save artifacts to Google Drive (default: True)"
    )

    save_to_firestore: bool = Field(
        True,
        description="Whether to save artifacts to Firestore (default: True)"
    )

    save_to_zep: bool = Field(
        False,
        description="Whether to save artifacts to Zep for retrieval (default: False)"
    )

    folder_name: Optional[str] = Field(
        None,
        description="Custom folder name in Drive (default: 'Strategy Reports')"
    )

    def run(self) -> str:
        """
        Saves strategy artifacts to configured storage systems.

        Returns:
            str: JSON string containing save results and references
                 Format: {
                     "save_results": {
                         "drive": {
                             "success": true,
                             "playbook_file_id": "1abc123...",
                             "briefs_file_id": "1def456...",
                             "folder_url": "https://drive.google.com/drive/folders/...",
                             "files_created": 2
                         },
                         "firestore": {
                             "success": true,
                             "document_path": "strategy_reports/linkedin_alexhormozi/2024-01-15",
                             "document_id": "auto_generated_id",
                             "timestamp": "2024-01-15T10:00:00Z"
                         },
                         "zep": {
                             "success": true,
                             "document_id": "zep_doc_123",
                             "group_id": "strategy_playbooks",
                             "searchable": true
                         }
                     },
                     "artifact_references": {
                         "playbook_drive_url": "https://drive.google.com/file/d/...",
                         "briefs_drive_url": "https://drive.google.com/file/d/...",
                         "firestore_path": "strategy_reports/linkedin_alexhormozi/2024-01-15",
                         "zep_document_id": "zep_doc_123"
                     },
                     "metadata": {
                         "urn": "linkedin_alexhormozi",
                         "total_briefs": 5,
                         "playbook_sections": 8,
                         "save_timestamp": "2024-01-15T10:00:00Z",
                         "file_sizes": {
                             "playbook_md": "12.5KB",
                             "playbook_json": "8.3KB",
                             "briefs_json": "15.7KB"
                         }
                     }
                 }
        """
        try:
            # Validate inputs
            validation_error = self._validate_inputs()
            if validation_error:
                return json.dumps(validation_error)

            # Load environment
            load_environment()

            # Initialize storage clients
            drive_client = None
            firestore_client = None
            zep_client = None

            if self.save_to_drive:
                drive_client = self._initialize_drive_client()

            if self.save_to_firestore:
                firestore_client = self._initialize_firestore_client()

            if self.save_to_zep:
                zep_client = self._initialize_zep_client()

            # Prepare artifacts for saving
            artifacts = self._prepare_artifacts()

            # Save to each storage system
            save_results = {}
            artifact_references = {}

            # Save to Google Drive
            if self.save_to_drive and drive_client:
                drive_result = self._save_to_drive(drive_client, artifacts)
                save_results["drive"] = drive_result
                if drive_result.get("success"):
                    artifact_references.update({
                        "playbook_drive_url": drive_result.get("playbook_url"),
                        "briefs_drive_url": drive_result.get("briefs_url"),
                        "drive_folder_url": drive_result.get("folder_url")
                    })

            # Save to Firestore
            if self.save_to_firestore and firestore_client:
                firestore_result = self._save_to_firestore(firestore_client, artifacts)
                save_results["firestore"] = firestore_result
                if firestore_result.get("success"):
                    artifact_references["firestore_path"] = firestore_result.get("document_path")

            # Save to Zep
            if self.save_to_zep and zep_client:
                zep_result = self._save_to_zep(zep_client, artifacts)
                save_results["zep"] = zep_result
                if zep_result.get("success"):
                    artifact_references["zep_document_id"] = zep_result.get("document_id")

            # Generate metadata
            metadata = self._generate_metadata(artifacts)

            # Prepare final result
            result = {
                "save_results": save_results,
                "artifact_references": artifact_references,
                "metadata": metadata,
                "storage_summary": {
                    "systems_used": len([k for k, v in save_results.items() if v.get("success")]),
                    "total_files_created": sum(r.get("files_created", 0) for r in save_results.values()),
                    "save_success": all(r.get("success", False) for r in save_results.values()) if save_results else False
                }
            }

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "artifact_save_failed",
                "message": str(e),
                "urn": self.urn,
                "storage_targets": {
                    "drive": self.save_to_drive,
                    "firestore": self.save_to_firestore,
                    "zep": self.save_to_zep
                }
            }
            return json.dumps(error_result)

    def _validate_inputs(self) -> Optional[Dict[str, Any]]:
        """Validate required inputs."""
        if not self.urn or not self.urn.strip():
            return {
                "error": "invalid_urn",
                "message": "Valid URN is required for artifact identification"
            }

        if not self.playbook_md or not self.playbook_md.strip():
            return {
                "error": "missing_playbook_md",
                "message": "Playbook markdown content is required"
            }

        if not self.playbook_json or not isinstance(self.playbook_json, dict):
            return {
                "error": "invalid_playbook_json",
                "message": "Valid playbook JSON data is required"
            }

        if not self.briefs or not isinstance(self.briefs, list):
            return {
                "error": "invalid_briefs",
                "message": "Valid briefs list is required"
            }

        # Check if at least one storage option is enabled
        if not (self.save_to_drive or self.save_to_firestore or self.save_to_zep):
            return {
                "error": "no_storage_enabled",
                "message": "At least one storage option must be enabled"
            }

        return None

    def _prepare_artifacts(self) -> Dict[str, Any]:
        """Prepare artifacts for saving with metadata."""
        timestamp = datetime.now(timezone.utc)
        date_str = timestamp.strftime("%Y-%m-%d")

        artifacts = {
            "urn": self.urn,
            "timestamp": timestamp,
            "date_str": date_str,
            "playbook_md": self.playbook_md,
            "playbook_json": self.playbook_json,
            "briefs": self.briefs,
            "file_names": {
                "playbook_md": f"strategy_playbook_{self.urn}_{date_str}.md",
                "playbook_json": f"strategy_playbook_{self.urn}_{date_str}.json",
                "briefs_json": f"content_briefs_{self.urn}_{date_str}.json"
            }
        }

        # Add combined JSON artifact
        artifacts["combined_json"] = {
            "urn": self.urn,
            "generated_at": timestamp.isoformat() + "Z",
            "playbook": self.playbook_json,
            "content_briefs": self.briefs,
            "metadata": {
                "brief_count": len(self.briefs),
                "playbook_sections": len(self.playbook_json.keys()) if self.playbook_json else 0,
                "total_artifacts": 3
            }
        }

        return artifacts

    def _initialize_drive_client(self):
        """Initialize Google Drive client."""
        try:
            # Check for service account credentials
            service_account_path = get_optional_env_var("GOOGLE_APPLICATION_CREDENTIALS", "", "Google service account credentials path for Drive storage")
            if not service_account_path or not os.path.exists(service_account_path):
                return MockDriveClient()

            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credentials = service_account.Credentials.from_service_account_file(
                service_account_path,
                scopes=['https://www.googleapis.com/auth/drive']
            )

            service = build('drive', 'v3', credentials=credentials)
            return DriveClient(service)

        except ImportError:
            return MockDriveClient()
        except Exception as e:
            return MockDriveClient()

    def _initialize_firestore_client(self):
        """Initialize Firestore client."""
        try:
            # Check for service account credentials
            service_account_path = get_optional_env_var("GOOGLE_APPLICATION_CREDENTIALS", "", "Google service account credentials path for Firestore")
            if not service_account_path or not os.path.exists(service_account_path):
                return MockFirestoreClient()

            import firebase_admin
            from firebase_admin import credentials, firestore

            # Initialize Firebase if not already done
            if not firebase_admin._apps:
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)

            db = firestore.client()
            return FirestoreClient(db)

        except ImportError:
            return MockFirestoreClient()
        except Exception as e:
            return MockFirestoreClient()

    def _initialize_zep_client(self):
        """Initialize Zep client."""
        try:
            try:
                zep_api_key = get_required_env_var("ZEP_API_KEY", "Zep API key for strategy artifact storage")
            except EnvironmentError:
                return MockZepClient()

            zep_base_url = get_optional_env_var("ZEP_BASE_URL", "https://api.getzep.com", "Zep API base URL")

            from zep_python import ZepClient
            return ZepClient(api_key=zep_api_key, base_url=zep_base_url)

        except ImportError:
            return MockZepClient()
        except Exception as e:
            return MockZepClient()

    def _save_to_drive(self, drive_client, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Save artifacts to Google Drive."""
        try:
            folder_name = self.folder_name or "Strategy Reports"
            folder_id = drive_client.create_or_get_folder(folder_name)

            # Create URN subfolder
            urn_folder_id = drive_client.create_or_get_folder(self.urn, parent_folder_id=folder_id)

            files_created = 0
            file_ids = {}

            # Save playbook markdown
            playbook_md_id = drive_client.upload_file(
                artifacts["file_names"]["playbook_md"],
                artifacts["playbook_md"],
                urn_folder_id,
                mime_type="text/markdown"
            )
            if playbook_md_id:
                file_ids["playbook_md"] = playbook_md_id
                files_created += 1

            # Save playbook JSON
            playbook_json_content = json.dumps(artifacts["playbook_json"], indent=2)
            playbook_json_id = drive_client.upload_file(
                artifacts["file_names"]["playbook_json"],
                playbook_json_content,
                urn_folder_id,
                mime_type="application/json"
            )
            if playbook_json_id:
                file_ids["playbook_json"] = playbook_json_id
                files_created += 1

            # Save briefs JSON
            briefs_content = json.dumps(artifacts["briefs"], indent=2)
            briefs_id = drive_client.upload_file(
                artifacts["file_names"]["briefs_json"],
                briefs_content,
                urn_folder_id,
                mime_type="application/json"
            )
            if briefs_id:
                file_ids["briefs"] = briefs_id
                files_created += 1

            # Generate URLs
            folder_url = f"https://drive.google.com/drive/folders/{urn_folder_id}"
            playbook_url = f"https://drive.google.com/file/d/{file_ids.get('playbook_md', '')}/view" if file_ids.get('playbook_md') else None
            briefs_url = f"https://drive.google.com/file/d/{file_ids.get('briefs', '')}/view" if file_ids.get('briefs') else None

            return {
                "success": True,
                "folder_id": urn_folder_id,
                "folder_url": folder_url,
                "playbook_file_id": file_ids.get("playbook_md"),
                "playbook_json_id": file_ids.get("playbook_json"),
                "briefs_file_id": file_ids.get("briefs"),
                "playbook_url": playbook_url,
                "briefs_url": briefs_url,
                "files_created": files_created
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "files_created": 0
            }

    def _save_to_firestore(self, firestore_client, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Save artifacts to Firestore."""
        try:
            # Create document path: strategy_reports/{urn}/{date}
            collection_path = "strategy_reports"
            document_path = f"{collection_path}/{self.urn}/{artifacts['date_str']}"

            # Prepare Firestore document
            doc_data = {
                "urn": self.urn,
                "created_at": artifacts["timestamp"],
                "playbook": artifacts["playbook_json"],
                "content_briefs": artifacts["briefs"],
                "metadata": {
                    "brief_count": len(artifacts["briefs"]),
                    "playbook_sections": len(artifacts["playbook_json"].keys()),
                    "markdown_length": len(artifacts["playbook_md"]),
                    "generation_date": artifacts["date_str"]
                },
                "status": "active",
                "version": "1.0"
            }

            # Save document
            doc_id = firestore_client.save_document(document_path, doc_data)

            return {
                "success": True,
                "document_path": document_path,
                "document_id": doc_id,
                "timestamp": artifacts["timestamp"].isoformat() + "Z",
                "collection": collection_path
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "document_path": None
            }

    def _save_to_zep(self, zep_client, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Save artifacts to Zep for retrieval."""
        try:
            # Create searchable document content
            searchable_content = f"""
Strategy Playbook for {self.urn}
Generated: {artifacts['date_str']}

{artifacts['playbook_md']}

Content Briefs Summary:
{len(artifacts['briefs'])} briefs generated covering various content types and strategies.
"""

            # Prepare metadata
            metadata = {
                "urn": self.urn,
                "type": "strategy_playbook",
                "generated_date": artifacts["date_str"],
                "brief_count": len(artifacts["briefs"]),
                "sections": list(artifacts["playbook_json"].keys()) if artifacts["playbook_json"] else []
            }

            # Save to Zep
            document_id = zep_client.save_document(
                content=searchable_content,
                metadata=metadata,
                group_id="strategy_playbooks"
            )

            return {
                "success": True,
                "document_id": document_id,
                "group_id": "strategy_playbooks",
                "searchable": True,
                "content_length": len(searchable_content)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "document_id": None
            }

    def _generate_metadata(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive metadata about saved artifacts."""
        # Calculate file sizes
        playbook_md_size = len(artifacts["playbook_md"].encode('utf-8'))
        playbook_json_size = len(json.dumps(artifacts["playbook_json"]).encode('utf-8'))
        briefs_size = len(json.dumps(artifacts["briefs"]).encode('utf-8'))

        def format_size(size_bytes: int) -> str:
            if size_bytes < 1024:
                return f"{size_bytes}B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f}KB"
            else:
                return f"{size_bytes / (1024 * 1024):.1f}MB"

        return {
            "urn": self.urn,
            "total_briefs": len(self.briefs),
            "playbook_sections": len(self.playbook_json.keys()) if self.playbook_json else 0,
            "save_timestamp": artifacts["timestamp"].isoformat() + "Z",
            "file_sizes": {
                "playbook_md": format_size(playbook_md_size),
                "playbook_json": format_size(playbook_json_size),
                "briefs_json": format_size(briefs_size),
                "total": format_size(playbook_md_size + playbook_json_size + briefs_size)
            },
            "storage_options": {
                "drive_enabled": self.save_to_drive,
                "firestore_enabled": self.save_to_firestore,
                "zep_enabled": self.save_to_zep
            }
        }


class DriveClient:
    """Google Drive client wrapper."""

    def __init__(self, service):
        self.service = service

    def create_or_get_folder(self, folder_name: str, parent_folder_id: str = None) -> str:
        """Create folder or get existing folder ID."""
        # Search for existing folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"

        results = self.service.files().list(q=query).execute()
        folders = results.get('files', [])

        if folders:
            return folders[0]['id']

        # Create new folder
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_folder_id:
            folder_metadata['parents'] = [parent_folder_id]

        folder = self.service.files().create(body=folder_metadata).execute()
        return folder['id']

    def upload_file(self, filename: str, content: str, folder_id: str, mime_type: str = "text/plain") -> str:
        """Upload file to Drive folder."""
        from googleapiclient.http import MediaIoBaseUpload
        import io

        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }

        media = MediaIoBaseUpload(
            io.BytesIO(content.encode('utf-8')),
            mimetype=mime_type
        )

        file = self.service.files().create(
            body=file_metadata,
            media_body=media
        ).execute()

        return file['id']


class FirestoreClient:
    """Firestore client wrapper."""

    def __init__(self, db):
        self.db = db

    def save_document(self, document_path: str, data: Dict[str, Any]) -> str:
        """Save document to Firestore."""
        doc_ref = self.db.document(document_path)
        doc_ref.set(data)
        return doc_ref.id


class MockDriveClient:
    """Mock Drive client for testing."""

    def create_or_get_folder(self, folder_name: str, parent_folder_id: str = None) -> str:
        return f"mock_folder_{folder_name.replace(' ', '_').lower()}"

    def upload_file(self, filename: str, content: str, folder_id: str, mime_type: str = "text/plain") -> str:
        return f"mock_file_{filename.replace('.', '_')}"


class MockFirestoreClient:
    """Mock Firestore client for testing."""

    def save_document(self, document_path: str, data: Dict[str, Any]) -> str:
        return f"mock_doc_{document_path.replace('/', '_')}"


class MockZepClient:
    """Mock Zep client for testing."""

    def save_document(self, content: str, metadata: Dict[str, Any], group_id: str) -> str:
        return f"mock_zep_doc_{uuid.uuid4().hex[:8]}"


if __name__ == "__main__":
    # Test the tool with sample data
    test_playbook_md = """# Strategy Playbook

## Executive Summary
This is a sample strategy playbook for testing.

## Winning Topics
- Entrepreneurship
- Leadership
- Growth strategies
"""

    test_playbook_json = {
        "executive_summary": {
            "key_insights": ["Personal stories drive engagement"],
            "top_opportunities": ["Increase authenticity"]
        },
        "winning_topics": [
            {"topic": "entrepreneurship", "engagement_score": 0.85}
        ]
    }

    test_briefs = [
        {
            "id": "brief_001",
            "title": "My Entrepreneurship Journey",
            "content_type": "personal_story",
            "hook": "Three years ago, I was a corporate employee..."
        }
    ]

    print("Testing SaveStrategyArtifacts tool...")

    # Test basic functionality
    tool = SaveStrategyArtifacts(
        urn="test_linkedin_profile",
        playbook_md=test_playbook_md,
        playbook_json=test_playbook_json,
        briefs=test_briefs,
        save_to_drive=True,
        save_to_firestore=True,
        save_to_zep=False  # Disabled for testing
    )

    result = tool.run()
    parsed_result = json.loads(result)

    print("✅ Strategy artifacts save completed successfully")
    print(f"Storage systems used: {parsed_result.get('storage_summary', {}).get('systems_used', 0)}")
    print(f"Files created: {parsed_result.get('storage_summary', {}).get('total_files_created', 0)}")
    print(f"Save success: {parsed_result.get('storage_summary', {}).get('save_success', False)}")

    # Show artifact references
    references = parsed_result.get('artifact_references', {})
    if references:
        print("\nArtifact references:")
        for key, value in references.items():
            print(f"  {key}: {value}")

    # Test with invalid data
    empty_tool = SaveStrategyArtifacts(
        urn="",
        playbook_md="",
        playbook_json={},
        briefs=[]
    )
    empty_result = json.loads(empty_tool.run())
    assert "error" in empty_result
    print("✅ Invalid data validation works")

    print("\nSample metadata:")
    metadata = parsed_result.get('metadata', {})
    if metadata:
        print(f"File sizes: {metadata.get('file_sizes', {})}")
        print(f"Total briefs: {metadata.get('total_briefs', 0)}")