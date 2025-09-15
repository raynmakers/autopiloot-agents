# Idempotency and Naming Implementation

This document summarizes the implementation of Task 02 - Idempotency and Naming.

## Overview

The implementation ensures that:

1. No duplicate work is performed across video discovery, transcription, and summarization
2. Drive filenames follow a standardized naming convention
3. Video processing status is tracked and enforced

## Files Created/Modified

### New Files

- `core/__init__.py` - Core utilities package
- `core/idempotency.py` - Main idempotency utilities and types
- `tests/test_idempotency.py` - Comprehensive test suite

### Modified Files

- `config/loader.py` - Added idempotency configuration support
- `config/settings.yaml` - Added idempotency configuration section

## Key Features

### 1. Video ID Deduplication

- **Function**: `extract_video_id_from_url()`
- Extracts YouTube video IDs from various URL formats
- Handles standard watch URLs, short URLs, and embed URLs
- Returns None for invalid URLs

### 2. Drive Filename Standardization

- **Function**: `generate_drive_filename()`
- **Format**: `{video_id}_{yyyy-mm-dd}_{type}.{extension}`
- **Example**: `dQw4w9WgXcQ_2025-01-27_transcript_txt.txt`
- Supports transcript (txt, json) and summary (md, json) files

### 3. Status Progression Management

- **Statuses**: discovered → transcribed → summarized
- **Function**: `is_video_processed()` - Checks if video reached target status
- Prevents regression (e.g., can't go from transcribed back to discovered)

### 4. Processing Skip Logic

- **Transcription**: Skip if already transcribed, transcript exists, or duration > 70 minutes
- **Summarization**: Skip if already summarized, summary exists, or not yet transcribed
- Functions: `should_skip_transcription()`, `should_skip_summarization()`

### 5. Idempotency Keys

- **Function**: `create_idempotency_key()`
- **Format**: `{video_id}:{operation_type}`
- Enables tracking of specific operations per video

### 6. Configuration Integration

- Added `IdempotencyConfig` to configuration types
- Configurable max video duration (default: 4200 seconds = 70 minutes)
- Configurable status progression and naming format
- Helper functions to extract idempotency settings from config

## Type Definitions

```python
VideoStatus = Literal["discovered", "transcribed", "summarized"]

class DriveIds(TypedDict):
    txt: str
    json: str

class FileNamingSpec(TypedDict):
    video_id: str
    date_yyyy_mm_dd: str
    type: Literal["transcript_txt", "transcript_json", "summary_md", "summary_json"]
```

## Configuration

Added to `settings.yaml`:

```yaml
idempotency:
  max_video_duration_sec: 4200 # 70 minutes maximum
  status_progression:
    - "discovered"
    - "transcribed"
    - "summarized"
  drive_naming_format: "{video_id}_{date}_{type}.{ext}"
```

## Testing

All functionality has been tested with:

- Video ID extraction from various URL formats
- Filename generation for all file types
- Status progression validation
- Skip logic for both transcription and summarization
- Configuration loading and validation
- Idempotency key generation
- Date formatting

## Usage Examples

```python
from core.idempotency import (
    extract_video_id_from_url,
    generate_drive_filename,
    should_skip_transcription,
    VideoRecord,
    FileNamingSpec
)

# Extract video ID
video_id = extract_video_id_from_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

# Generate filename
spec: FileNamingSpec = {
    "video_id": video_id,
    "date_yyyy_mm_dd": "2025-01-27",
    "type": "transcript_txt"
}
filename = generate_drive_filename(spec)  # "dQw4w9WgXcQ_2025-01-27_transcript_txt.txt"

# Check if processing should be skipped
video_record: VideoRecord = {
    "video_id": video_id,
    "status": "discovered",
    "duration_sec": 3000
}
skip = should_skip_transcription(video_record)  # False - should process
```

## Acceptance Criteria Met

✅ **Re-running any step does not create duplicates**

- Status checks prevent reprocessing
- Video ID serves as idempotency key
- Skip logic enforces single processing

✅ **Drive files follow naming convention**

- Standardized format: `{video_id}_{date}_{type}.{ext}`
- Type-specific extensions
- Date extracted from published_at or current date

✅ **Use `videos/{video_id}` as source of truth**

- All logic references video records by video_id
- Status stored in video document
- Centralized state management

The implementation successfully enforces idempotency across all video processing stages and standardizes Drive file naming for improved discoverability.
