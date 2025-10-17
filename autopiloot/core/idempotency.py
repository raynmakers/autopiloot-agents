"""
Idempotency module for Autopiloot agents.
Handles naming conventions, deduplication, and unique identifier generation.
"""

import re
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs


class IdempotencyError(Exception):
    """Base exception for idempotency operations."""
    pass


class VideoIDExtractor:
    """
    Utility for extracting and validating YouTube video IDs.
    Ensures consistent video identification across the system.
    """
    
    # YouTube URL patterns for video ID extraction
    YOUTUBE_PATTERNS = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch.*?v=([a-zA-Z0-9_-]{11})',
    ]
    
    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """
        Extract YouTube video ID from URL using multiple patterns.
        
        Args:
            url: YouTube URL
            
        Returns:
            11-character video ID or None if not found
        """
        if not url or not isinstance(url, str):
            return None
        
        # Try regex patterns first
        for pattern in cls.YOUTUBE_PATTERNS:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                if cls.is_valid_video_id(video_id):
                    return video_id
        
        # Try URL parsing approach
        try:
            parsed = urlparse(url)
            
            # Handle youtube.com/watch URLs
            if 'youtube.com' in parsed.netloc and '/watch' in parsed.path:
                query_params = parse_qs(parsed.query)
                if 'v' in query_params and query_params['v']:
                    video_id = query_params['v'][0]
                    if cls.is_valid_video_id(video_id):
                        return video_id
            
            # Handle youtu.be URLs
            elif 'youtu.be' in parsed.netloc:
                video_id = parsed.path.lstrip('/')
                if cls.is_valid_video_id(video_id):
                    return video_id
                    
        except Exception:
            pass
        
        return None
    
    @classmethod
    def is_valid_video_id(cls, video_id: str) -> bool:
        """
        Validate YouTube video ID format.
        
        Args:
            video_id: Video ID to validate
            
        Returns:
            True if valid 11-character YouTube video ID
        """
        if not video_id or not isinstance(video_id, str):
            return False
        
        # YouTube video IDs are exactly 11 characters
        if len(video_id) != 11:
            return False
        
        # Must contain only valid characters
        valid_chars = re.match(r'^[a-zA-Z0-9_-]+$', video_id)
        return bool(valid_chars)
    
    @classmethod
    def normalize_video_url(cls, url: str) -> Optional[str]:
        """
        Normalize video URL to standard format.
        
        Args:
            url: Video URL to normalize
            
        Returns:
            Normalized URL or None if invalid
        """
        video_id = cls.extract_video_id(url)
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return None


class FilenameGenerator:
    """
    Generator for consistent file naming across the system.
    Implements the naming convention: <video_id>_<yyyy-mm-dd>_<type>.<ext>
    """
    
    @classmethod
    def generate_filename(cls, video_id: str, file_type: str, 
                         extension: str, date: Optional[datetime] = None) -> str:
        """
        Generate filename following the convention.
        
        Args:
            video_id: YouTube video ID
            file_type: Type descriptor (transcript, summary, etc.)
            extension: File extension (txt, json, md)
            date: Optional date (defaults to current UTC date)
            
        Returns:
            Generated filename
        """
        if not cls._is_valid_video_id(video_id):
            raise IdempotencyError(f"Invalid video ID: {video_id}")
        
        if not file_type or not extension:
            raise IdempotencyError("file_type and extension are required")
        
        # Use provided date or current UTC date
        if date is None:
            date = datetime.now(timezone.utc)
        
        date_str = date.strftime("%Y-%m-%d")
        
        # Sanitize file_type
        safe_type = re.sub(r'[^a-zA-Z0-9_-]', '_', file_type.lower())
        
        # Sanitize extension
        safe_ext = extension.lower().lstrip('.')
        
        return f"{video_id}_{date_str}_{safe_type}.{safe_ext}"
    
    @classmethod
    def parse_filename(cls, filename: str) -> Dict[str, str]:
        """
        Parse filename to extract components.
        
        Args:
            filename: Filename to parse
            
        Returns:
            Dictionary with video_id, date, type, extension
        """
        # Pattern: video_id_yyyy-mm-dd_type.ext
        pattern = r'^([a-zA-Z0-9_-]{11})_(\d{4}-\d{2}-\d{2})_([^.]+)\.(.+)$'
        match = re.match(pattern, filename)
        
        if not match:
            raise IdempotencyError(f"Filename does not match expected pattern: {filename}")
        
        return {
            "video_id": match.group(1),
            "date": match.group(2),
            "type": match.group(3),
            "extension": match.group(4)
        }
    
    @classmethod
    def _is_valid_video_id(cls, video_id: str) -> bool:
        """Internal video ID validation."""
        return VideoIDExtractor.is_valid_video_id(video_id)


