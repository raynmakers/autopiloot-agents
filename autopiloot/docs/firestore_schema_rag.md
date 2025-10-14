# Firestore Schema: Hybrid RAG Extensions

This document describes the Firestore schema extensions for Hybrid RAG full transcript storage.

## Overview

The Hybrid RAG system extends the `transcripts/{video_id}` collection with additional fields to track full transcript ingestion across three storage surfaces: Zep (semantic), OpenSearch (keyword), and BigQuery (SQL analytics with metadata only).

## Updated `transcripts/{video_id}` Schema

### Core Fields (Existing)

```typescript
{
  video_id: string;              // YouTube video ID (document ID)
  title: string;                 // Video title
  channel_id: string;            // YouTube channel ID
  channel_handle: string;        // e.g., "@DanMartell"
  published_at: Timestamp;       // Video publication date
  duration_sec: number;          // Video duration in seconds
  transcript_text: string;       // Full transcript text
  created_at: Timestamp;         // Document creation timestamp
  updated_at: Timestamp;         // Last update timestamp
  status: string;                // "transcribed", "summarized", etc.
}
```

### New RAG Fields

```typescript
{
  // Zep v3 Integration
  zep_transcript_doc_id?: string;    // Thread ID in Zep (e.g., "transcript_mZxDw92UXmA")
  rag_ingested_at?: Timestamp;       // When full transcript was ingested to RAG systems

  // Content Hashing for Idempotency
  content_sha256?: string;           // SHA-256 hash of full transcript text

  // Chunking Metadata
  chunk_count?: number;              // Total number of chunks created
  chunk_hashes?: string[];           // Array of SHA-256 hashes per chunk

  // Optional: Individual System Timestamps
  zep_ingested_at?: Timestamp;       // When stored to Zep
  opensearch_indexed_at?: Timestamp; // When indexed to OpenSearch
  bigquery_streamed_at?: Timestamp;  // When streamed to BigQuery
}
```

## Field Descriptions

### `zep_transcript_doc_id`
- **Type**: `string`
- **Format**: `transcript_{video_id}`
- **Purpose**: References the Zep v3 thread containing transcript chunks
- **Example**: `"transcript_mZxDw92UXmA"`
- **Set by**: `UpsertFullTranscriptToZep` tool
- **Use Case**: Enables retrieval of semantic search results from Zep

### `rag_ingested_at`
- **Type**: `Timestamp` (Firestore SERVER_TIMESTAMP)
- **Purpose**: Tracks when full transcript was ingested to RAG systems
- **Set by**: `UpsertFullTranscriptToZep` tool
- **Use Case**: Enables filtering/querying ingested vs non-ingested transcripts

### `content_sha256`
- **Type**: `string`
- **Format**: 64-character hex string
- **Purpose**: SHA-256 hash of complete transcript text for deduplication
- **Example**: `"a3c7f9e2b1d4..."`
- **Set by**: `UpsertFullTranscriptToZep` tool
- **Use Case**: Detect duplicate content, verify transcript integrity

### `chunk_count`
- **Type**: `number`
- **Purpose**: Total number of chunks created during ingestion
- **Example**: `12` (for a 12,000 token transcript with 1000 tokens/chunk)
- **Set by**: `UpsertFullTranscriptToZep` tool
- **Use Case**: Track chunking statistics, estimate storage size

### `chunk_hashes`
- **Type**: `array<string>`
- **Purpose**: SHA-256 hash for each individual chunk
- **Example**: `["a3c7f9...", "b2d5e1...", "c4f8a2..."]`
- **Set by**: `UpsertFullTranscriptToZep` tool
- **Use Case**: Per-chunk deduplication, verify chunk integrity

### Optional Timestamp Fields

These fields enable tracking ingestion to individual systems:

- `zep_ingested_at`: When transcript stored to Zep v3
- `opensearch_indexed_at`: When transcript indexed to OpenSearch
- `bigquery_streamed_at`: When transcript streamed to BigQuery

**Use Case**: Monitor system-specific ingestion status, identify ingestion failures

## Example Document

