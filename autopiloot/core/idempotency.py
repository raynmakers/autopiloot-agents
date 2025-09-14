"""
Idempotency utilities for Autopiloot agents.
Ensures no duplicate processing across video discovery, transcription, and summarization.
"""

from typing import TypedDict, List, Literal, Optional
from datetime import datetime
import re


# Type definitions from task specification
VideoStatus = Literal["discovered", "transcribed", "summarized"]


class DriveIds(TypedDict):
    """Drive file IDs for transcript files."""
    txt: str
    json: str


class FileNamingSpec(TypedDict):
    """Specification for standardized Drive file naming."""
    video_id: str
    date_yyyy_mm_dd: str
    type: Literal["transcript_txt", "transcript_json", "summary_md", "summary_json"]


class VideoRecord(TypedDict, total=False):
    """Complete video record structure from Firestore."""
    video_id: str
    url: str
    title: str
    published_at: str  # ISO8601 UTC
    channel_id: str
    duration_sec: int
    source: Literal["scrape", "sheet"]
    status: VideoStatus
    created_at: str
    updated_at: str


class TranscriptRecord(TypedDict, total=False):
    """Transcript record structure from Firestore."""
    video_id: str
    transcript_drive_ids: DriveIds
    digest: str
    created_at: str
    costs: dict  # {"transcription_usd": float}


class SummaryRecord(TypedDict, total=False):
    """Summary record structure from Firestore."""
    video_id: str
    short: dict  # {"zep_doc_id": str, "drive_id": str, "prompt_id": str, "token_usage": dict}
    linkage: dict  # {"transcript_doc_ref": str, "transcript_drive_id_txt": str, "transcript_drive_id_json": str}
    rag_refs: List[str]
    created_at: str


def extract_video_id_from_url(video_url: str) -> Optional[str]:
    """
    Extract YouTube video ID from various URL formats.
    
    Args:
        video_url: YouTube URL in various formats
        
    Returns:
        Video ID string or None if not found
        
    Examples:
        >>> extract_video_id_from_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
        >>> extract_video_id_from_url("https://youtu.be/dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
    """
    if not video_url or not isinstance(video_url, str):
        return None
    
    # Handle different YouTube URL formats
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?.*[&?]v=([a-zA-Z0-9_-]{11})',
        r'(?:^|.*/)([a-zA-Z0-9_-]{11})(?:\?.*)?$',  # For youtu.be/ID format without protocol
    ]
    
    for pattern in patterns:
        match = re.search(pattern, video_url)
        if match:
            return match.group(1)
    
    return None


def generate_drive_filename(spec: FileNamingSpec) -> str:
    """
    Generate standardized Drive filename according to naming convention.
    
    Format: <video_id>_<yyyy-mm-dd>_<type>.{extension}
    
    Args:
        spec: FileNamingSpec with video_id, date, and type
        
    Returns:
        Standardized filename string
        
    Examples:
        >>> spec = {"video_id": "dQw4w9WgXcQ", "date_yyyy_mm_dd": "2025-01-27", "type": "transcript_txt"}
        >>> generate_drive_filename(spec)
        'dQw4w9WgXcQ_2025-01-27_transcript_txt.txt'
    """
    # Map type to file extension
    extension_map = {
        "transcript_txt": "txt",
        "transcript_json": "json", 
        "summary_md": "md",
        "summary_json": "json"
    }
    
    file_type = spec["type"]
    extension = extension_map.get(file_type, "txt")
    
    # Format: video_id_yyyy-mm-dd_type.extension
    filename = f"{spec['video_id']}_{spec['date_yyyy_mm_dd']}_{file_type}.{extension}"
    
    return filename


def is_video_processed(video_record: Optional[VideoRecord], target_status: VideoStatus) -> bool:
    """
    Check if video has already been processed to the target status or beyond.
    
    Args:
        video_record: Video record from Firestore, or None if not found
        target_status: Minimum status required
        
    Returns:
        True if video is already processed to target status or beyond
        
    Examples:
        >>> record = {"status": "transcribed", "video_id": "test"}
        >>> is_video_processed(record, "discovered")
        True
        >>> is_video_processed(record, "summarized") 
        False
        >>> is_video_processed(None, "discovered")
        False
    """
    if not video_record:
        return False
    
    current_status = video_record.get("status")
    if not current_status:
        return False
    
    # Status progression: discovered -> transcribed -> summarized
    status_order = {"discovered": 1, "transcribed": 2, "summarized": 3}
    
    current_level = status_order.get(current_status, 0)
    target_level = status_order.get(target_status, 0)
    
    return current_level >= target_level


