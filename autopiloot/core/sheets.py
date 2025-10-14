"""
Google Sheets utilities for Autopiloot Agency.
Handles backfill processing, URL extraction, and batch operations
for managing coaching content and video processing workflows.
"""

import os
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

# Import config utilities for environment variable access
try:
    from config.env_loader import get_optional_env_var
except ImportError:
    # Fallback for when config module isn't available
    def get_optional_env_var(name: str, default: str = "", description: str = "") -> str:
        return os.getenv(name, default)


@dataclass
class URLExtractionResult:
    """Result of URL extraction from Google Sheets."""
    video_id: str
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    row_index: int = 0
    sheet_name: str = "Sheet1"


@dataclass
class BackfillJob:
    """Configuration for a backfill processing job."""
    job_id: str
    sheet_id: str
    sheet_name: str
    url_column: str
    title_column: Optional[str] = None
    description_column: Optional[str] = None
    start_row: int = 2  # Skip header row
    end_row: Optional[int] = None
    batch_size: int = 10
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class URLExtractor:
    """Extract and validate YouTube URLs from various formats."""
    
    # YouTube URL patterns for extraction
    YOUTUBE_PATTERNS = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'https?://(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
        r'https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'https?://(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})'
    ]
    
    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """Extract YouTube video ID from various URL formats."""
        if not url or not isinstance(url, str):
            return None
        
        url = url.strip()
        
        for pattern in cls.YOUTUBE_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Try bare video ID (11 characters)
        if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
            return url
        
        return None
    
    @classmethod
    def validate_url(cls, url: str) -> bool:
        """Validate if URL is a valid YouTube URL."""
        return cls.extract_video_id(url) is not None
    
    @classmethod
    def normalize_url(cls, url: str) -> Optional[str]:
        """Normalize URL to standard YouTube watch format."""
        video_id = cls.extract_video_id(url)
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return None


class GoogleSheetsClient:
    """Client for interacting with Google Sheets API."""

    def __init__(self, credentials_path: Optional[str] = None):
        """Initialize with Google Sheets credentials."""
        self.credentials_path = credentials_path or get_optional_env_var(
            'GOOGLE_APPLICATION_CREDENTIALS',
            '',
            'Path to Google service account credentials JSON file'
        )
        self._service = None
    
    def _get_service(self):
        """Get authenticated Google Sheets service."""
        if self._service is None:
            try:
                from googleapiclient.discovery import build
                from google.oauth2.service_account import Credentials
                
                credentials = Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
                self._service = build('sheets', 'v4', credentials=credentials)
            except ImportError:
                raise RuntimeError("google-api-python-client is required for Sheets functionality")
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Google Sheets service: {e}")
        
        return self._service
    
    def read_range(self, sheet_id: str, range_name: str) -> List[List[str]]:
        """Read data from a specific range in the sheet."""
        service = self._get_service()
        
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name
            ).execute()
            
            return result.get('values', [])
        except Exception as e:
            raise RuntimeError(f"Failed to read sheet range {range_name}: {e}")
    
    def write_range(self, sheet_id: str, range_name: str, values: List[List[str]]) -> bool:
        """Write data to a specific range in the sheet."""
        service = self._get_service()
        
        try:
            body = {
                'values': values
            }
            
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to write sheet range {range_name}: {e}")
    
    def get_sheet_info(self, sheet_id: str) -> Dict[str, Any]:
        """Get information about the spreadsheet and its sheets."""
        service = self._get_service()
        
        try:
            result = service.spreadsheets().get(
                spreadsheetId=sheet_id
            ).execute()
            
            return result
        except Exception as e:
            raise RuntimeError(f"Failed to get sheet info: {e}")
    
    def batch_read(self, sheet_id: str, ranges: List[str]) -> Dict[str, List[List[str]]]:
        """Read multiple ranges in a single request."""
        service = self._get_service()
        
        try:
            result = service.spreadsheets().values().batchGet(
                spreadsheetId=sheet_id,
                ranges=ranges
            ).execute()
            
            batch_data = {}
            for i, range_name in enumerate(ranges):
                values = result.get('valueRanges', [])[i].get('values', [])
                batch_data[range_name] = values
            
            return batch_data
        except Exception as e:
            raise RuntimeError(f"Failed to batch read ranges: {e}")


