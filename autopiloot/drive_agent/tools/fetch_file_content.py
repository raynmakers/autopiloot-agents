"""
Fetch Google Drive file content for supported MIME types
Handles direct downloads and exports with size limits and text extraction
"""

import os
import json
import sys
import io
from typing import Dict, Any, Optional
from pydantic import Field
from agency_swarm.tools import BaseTool
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import mimetypes

# Add config directory to path
from env_loader import get_required_env_var
from loader import get_config_value

# Optional imports for content extraction
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class FetchFileContent(BaseTool):
    """
    Fetch content from Google Drive files with support for various MIME types.
    Handles direct downloads, Google Workspace exports, and text extraction.
    """

    file_id: str = Field(
        ...,
        description="Google Drive file ID to fetch content from"
    )

    max_size_mb: Optional[float] = Field(
        default=None,
        description="Maximum file size in MB to process. If None, uses config default."
    )

    extract_text_only: bool = Field(
        default=True,
        description="Whether to extract only text content (true) or return raw bytes (false)"
    )

    include_metadata: bool = Field(
        default=True,
        description="Whether to include file metadata in the response"
    )

    def _get_drive_service(self):
        """Initialize Google Drive API service."""
        try:
            # Get credentials path from environment
            creds_path = get_required_env_var("GOOGLE_APPLICATION_CREDENTIALS")

            # Create credentials from service account file
            credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )

            # Build Drive service
            service = build('drive', 'v3', credentials=credentials)
            return service
        except Exception as e:
            raise Exception(f"Failed to initialize Drive service: {str(e)}")

    def _get_size_limit(self) -> int:
        """Get file size limit in bytes."""
        if self.max_size_mb is not None:
            return int(self.max_size_mb * 1024 * 1024)

        # Get from config
        drive_config = get_config_value("drive", {})
        tracking_config = drive_config.get("tracking", {})
        max_size_mb = tracking_config.get("max_file_size_mb", 10)
        return int(max_size_mb * 1024 * 1024)

    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes."""
        if not PDF_AVAILABLE:
            return "[PDF text extraction not available - PyPDF2 not installed]"

        try:
            pdf_file = io.BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            text_content = []
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():
                        text_content.append(f"--- Page {page_num + 1} ---\n{page_text}")
                except Exception as e:
                    text_content.append(f"--- Page {page_num + 1} ---\n[Error extracting text: {str(e)}]")

            return "\n\n".join(text_content) if text_content else "[No text content found in PDF]"

        except Exception as e:
            return f"[Error processing PDF: {str(e)}]"

    def _extract_text_from_docx(self, docx_bytes: bytes) -> str:
        """Extract text from DOCX bytes."""
        if not DOCX_AVAILABLE:
            return "[DOCX text extraction not available - python-docx not installed]"

        try:
            docx_file = io.BytesIO(docx_bytes)
            doc = Document(docx_file)

            text_content = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text)

            return "\n".join(text_content) if text_content else "[No text content found in DOCX]"

        except Exception as e:
            return f"[Error processing DOCX: {str(e)}]"

    def _get_export_mime_type(self, original_mime_type: str) -> Optional[str]:
        """Get the appropriate export MIME type for Google Workspace files."""
        export_map = {
            'application/vnd.google-apps.document': 'text/plain',  # Google Docs to plain text
            'application/vnd.google-apps.spreadsheet': 'text/csv',  # Sheets to CSV
            'application/vnd.google-apps.presentation': 'text/plain',  # Slides to plain text
            'application/vnd.google-apps.drawing': 'image/png',  # Drawings to PNG
        }
        return export_map.get(original_mime_type)

    def _download_file_content(self, service, file_id: str, mime_type: str) -> tuple[bytes, str]:
        """Download file content, handling both direct downloads and exports."""

        # Check if it's a Google Workspace file that needs export
        export_mime_type = self._get_export_mime_type(mime_type)

        if export_mime_type:
            # Export Google Workspace file
            request = service.files().export_media(fileId=file_id, mimeType=export_mime_type)
            actual_mime_type = export_mime_type
        else:
            # Direct download for regular files
            request = service.files().get_media(fileId=file_id)
            actual_mime_type = mime_type

        # Execute download
        file_content = request.execute()
        return file_content, actual_mime_type

    def _process_content(self, content_bytes: bytes, mime_type: str) -> str:
        """Process file content based on MIME type and extraction settings."""

        if not self.extract_text_only:
            # Return base64 encoded content for binary files
            return base64.b64encode(content_bytes).decode('utf-8')

        # Text extraction based on MIME type
        if mime_type.startswith('text/') or mime_type in ['text/plain', 'text/csv', 'text/html']:
            # Plain text files
            try:
                # Try different encodings
                for encoding in ['utf-8', 'utf-16', 'latin-1']:
                    try:
                        return content_bytes.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                return content_bytes.decode('utf-8', errors='replace')
            except Exception as e:
                return f"[Error decoding text: {str(e)}]"

        elif mime_type == 'application/pdf':
            # PDF text extraction
            return self._extract_text_from_pdf(content_bytes)

        elif mime_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            # DOCX text extraction
            return self._extract_text_from_docx(content_bytes)

        elif mime_type.startswith('application/vnd.google-apps'):
            # Google Workspace files should have been exported to text
            try:
                return content_bytes.decode('utf-8')
            except UnicodeDecodeError:
                return content_bytes.decode('utf-8', errors='replace')

        else:
            # Unsupported MIME type for text extraction
            if self.extract_text_only:
                return f"[Text extraction not supported for MIME type: {mime_type}]"
            else:
                return base64.b64encode(content_bytes).decode('utf-8')

    def run(self) -> str:
        """
        Fetch content from the specified Google Drive file.

        Returns:
            JSON string containing file content and metadata
        """
        try:
            # Initialize Drive service
            service = self._get_drive_service()

            # Get file metadata first
            try:
                file_metadata = service.files().get(
                    fileId=self.file_id,
                    fields="id, name, mimeType, size, modifiedTime, version, owners, webViewLink, parents"
                ).execute()
            except HttpError as e:
                if e.resp.status == 404:
                    return json.dumps({
                        "error": "file_not_found",
                        "message": f"File with ID {self.file_id} not found"
                    })
                elif e.resp.status == 403:
                    return json.dumps({
                        "error": "access_denied",
                        "message": f"Permission denied for file {self.file_id}"
                    })
                raise

            # Check if it's a folder
            if file_metadata.get('mimeType') == 'application/vnd.google-apps.folder':
                return json.dumps({
                    "error": "unsupported_type",
                    "message": "Cannot fetch content from folders"
                })

            # Check file size
            file_size = int(file_metadata.get('size', 0))
            size_limit = self._get_size_limit()

            # Google Workspace files don't have size, so we skip the check for them
            if file_size > 0 and file_size > size_limit:
                return json.dumps({
                    "error": "file_too_large",
                    "message": f"File size ({file_size / 1024 / 1024:.1f} MB) exceeds limit ({size_limit / 1024 / 1024:.1f} MB)",
                    "file_size_bytes": file_size,
                    "limit_bytes": size_limit
                })

            # Download/export file content
            try:
                content_bytes, actual_mime_type = self._download_file_content(
                    service,
                    self.file_id,
                    file_metadata.get('mimeType')
                )
            except HttpError as e:
                if e.resp.status == 403:
                    return json.dumps({
                        "error": "export_denied",
                        "message": "File export/download not permitted"
                    })
                elif e.resp.status == 404:
                    return json.dumps({
                        "error": "export_not_available",
                        "message": "File content not available for download"
                    })
                else:
                    return json.dumps({
                        "error": "download_error",
                        "message": f"Failed to download file: {str(e)}"
                    })

            # Process content
            processed_content = self._process_content(content_bytes, actual_mime_type)

            # Build result
            result = {
                "file_id": self.file_id,
                "content": processed_content,
                "content_type": "text" if self.extract_text_only else "base64",
                "mime_type": actual_mime_type,
                "original_mime_type": file_metadata.get('mimeType'),
                "content_length": len(processed_content),
                "raw_size_bytes": len(content_bytes)
            }

            # Add metadata if requested
            if self.include_metadata:
                result["metadata"] = {
                    "name": file_metadata.get('name'),
                    "size": file_size,
                    "modifiedTime": file_metadata.get('modifiedTime'),
                    "version": file_metadata.get('version'),
                    "webViewLink": file_metadata.get('webViewLink')
                }

                # Add parent folder info
                if 'parents' in file_metadata and file_metadata['parents']:
                    result["metadata"]["parent_folder_id"] = file_metadata['parents'][0]

                # Add owner info if available
                if 'owners' in file_metadata and file_metadata['owners']:
                    result["metadata"]["owner"] = file_metadata['owners'][0].get('emailAddress', 'unknown')

            return json.dumps(result)

        except Exception as e:
            return json.dumps({
                "error": "fetch_error",
                "message": f"Failed to fetch file content: {str(e)}",
                "details": {
                    "file_id": self.file_id,
                    "type": type(e).__name__
                }
            })


if __name__ == "__main__":
    # Test the tool
    print("Testing FetchFileContent tool...")

    # Test file ID (replace with valid ID for testing)
    test_file_id = os.environ.get("TEST_DRIVE_FILE_ID", "example_file_id_here")

    # Test 1: Fetch text content with metadata
    print(f"\n1. Testing text content fetch for ID: {test_file_id}")
    tool = FetchFileContent(
        file_id=test_file_id,
        extract_text_only=True,
        include_metadata=True,
        max_size_mb=5.0
    )
    result = tool.run()
    result_json = json.loads(result)

    if "error" not in result_json:
        print("Success! Content summary:")
        print(f"  Content type: {result_json.get('content_type')}")
        print(f"  MIME type: {result_json.get('mime_type')}")
        print(f"  Content length: {result_json.get('content_length')} characters")
        print(f"  Raw size: {result_json.get('raw_size_bytes')} bytes")

        if "metadata" in result_json:
            metadata = result_json["metadata"]
            print(f"  File name: {metadata.get('name')}")
            print(f"  Modified: {metadata.get('modifiedTime')}")

        # Show first 200 characters of content
        content = result_json.get('content', '')
        if len(content) > 200:
            print(f"  Content preview: {content[:200]}...")
        else:
            print(f"  Content: {content}")
    else:
        print(f"Error: {result_json.get('error')}")
        print(f"Message: {result_json.get('message')}")

    # Test 2: Fetch binary content (base64)
    print(f"\n2. Testing binary content fetch for ID: {test_file_id}")
    tool = FetchFileContent(
        file_id=test_file_id,
        extract_text_only=False,
        include_metadata=False,
        max_size_mb=1.0
    )
    result = tool.run()
    result_json = json.loads(result)

    if "error" not in result_json:
        print("Success! Binary content summary:")
        print(f"  Content type: {result_json.get('content_type')}")
        print(f"  MIME type: {result_json.get('mime_type')}")
        print(f"  Content length: {result_json.get('content_length')} characters (base64)")
        print(f"  Raw size: {result_json.get('raw_size_bytes')} bytes")
    else:
        print(f"Error: {result_json.get('error')}")
        print(f"Message: {result_json.get('message')}")

    # Test 3: Size limit test
    print(f"\n3. Testing size limit (0.1MB) for ID: {test_file_id}")
    tool = FetchFileContent(
        file_id=test_file_id,
        max_size_mb=0.1
    )
    result = tool.run()
    result_json = json.loads(result)

    if "error" in result_json:
        print(f"Expected size limit error: {result_json.get('error')}")
        print(f"Message: {result_json.get('message')}")
    else:
        print("File was within size limit")
        print(f"Content length: {result_json.get('content_length')} characters")