"""
Google Sheets processing utilities for Autopiloot agents.
Handles reading, updating, and archiving sheet rows for video ingestion.
"""

from typing import TypedDict, List, Optional, Dict, Any
from datetime import datetime
import re


class SheetRow(TypedDict):
    """Represents a row from the Google Sheet."""
    url: str
    status: str
    notes: Optional[str]
    processed_at: Optional[str]


class SheetLink(TypedDict):
    """Represents an extracted link from a sheet row."""
    source_page_url: str
    video_url: str


class ReadSheetLinksRequest(TypedDict):
    """Request for reading sheet links."""
    sheet_id: str
    range_a1: str


class ReadSheetLinksResponse(TypedDict):
    """Response containing extracted sheet links."""
    items: List[SheetLink]


class ProcessSheetResult(TypedDict):
    """Result of processing a sheet row."""
    success: bool
    video_ids: List[str]
    error_message: Optional[str]


def extract_youtube_urls_from_text(text: str) -> List[str]:
    """
    Extract YouTube URLs from text content.
    
    Args:
        text: Text content to search for YouTube URLs
        
    Returns:
        List of YouTube URLs found in the text
        
    Examples:
        >>> extract_youtube_urls_from_text("Check out https://youtu.be/dQw4w9WgXcQ")
        ['https://youtu.be/dQw4w9WgXcQ']
    """
    if not text or not isinstance(text, str):
        return []
    
    # YouTube URL patterns
    patterns = [
        r'https?://(?:www\.)?youtube\.com/watch\?[^\s]*v=([a-zA-Z0-9_-]{11})[^\s]*',
        r'https?://youtu\.be/([a-zA-Z0-9_-]{11})[^\s]*',
        r'https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})[^\s]*',
    ]
    
    video_ids_seen = set()
    urls = []
    
    for pattern in patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            video_id = match.group(1)
            
            # Skip if we've already seen this video ID
            if video_id in video_ids_seen:
                continue
                
            video_ids_seen.add(video_id)
            
            # Reconstruct the full URL based on the original format
            if 'youtu.be' in match.group(0):
                url = f"https://youtu.be/{video_id}"
            else:
                url = f"https://www.youtube.com/watch?v={video_id}"
            
            urls.append(url)
    
    return urls


def parse_sheet_row(row_values: List[str], row_index: int) -> Optional[SheetRow]:
    """
    Parse a sheet row into a SheetRow object.
    
    Args:
        row_values: List of cell values from the sheet row
        row_index: 1-based row index in the sheet
        
    Returns:
        SheetRow object or None if row is invalid
        
    Expected columns: A=url, B=status, C=notes, D=processed_at
    """
    if not row_values or len(row_values) == 0:
        return None
    
    # Skip header row
    if row_index == 1:
        return None
    
    # Get values with defaults
    url = row_values[0] if len(row_values) > 0 else ""
    status = row_values[1] if len(row_values) > 1 else "pending"
    notes = row_values[2] if len(row_values) > 2 else None
    processed_at = row_values[3] if len(row_values) > 3 else None
    
    # Skip empty rows
    if not url.strip():
        return None
    
    # Only process pending rows
    if status.strip().lower() != "pending":
        return None
    
    return SheetRow(
        url=url.strip(),
        status=status.strip(),
        notes=notes.strip() if notes and notes.strip() else None,
        processed_at=processed_at.strip() if processed_at and processed_at.strip() else None
    )


def create_archive_row_values(sheet_row: SheetRow, video_ids: List[str]) -> List[str]:
    """
    Create values for archiving a processed row.
    
    Args:
        sheet_row: Original sheet row
        video_ids: List of video IDs that were processed
        
    Returns:
        List of values for the archive row
    """
    processed_at = datetime.utcnow().isoformat() + "Z"
    notes = f"Processed {len(video_ids)} video(s): {', '.join(video_ids)}" if video_ids else "No videos found"
    
    return [
        sheet_row["url"],
        "completed",
        notes,
        processed_at
    ]


def create_error_row_values(sheet_row: SheetRow, error_message: str) -> List[str]:
    """
    Create values for updating a row with error status.
    
    Args:
        sheet_row: Original sheet row
        error_message: Error message to include
        
    Returns:
        List of values for the error row
    """
    processed_at = datetime.utcnow().isoformat() + "Z"
    
    return [
        sheet_row["url"],
        "error",
        error_message,
        processed_at
    ]


def get_archive_range(row_count: int) -> str:
    """
    Get the A1 notation range for appending to the archive sheet.
    
    Args:
        row_count: Number of existing rows in archive
        
    Returns:
        A1 notation range for the next row
    """
    next_row = row_count + 1
    return f"Archive!A{next_row}:D{next_row}"


def get_update_range(row_index: int) -> str:
    """
    Get the A1 notation range for updating a specific row.
    
    Args:
        row_index: 1-based row index to update
        
    Returns:
        A1 notation range for the row
    """
    return f"Sheet1!A{row_index}:D{row_index}"


if __name__ == "__main__":
    # Test the functions
    test_text = "Check out this video: https://youtu.be/dQw4w9WgXcQ and also https://www.youtube.com/watch?v=abc123def45"
    urls = extract_youtube_urls_from_text(test_text)
    print(f"Extracted URLs: {urls}")
    
    # Test row parsing
    test_row = ["https://example.com/page", "pending", "", ""]
    parsed = parse_sheet_row(test_row, 2)
    print(f"Parsed row: {parsed}")
    
    # Test archive values
    if parsed:
        archive_values = create_archive_row_values(parsed, ["dQw4w9WgXcQ"])
        print(f"Archive values: {archive_values}")