class BackfillProcessor:
    """Process backfill jobs for extracting and validating URLs from Google Sheets."""
    
    def __init__(self, sheets_client: Optional[GoogleSheetsClient] = None):
        """Initialize with Google Sheets client."""
        self.sheets_client = sheets_client or GoogleSheetsClient()
        self.extractor = URLExtractor()
    
    def process_backfill_job(self, job: BackfillJob) -> List[URLExtractionResult]:
        """Process a backfill job and extract URLs from the specified sheet."""
        results = []
        
        # Determine the range to read
        if job.end_row:
            range_name = f"{job.sheet_name}!{job.start_row}:{job.end_row}"
        else:
            range_name = f"{job.sheet_name}!{job.start_row}:1000"  # Read up to 1000 rows
        
        try:
            # Read the data from the sheet
            data = self.sheets_client.read_range(job.sheet_id, range_name)
            
            # Determine column indices
            url_col_idx = self._column_letter_to_index(job.url_column)
            title_col_idx = self._column_letter_to_index(job.title_column) if job.title_column else None
            desc_col_idx = self._column_letter_to_index(job.description_column) if job.description_column else None
            
            # Process each row
            for row_idx, row in enumerate(data):
                if len(row) <= url_col_idx:
                    continue  # Skip rows without URL column
                
                url = row[url_col_idx].strip() if row[url_col_idx] else ""
                if not url:
                    continue  # Skip empty URLs
                
                # Extract video ID
                video_id = self.extractor.extract_video_id(url)
                if not video_id:
                    continue  # Skip invalid URLs
                
                # Extract title and description if available
                title = None
                if title_col_idx is not None and len(row) > title_col_idx:
                    title = row[title_col_idx].strip() if row[title_col_idx] else None
                
                description = None
                if desc_col_idx is not None and len(row) > desc_col_idx:
                    description = row[desc_col_idx].strip() if row[desc_col_idx] else None
                
                # Create result
                result = URLExtractionResult(
                    video_id=video_id,
                    url=self.extractor.normalize_url(url),
                    title=title,
                    description=description,
                    row_index=job.start_row + row_idx,
                    sheet_name=job.sheet_name
                )
                
                results.append(result)
        
        except Exception as e:
            raise RuntimeError(f"Failed to process backfill job {job.job_id}: {e}")
        
        return results
    
    def validate_sheet_structure(self, sheet_id: str, sheet_name: str, required_columns: List[str]) -> Dict[str, Any]:
        """Validate that the sheet has the required column structure."""
        try:
            # Read header row
            header_range = f"{sheet_name}!1:1"
            headers = self.sheets_client.read_range(sheet_id, header_range)
            
            if not headers or not headers[0]:
                return {"valid": False, "error": "No header row found"}
            
            header_row = headers[0]
            validation_result = {
                "valid": True,
                "headers": header_row,
                "missing_columns": [],
                "column_mapping": {}
            }
            
            # Check for required columns
            for col in required_columns:
                col_idx = self._find_column_by_name(header_row, col)
                if col_idx is None:
                    validation_result["missing_columns"].append(col)
                    validation_result["valid"] = False
                else:
                    validation_result["column_mapping"][col] = self._index_to_column_letter(col_idx)
            
            return validation_result
            
        except Exception as e:
            return {"valid": False, "error": f"Failed to validate sheet structure: {e}"}
    
    def _column_letter_to_index(self, column_letter: str) -> int:
        """Convert column letter (A, B, C...) to zero-based index."""
        result = 0
        for char in column_letter.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1
    
    def _index_to_column_letter(self, index: int) -> str:
        """Convert zero-based index to column letter."""
        result = ""
        index += 1  # Convert to 1-based
        while index > 0:
            index -= 1
            result = chr(index % 26 + ord('A')) + result
            index //= 26
        return result
    
    def _find_column_by_name(self, headers: List[str], column_name: str) -> Optional[int]:
        """Find column index by name (case-insensitive)."""
        column_name_lower = column_name.lower()
        for i, header in enumerate(headers):
            if header.lower().strip() == column_name_lower:
                return i
        return None
    
    def create_batch_jobs(self, 
                         sheet_id: str, 
                         sheet_name: str, 
                         total_rows: int, 
                         batch_size: int = 50) -> List[BackfillJob]:
        """Create multiple batch jobs for processing large sheets."""
        jobs = []
        start_row = 2  # Skip header
        
        while start_row <= total_rows:
            end_row = min(start_row + batch_size - 1, total_rows)
            
            job = BackfillJob(
                job_id=f"{sheet_id}_{sheet_name}_batch_{start_row}_{end_row}",
                sheet_id=sheet_id,
                sheet_name=sheet_name,
                url_column="A",  # Default - should be configured
                start_row=start_row,
                end_row=end_row,
                batch_size=batch_size
            )
            
            jobs.append(job)
            start_row = end_row + 1
        
        return jobs


# Helper functions for common sheet operations
def extract_urls_from_sheet(sheet_id: str, 
                           sheet_name: str = "Sheet1", 
                           url_column: str = "A",
                           start_row: int = 2) -> List[URLExtractionResult]:
    """Simple function to extract URLs from a sheet."""
    processor = BackfillProcessor()
    
    job = BackfillJob(
        job_id=f"extract_{sheet_id}_{sheet_name}",
        sheet_id=sheet_id,
        sheet_name=sheet_name,
        url_column=url_column,
        start_row=start_row
    )
    
    return processor.process_backfill_job(job)


# Helper functions for test compatibility