def should_skip_transcription(video_record: Optional[VideoRecord], transcript_record: Optional[TranscriptRecord] = None) -> bool:
    """
    Determine if transcription should be skipped for a video.
    
    Args:
        video_record: Video record from Firestore
        transcript_record: Existing transcript record, if any
        
    Returns:
        True if transcription should be skipped
        
    Reasons to skip:
        - Video already transcribed (status >= "transcribed")
        - Transcript record already exists
        - Video duration > 70 minutes (4200 seconds)
    """
    if not video_record:
        return True
    
    # Check if already transcribed
    if is_video_processed(video_record, "transcribed"):
        return True
    
    # Check if transcript record exists
    if transcript_record:
        return True
    
    # Check duration limit (70 minutes = 4200 seconds)
    duration_sec = video_record.get("duration_sec", 0)
    if duration_sec > 4200:
        return True
    
    return False


def should_skip_summarization(video_record: Optional[VideoRecord], summary_record: Optional[SummaryRecord] = None) -> bool:
    """
    Determine if summarization should be skipped for a video.
    
    Args:
        video_record: Video record from Firestore
        summary_record: Existing summary record, if any
        
    Returns:
        True if summarization should be skipped
        
    Reasons to skip:
        - Video already summarized (status >= "summarized")
        - Summary record already exists
        - Video not yet transcribed
    """
    if not video_record:
        return True
    
    # Check if already summarized
    if is_video_processed(video_record, "summarized"):
        return True
    
    # Check if summary record exists
    if summary_record:
        return True
    
    # Check if video is transcribed (prerequisite)
    if not is_video_processed(video_record, "transcribed"):
        return True
    
    return False


def get_date_for_filename(published_at: Optional[str] = None) -> str:
    """
    Get formatted date string for filename generation.
    
    Args:
        published_at: ISO8601 UTC timestamp, or None for current date
        
    Returns:
        Date string in YYYY-MM-DD format
        
    Examples:
        >>> get_date_for_filename("2025-01-27T13:45:00Z")
        '2025-01-27'
        >>> get_date_for_filename(None)  # Returns current date
        '2025-01-27'
    """
    if published_at:
        try:
            # Parse ISO8601 UTC timestamp
            dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        except (ValueError, AttributeError):
            pass
    
    # Fallback to current date
    return datetime.utcnow().strftime('%Y-%m-%d')


def create_idempotency_key(video_id: str, operation_type: str) -> str:
    """
    Create a unique idempotency key for tracking operations.
    
    Args:
        video_id: YouTube video ID
        operation_type: Type of operation (e.g., "transcription", "summarization")
        
    Returns:
        Idempotency key string
        
    Examples:
        >>> create_idempotency_key("dQw4w9WgXcQ", "transcription")
        'dQw4w9WgXcQ:transcription'
    """
    return f"{video_id}:{operation_type}"


if __name__ == "__main__":
    # Test the functions
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    video_id = extract_video_id_from_url(test_url)
    print(f"Extracted video ID: {video_id}")
    
    spec: FileNamingSpec = {
        "video_id": "dQw4w9WgXcQ",
        "date_yyyy_mm_dd": "2025-01-27", 
        "type": "transcript_txt"
    }
    filename = generate_drive_filename(spec)
    print(f"Generated filename: {filename}")
    
    # Test status checking
    video_record: VideoRecord = {
        "video_id": "test",
        "status": "transcribed",
        "duration_sec": 3000
    }
    
    print(f"Should skip transcription: {should_skip_transcription(video_record)}")
    print(f"Should skip summarization: {should_skip_summarization(video_record)}")
    
    print(f"Date for filename: {get_date_for_filename('2025-01-27T13:45:00Z')}")
    print(f"Idempotency key: {create_idempotency_key('test123', 'transcription')}")