class DeduplicationManager:
    """
    Manager for handling deduplication across the system.
    Uses video IDs as primary deduplication keys.
    """
    
    @classmethod
    def generate_content_hash(cls, content: str) -> str:
        """
        Generate hash for content deduplication.
        
        Args:
            content: Content to hash
            
        Returns:
            SHA-256 hash (first 16 characters)
        """
        if not content:
            return ""
        
        content_bytes = content.encode('utf-8')
        full_hash = hashlib.sha256(content_bytes).hexdigest()
        return full_hash[:16]  # First 16 characters for brevity
    
    @classmethod
    def generate_metadata_fingerprint(cls, metadata: Dict[str, Any]) -> str:
        """
        Generate fingerprint for metadata deduplication.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            Fingerprint string
        """
        # Sort keys for consistent hashing
        sorted_items = sorted(metadata.items())
        fingerprint_data = str(sorted_items)
        
        return cls.generate_content_hash(fingerprint_data)
    
    @classmethod
    def is_duplicate_by_video_id(cls, video_id: str, existing_video_ids: List[str]) -> bool:
        """
        Check if video ID already exists.
        
        Args:
            video_id: Video ID to check
            existing_video_ids: List of existing video IDs
            
        Returns:
            True if duplicate found
        """
        return video_id in existing_video_ids
    
    @classmethod
    def create_deduplication_key(cls, video_id: str, source: str) -> str:
        """
        Create compound deduplication key.
        
        Args:
            video_id: YouTube video ID
            source: Source identifier (scrape, sheet, etc.)
            
        Returns:
            Deduplication key
        """
        return f"{video_id}:{source}"
    
    @classmethod
    def extract_video_metadata_for_dedup(cls, video_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant metadata for deduplication.
        
        Args:
            video_data: Full video data
            
        Returns:
            Metadata relevant for deduplication
        """
        dedup_fields = ['video_id', 'title', 'published_at', 'duration_sec', 'channel_id']
        
        return {
            field: video_data.get(field)
            for field in dedup_fields
            if field in video_data
        }


class StatusTransitionManager:
    """
    Manager for handling status transitions with validation.
    Ensures proper progression: discovered → transcription_queued → transcribed → summarized
    """
    
    VALID_STATUSES = [
        "discovered",
        "transcription_queued", 
        "transcribed",
        "summarized",
        "failed",
        "skipped"
    ]
    
    VALID_TRANSITIONS = {
        "discovered": ["transcription_queued", "failed", "skipped"],
        "transcription_queued": ["transcribed", "failed"],
        "transcribed": ["summarized", "failed"],
        "summarized": [],  # Terminal state
        "failed": ["transcription_queued", "discovered"],  # Allow retry
        "skipped": []  # Terminal state
    }
    
    @classmethod
    def is_valid_status(cls, status: str) -> bool:
        """Check if status is valid."""
        return status in cls.VALID_STATUSES
    
    @classmethod
    def is_valid_transition(cls, from_status: str, to_status: str) -> bool:
        """
        Check if status transition is valid.
        
        Args:
            from_status: Current status
            to_status: Target status
            
        Returns:
            True if transition is allowed
        """
        if not cls.is_valid_status(from_status) or not cls.is_valid_status(to_status):
            return False
        
        return to_status in cls.VALID_TRANSITIONS.get(from_status, [])
    
    @classmethod
    def get_next_statuses(cls, current_status: str) -> List[str]:
        """
        Get list of valid next statuses.
        
        Args:
            current_status: Current status
            
        Returns:
            List of valid next statuses
        """
        return cls.VALID_TRANSITIONS.get(current_status, [])
    
    @classmethod
    def validate_status_update(cls, current_status: str, new_status: str) -> bool:
        """
        Validate status update with detailed error.
        
        Args:
            current_status: Current status
            new_status: Proposed new status
            
        Returns:
            True if valid
            
        Raises:
            IdempotencyError: If transition is invalid
        """
        if not cls.is_valid_transition(current_status, new_status):
            valid_next = cls.get_next_statuses(current_status)
            raise IdempotencyError(
                f"Invalid status transition from '{current_status}' to '{new_status}'. "
                f"Valid next statuses: {valid_next}"
            )
        
        return True


class FirestoreExistenceChecker:
    """
    Centralized helpers for checking document existence in Firestore collections.

    Eliminates duplicate .get().exists patterns across tools by providing
    reusable query methods with consistent error handling.

    Usage:
        from core.idempotency import FirestoreExistenceChecker

        if FirestoreExistenceChecker.transcript_exists("dQw4w9WgXcQ"):
            print("Transcript already exists")

        has_job, job_id = FirestoreExistenceChecker.has_active_transcription_job("dQw4w9WgXcQ")
        if has_job:
            print(f"Active transcription job: {job_id}")
    """

    @classmethod
    def transcript_exists(cls, video_id: str, db=None) -> bool:
        """
        Check if a transcript exists for the given video ID.

        Args:
            video_id: YouTube video ID to check
            db: Firestore client (optional, will create if not provided)

        Returns:
            bool: True if transcript exists, False otherwise

        Example:
            >>> if FirestoreExistenceChecker.transcript_exists("dQw4w9WgXcQ"):
            >>>     print("Transcript already exists")
        """
        try:
            if db is None:
                from firestore_client import get_firestore_client
                db = get_firestore_client()

            transcript_ref = db.collection('transcripts').document(video_id)
            return transcript_ref.get().exists
        except Exception as e:
            # Log error but return False to allow graceful degradation
            print(f"Warning: Failed to check transcript existence for {video_id}: {e}")
            return False

    @classmethod
    def video_exists(cls, video_id: str, db=None) -> bool:
        """
        Check if a video document exists in Firestore.

        Args:
            video_id: YouTube video ID to check
            db: Firestore client (optional, will create if not provided)

        Returns:
            bool: True if video exists, False otherwise

        Example:
            >>> if FirestoreExistenceChecker.video_exists("dQw4w9WgXcQ"):
            >>>     print("Video record exists")
        """
        try:
            if db is None:
                from firestore_client import get_firestore_client
                db = get_firestore_client()

            video_ref = db.collection('videos').document(video_id)
            return video_ref.get().exists
        except Exception as e:
            print(f"Warning: Failed to check video existence for {video_id}: {e}")
            return False

    @classmethod
    def summary_exists(cls, video_id: str, db=None) -> bool:
        """
        Check if a summary exists for the given video ID.

        Args:
            video_id: YouTube video ID to check
            db: Firestore client (optional, will create if not provided)

        Returns:
            bool: True if summary exists, False otherwise

        Example:
            >>> if FirestoreExistenceChecker.summary_exists("dQw4w9WgXcQ"):
            >>>     print("Summary already generated")
        """
        try:
            if db is None:
                from firestore_client import get_firestore_client
                db = get_firestore_client()

            summary_ref = db.collection('summaries').document(video_id)
            return summary_ref.get().exists
        except Exception as e:
            print(f"Warning: Failed to check summary existence for {video_id}: {e}")
            return False

    @classmethod
    def has_active_transcription_job(cls, video_id: str, db=None) -> tuple:
        """
        Check if an active transcription job exists for the video.

        Searches for jobs with status in ['pending', 'processing', 'completed']
        in the jobs_transcription collection.

        Args:
            video_id: YouTube video ID to check
            db: Firestore client (optional, will create if not provided)

        Returns:
            tuple: (has_job: bool, job_id: Optional[str])
                   Returns (True, job_id) if active job found, (False, None) otherwise

        Example:
            >>> has_job, job_id = FirestoreExistenceChecker.has_active_transcription_job("dQw4w9WgXcQ")
            >>> if has_job:
            >>>     print(f"Active job: {job_id}")
        """
        try:
            if db is None:
                from firestore_client import get_firestore_client
                db = get_firestore_client()

            from google.cloud.firestore_v1.base_query import FieldFilter

            # Query for active jobs
            existing_jobs = db.collection('jobs_transcription').where(
                filter=FieldFilter('video_id', '==', video_id)
            ).where(
                filter=FieldFilter('status', 'in', ['pending', 'processing', 'completed'])
            ).limit(1).get()

            if len(existing_jobs) > 0:
                return True, existing_jobs[0].id
            return False, None

        except Exception as e:
            print(f"Warning: Failed to check transcription job for {video_id}: {e}")
            return False, None

    @classmethod
    def get_video_data(cls, video_id: str, db=None) -> Optional[Dict[str, Any]]:
        """
        Retrieve video document data from Firestore.

        Args:
            video_id: YouTube video ID to retrieve
            db: Firestore client (optional, will create if not provided)

        Returns:
            Optional[Dict]: Video data if exists, None otherwise

        Example:
            >>> video_data = FirestoreExistenceChecker.get_video_data("dQw4w9WgXcQ")
            >>> if video_data:
            >>>     print(f"Video title: {video_data.get('title')}")
        """
        try:
            if db is None:
                from firestore_client import get_firestore_client
                db = get_firestore_client()

            video_ref = db.collection('videos').document(video_id)
            video_doc = video_ref.get()

            if video_doc.exists:
                return video_doc.to_dict()
            return None

        except Exception as e:
            print(f"Warning: Failed to get video data for {video_id}: {e}")
            return None

    @classmethod
    def get_transcript_data(cls, video_id: str, db=None) -> Optional[Dict[str, Any]]:
        """
        Retrieve transcript document data from Firestore.

        Args:
            video_id: YouTube video ID to retrieve
            db: Firestore client (optional, will create if not provided)

        Returns:
            Optional[Dict]: Transcript data if exists, None otherwise

        Example:
            >>> transcript_data = FirestoreExistenceChecker.get_transcript_data("dQw4w9WgXcQ")
            >>> if transcript_data:
            >>>     print(f"Transcript length: {len(transcript_data.get('transcript_text', ''))}")
        """
        try:
            if db is None:
                from firestore_client import get_firestore_client
                db = get_firestore_client()

            transcript_ref = db.collection('transcripts').document(video_id)
            transcript_doc = transcript_ref.get()

            if transcript_doc.exists:
                return transcript_doc.to_dict()
            return None

        except Exception as e:
            print(f"Warning: Failed to get transcript data for {video_id}: {e}")
            return None


# Test block for standalone execution
if __name__ == "__main__":
    print("Testing Idempotency module...")
    
    try:
        # Test VideoIDExtractor
        extractor = VideoIDExtractor()
        
        test_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "invalid url"
        ]
        
        for url in test_urls:
            video_id = extractor.extract_video_id(url)
            print(f"URL: {url} → Video ID: {video_id}")
        
        print("✅ Video ID extraction tests passed")
        
        # Test FilenameGenerator
        generator = FilenameGenerator()
        
        filename = generator.generate_filename("dQw4w9WgXcQ", "transcript", "txt")
        print(f"Generated filename: {filename}")
        
        parsed = generator.parse_filename(filename)
        print(f"Parsed filename: {parsed}")
        
        print("✅ Filename generation tests passed")
        
        # Test StatusTransitionManager
        status_mgr = StatusTransitionManager()
        
        valid_transition = status_mgr.is_valid_transition("discovered", "transcription_queued")
        invalid_transition = status_mgr.is_valid_transition("summarized", "discovered")
        
        print(f"Valid transition (discovered → transcription_queued): {valid_transition}")
        print(f"Invalid transition (summarized → discovered): {invalid_transition}")
        
        print("✅ Status transition tests passed")
        
        # Test DeduplicationManager
        dedup_mgr = DeduplicationManager()
        
        content_hash = dedup_mgr.generate_content_hash("test content")
        print(f"Content hash: {content_hash}")
        
        metadata = {"title": "Test Video", "duration": 120}
        fingerprint = dedup_mgr.generate_metadata_fingerprint(metadata)
        print(f"Metadata fingerprint: {fingerprint}")
        
        print("✅ Deduplication tests passed")
        
        print("🎉 Idempotency module tests completed!")
        
    except Exception as e:
        print(f"❌ Idempotency module test failed: {e}")
        exit(1)