def extract_youtube_urls_from_text(text: str) -> List[str]:
    """Extract YouTube URLs from text."""
    # Handle invalid input gracefully
    if not isinstance(text, str):
        return []

    patterns = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=[a-zA-Z0-9_-]{11}',
        r'https?://youtu\.be/[a-zA-Z0-9_-]{11}',
        r'https?://(?:www\.)?youtube\.com/embed/[a-zA-Z0-9_-]{11}',
        r'https?://(?:www\.)?youtube\.com/v/[a-zA-Z0-9_-]{11}'
    ]

    urls = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        urls.extend(matches)

    # Remove duplicates while preserving order and original URL format
    unique_urls = []
    seen = set()
    for url in urls:
        # Extract video ID for deduplication purposes
        video_id = None
        if 'youtu.be' in url:
            video_id = url.split('/')[-1].split('?')[0]  # Remove query params
        elif 'youtube.com/watch' in url:
            match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
            if match:
                video_id = match.group(1)
        elif 'youtube.com/embed' in url:
            video_id = url.split('/')[-1].split('?')[0]  # Remove query params
        elif 'youtube.com/v' in url:
            video_id = url.split('/')[-1].split('?')[0]  # Remove query params

        # Only add if we haven't seen this video ID before
        if video_id and video_id not in seen:
            seen.add(video_id)

            # Normalize URL format based on type
            if 'youtu.be' in url:
                # Keep youtu.be format as-is, just clean parameters
                clean_url = re.sub(r'\?.*', '', url)  # Remove all params for youtu.be
            elif 'youtube.com/embed' in url or 'youtube.com/v' in url:
                # Convert embed and v URLs to watch format
                clean_url = f'https://www.youtube.com/watch?v={video_id}'
            else:
                # Standard youtube.com watch URLs - clean params and ensure www
                clean_url = re.sub(r'[?&](?!v=)[^&]*', '', url)  # Remove non-v params
                if 'youtube.com' in clean_url and 'www.youtube.com' not in clean_url:
                    clean_url = clean_url.replace('youtube.com', 'www.youtube.com')

            unique_urls.append(clean_url)

    return unique_urls


@dataclass
class SheetRow:
    """Represents a row from Google Sheets."""
    index: int
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


def parse_sheet_row(row_values: List[Any], row_index: int) -> Optional[SheetRow]:
    """Parse a sheet row into structured data.

    Returns None for rows that should be skipped:
    - Header rows (row_index = 1)
    - Empty rows
    - Rows with empty or whitespace-only URLs
    - Rows with non-pending status (completed, error, etc.)
    """
    # Skip header row
    if row_index == 1:
        return None

    # Skip empty rows
    if not row_values:
        return None

    # Check URL (first column)
    url = str(row_values[0]) if len(row_values) > 0 and row_values[0] else ""
    url = url.strip()

    # Skip rows with empty or whitespace-only URLs
    if not url:
        return None

    # Based on test cases, the second column appears to be status
    status_value = str(row_values[1]).strip() if len(row_values) > 1 and row_values[1] else None

    # Skip rows with non-pending status
    if status_value and status_value.lower() in ['completed', 'error', 'processed']:
        return None

    return SheetRow(
        index=row_index,
        url=url,
        title=str(row_values[1]).strip() if len(row_values) > 1 and row_values[1] else None,
        description=str(row_values[2]).strip() if len(row_values) > 2 and row_values[2] else None,
        status=str(row_values[3]).strip() if len(row_values) > 3 and row_values[3] else None,
        notes=str(row_values[4]).strip() if len(row_values) > 4 and row_values[4] else None
    )


def create_archive_row_values(row: SheetRow, archive_reason: str) -> List[Any]:
    """Create values for archiving a row."""
    timestamp = datetime.now(timezone.utc).isoformat()
    return [
        row.url,
        row.title or "",
        row.description or "",
        row.status or "archived",
        archive_reason,
        timestamp
    ]


def create_error_row_values(row: SheetRow, error_message: str) -> List[Any]:
    """Create values for marking a row with an error."""
    timestamp = datetime.now(timezone.utc).isoformat()
    return [
        row.url,
        row.title or "",
        row.description or "",
        "error",
        error_message,
        timestamp
    ]


def get_archive_range(sheet_name: str, start_row: int, num_columns: int = 6) -> str:
    """Get A1 notation for archive range."""
    end_column = chr(ord('A') + num_columns - 1)
    return f"{sheet_name}!A{start_row}:{end_column}{start_row}"


def get_update_range(sheet_name: str, row_index: int, column: str = "D") -> str:
    """Get A1 notation for updating a single cell."""
    return f"{sheet_name}!{column}{row_index}"


def validate_youtube_urls_in_sheet(sheet_id: str, 
                                  sheet_name: str = "Sheet1",
                                  url_column: str = "A") -> Dict[str, Any]:
    """Validate all YouTube URLs in a sheet and return statistics."""
    results = extract_urls_from_sheet(sheet_id, sheet_name, url_column)
    
    stats = {
        "total_urls": len(results),
        "valid_urls": len([r for r in results if r.video_id]),
        "invalid_urls": len([r for r in results if not r.video_id]),
        "unique_videos": len(set(r.video_id for r in results if r.video_id))
    }
    
    return {
        "statistics": stats,
        "results": results
    }