```json
{
  "video_id": "mZxDw92UXmA",
  "title": "How to 10x Your Business - Dan Martell",
  "channel_id": "UCkP5J0pXI11VE81q7S7V1Jw",
  "channel_handle": "@DanMartell",
  "published_at": "2025-10-08T12:00:00Z",
  "duration_sec": 1200,
  "transcript_text": "Welcome to this tutorial...",
  "status": "summarized",
  "created_at": "2025-10-08T12:30:00Z",
  "updated_at": "2025-10-08T12:35:00Z",

  // New RAG fields
  "zep_transcript_doc_id": "transcript_mZxDw92UXmA",
  "rag_ingested_at": "2025-10-08T12:35:00Z",
  "content_sha256": "a3c7f9e2b1d4c5a8f3e9d7b2c6a1f4e8d9b3c7a5f2e6d1b8c4a9f7e3d2b5c8a6",
  "chunk_count": 2,
  "chunk_hashes": [
    "4ad968bab7b2574c551aad731381d8e4a4de5641ddf8776d6f8dbf17abe11a69",
    "f0eb24671b21000cd17dd180fbd0adcf325cdc2721390d99cc341febe9770509"
  ],
  "zep_ingested_at": "2025-10-08T12:35:00Z",
  "opensearch_indexed_at": "2025-10-08T12:35:15Z",
  "bigquery_streamed_at": "2025-10-08T12:35:30Z"
}
```

## Querying Patterns

### Find Ingested Transcripts
```javascript
db.collection('transcripts')
  .where('rag_ingested_at', '!=', null)
  .orderBy('rag_ingested_at', 'desc')
  .limit(100);
```

### Find Transcripts Needing Ingestion
```javascript
db.collection('transcripts')
  .where('status', '==', 'transcribed')
  .where('rag_ingested_at', '==', null)
  .limit(100);
```

### Check for Duplicate Content
```javascript
db.collection('transcripts')
  .where('content_sha256', '==', specificHash)
  .get();
```

## Idempotency Strategy

The schema supports idempotent operations through:

1. **Document-Level Hash**: `content_sha256` detects duplicate transcripts
2. **Chunk-Level Hashes**: `chunk_hashes[]` detects duplicate chunks
3. **Zep Thread ID**: `zep_transcript_doc_id` enables retrieval and update operations
4. **Timestamps**: `rag_ingested_at` prevents re-ingestion

## Migration Notes

### Existing Documents

Existing `transcripts/{video_id}` documents without RAG fields are compatible. The new fields are optional and added only when full transcript ingestion is performed.

### Backward Compatibility

- All new fields are optional (`?` suffix in TypeScript)
- Existing queries continue to work
- New queries can filter by RAG fields when present

### Re-ingestion

To re-ingest a transcript:
1. Check `content_sha256` to detect content changes
2. Compare `chunk_hashes` to identify changed chunks
3. Update only changed chunks in Zep/OpenSearch/BigQuery
4. Update `rag_ingested_at` timestamp

## Related Documentation

- **Configuration**: `config/settings.yaml` - RAG chunking and storage settings
- **Tools**: `summarizer_agent/tools/upsert_full_transcript_to_zep.py` - Primary ingestion tool
- **Architecture**: `docs/testing.md` - Testing patterns for RAG systems
- **Workflow**: `summarizer_agent/instructions.md` - Agent workflow documentation

---

# Optional Firestore RAG References

**Collection**: `rag_refs/{document_id}` *(TASK-0096)*

## Purpose

Optional lightweight Firestore references that point to where RAG artifacts are indexed. These are **audit/discovery pointers only** and do not couple RAG indexing to Firestore.

## Key Principles

1. **Optional**: Controlled by `rag.features.write_firestore_refs` feature flag (default: false)
2. **Best-Effort**: Reference writes never block indexing operations
3. **Non-Blocking**: All exceptions caught and logged as warnings only
4. **No Hard Dependency**: RAG indexing/search works perfectly without Firestore
5. **Audit Trail**: Helps operations team locate where artifacts are stored

## Document ID Format

Document IDs use natural keys from source artifacts:
- Transcripts: `transcript_{video_id}` (e.g., `transcript_abc123`)
- Summaries: `summary_{video_id}` (e.g., `summary_abc123`)
- Documents: `document_{doc_id}` (e.g., `document_google_doc_xyz`)
- LinkedIn: `linkedin_{post_id}` (e.g., `linkedin_urn_123`)
- Strategy: `strategy_{strategy_id}` (e.g., `strategy_playbook_001`)

## Reference Schema

```typescript
interface RAGReference {
  // Required fields
  type: "transcript" | "summary" | "document" | "linkedin" | "strategy";
  source_ref: string;  // Original source identifier (video_id, doc_id, etc.)
  created_at: Timestamp;
  created_by_agent: string;  // Agent that created the reference

  // Optional sink references (only set if sink enabled and indexing succeeded)
  opensearch_index?: string;  // OpenSearch index name
  bigquery_table?: string;    // BigQuery table ID (project.dataset.table)
  zep_doc_id?: string;        // Zep document/thread ID

  // Content metadata
  content_hashes: string[];   // SHA-256 hashes of all chunks
  chunk_count: number;        // Total number of chunks created
  total_tokens: number;       // Total tokens across all chunks

  // Optional metadata
  title?: string;             // Human-readable title
  channel_id?: string;        // YouTube channel ID (for transcripts/summaries)
  published_at?: string;      // Publication date (ISO 8601)
  tags?: string[];            // Categorization tags

  // Status tracking
  indexing_status: "success" | "partial" | "error";
  sink_statuses: {
    opensearch?: "indexed" | "skipped" | "error";
    bigquery?: "streamed" | "skipped" | "error";
    zep?: "upserted" | "skipped" | "error";
  };

  // Audit trail
  last_updated_at: Timestamp;
  indexing_duration_ms: number;  // Total time taken for indexing operation
}
```

## Example: Transcript Reference

```json
{
  "type": "transcript",
  "source_ref": "abc123",
  "created_at": "2025-10-13T14:30:00Z",
  "created_by_agent": "transcriber_agent",

  "opensearch_index": "autopiloot_transcripts",
  "bigquery_table": "autopiloot-prod.autopiloot.transcript_chunks",
  "zep_doc_id": "transcript_abc123",

  "content_hashes": ["a1b2c3d4e5f6...", "f6e5d4c3b2a1..."],
  "chunk_count": 10,
  "total_tokens": 8500,

  "title": "How to Scale a SaaS Business",
  "channel_id": "UCkP5J0pXI11VE81q7S7V1Jw",
  "published_at": "2025-10-08T12:00:00Z",
  "tags": ["saas", "scaling", "business"],

  "indexing_status": "success",
  "sink_statuses": {
    "opensearch": "indexed",
    "bigquery": "streamed",
    "zep": "upserted"
  },

  "last_updated_at": "2025-10-13T14:30:05Z",
  "indexing_duration_ms": 5234
}
```

## Usage in Code

```python
from core.rag.refs import upsert_ref

# After successful RAG indexing (best-effort, never blocks)
upsert_ref({
    "type": "transcript",
    "source_ref": video_id,
    "created_by_agent": "transcriber_agent",
    "opensearch_index": "autopiloot_transcripts",
    "bigquery_table": f"{project_id}.{dataset}.transcript_chunks",
    "zep_doc_id": f"transcript_{video_id}",
    "content_hashes": chunk_hashes,
    "chunk_count": len(chunks),
    "total_tokens": total_tokens,
    "indexing_status": "success",
    "sink_statuses": sink_statuses,
    "indexing_duration_ms": duration_ms
})
```

## Firestore Indexes

For efficient querying:

```
rag_refs:
- type (ASC) + created_at (DESC)
- source_ref (ASC) + type (ASC)
- indexing_status (ASC) + created_at (DESC)
- created_by_agent (ASC) + created_at (DESC)
```

## Feature Flag

In `config/settings.yaml`:

```yaml
rag:
  features:
    write_firestore_refs: false  # Default: disabled (opt-in)
```

## Behavior Notes

- **Feature Flag Disabled (Default)**: No Firestore writes, zero overhead
- **Feature Flag Enabled**: Best-effort writes, failures logged only
- **Error Handling**: All exceptions caught, never propagate
- **Use Cases**: Operations audit, debugging, analytics, recovery planning

## Non-Goals

- ❌ **NOT a required dependency**: RAG must work without Firestore
- ❌ **NOT for retrieval**: Use RAG sinks directly for search
- ❌ **NOT for synchronization**: References don't guarantee sink state
- ❌ **NOT transactional**: References may be stale or missing
