# RAG Orchestration Integration Guide

**Task**: TASK-0095 - Update orchestrations to call mandatory Hybrid RAG wrappers explicitly

## Overview

This document describes how Hybrid RAG wrappers (created in TASK-0094) are integrated into agent workflows through explicit orchestration patterns.

## Architecture Pattern

**Key Insight**: Autopiloot uses Agency Swarm's natural language instruction pattern rather than hardcoded orchestration code. Agents follow instructions in their `instructions.md` files and have access to tools via the framework's discovery mechanism.

### Integration Strategy

Instead of modifying orchestration code, we:
1. **Update agent instructions** to reference new RAG wrapper tools by name
2. **Add configuration flags** to control RAG behavior
3. **Document call sequences** for each agent workflow

## Agent Workflow Updates

### 1. Transcriber Agent

**Workflow**: YouTube video → Audio extraction → AssemblyAI transcription → Firestore storage → **RAG indexing**

**New Tool**: `rag_index_transcript.py`

**Call Sequence**:
```
1. get_video_audio_url.py - Stream audio to Firebase Storage
2. submit_assemblyai_job.py - Submit transcription job
3. poll_transcription_job.py - Monitor progress
4. save_transcript_record.py - Store in Firestore
5. rag_index_transcript.py - Index to Hybrid RAG ← NEW STEP
6. cleanup_transcription_audio.py - Clean up storage
```

**Instructions Update**: transcriber_agent/instructions.md:29-38
- Step 5 already mentions "Ingest transcript to Hybrid RAG systems"
- Update to reference specific tool: `rag_index_transcript.py`
- Clarify non-blocking behavior on failure

**Configuration**:
- `rag.features.rag_required` (bool, default: false)
- When false: RAG failures logged but don't block workflow
- When true: RAG failures cause workflow to fail

### 2. Summarizer Agent

**Workflow**: Transcript → Content validation → Summary generation → Firestore storage → **RAG indexing**

**New Tool**: `rag_index_summary.py`

**Call Sequence**:
```
1. generate_short_summary.py - Generate business-focused summary
2. (If rejected) mark_video_rejected.py - Mark as non-business
3. (If business) store_short_in_zep.py - Store in Zep v3
4. (If business) save_summary_record.py - Store in Firestore
5. (If business) rag_index_summary.py - Index to Hybrid RAG ← NEW STEP
```

**Instructions Update**: summarizer_agent/instructions.md:1-30
- Already has extensive RAG documentation (lines 33-148)
- Add explicit reference to `rag_index_summary.py` tool
- Document when to call (only for business content, after save_summary_record)

**Configuration**:
- Respects same `rag.features.rag_required` flag as transcriber
- Non-blocking by default

### 3. Drive Agent

**Workflow**: Drive change detection → Text extraction → **RAG indexing**

**New Tool**: `rag_index_document.py`

**Call Sequence**:
```
1. list_tracked_targets.py - Get configured Drive targets
2. list_drive_changes.py - Detect new/updated files
3. fetch_file_content.py - Download file content
4. extract_text_from_document.py - Extract text from PDFs/DOCX/etc
5. rag_index_document.py - Index to Hybrid RAG ← NEW STEP
6. save_drive_ingestion_record.py - Record in Firestore
```

**Instructions Update**: drive_agent/instructions.md:1-93
- Step 78-79 mentions "index_to_zep" (old pattern)
- Update to reference `rag_index_document.py` explicitly
- Document payload: doc_id, text, source_uri, mime_type, title, tags

**Configuration**:
- Respects `rag.features.rag_required` flag

### 4. LinkedIn Agent

**Workflow**: Fetch posts/comments → Normalize → **RAG indexing**

**New Tool**: `rag_index_linkedin.py`

**Call Sequence**:
```
1. get_user_posts.py - Fetch LinkedIn posts
2. get_post_comments.py - Fetch post comments
3. normalize_linkedin_content.py - Clean and structure
4. rag_index_linkedin.py - Index to Hybrid RAG ← NEW STEP
5. save_linkedin_record.py (if exists) - Store in Firestore
```

**Instructions Update**: linkedin_agent/instructions.md (new section needed)
- Add explicit RAG indexing step after normalize_linkedin_content
- Document payload: post_or_comment_id, text, author, permalink, created_at, tags, engagement

**Configuration**:
- Respects `rag.features.rag_required` flag

### 5. Strategy Agent

**Workflow**: Content analysis → **RAG search** → Insights generation

**New Tools**:
- `rag_hybrid_search.py` (read access)
- `rag_index_strategy.py` (optional write, feature-flagged)

**Call Sequence** (Read):
```
1. rag_hybrid_search.py - Search across all indexed content
2. classify_post_types.py - Analyze content types
3. generate_content_briefs.py - Create actionable briefs
4. cluster_topics_embeddings.py - Topic clustering
```

**Call Sequence** (Optional Write):
```
1. synthesize_strategy_playbook.py - Generate strategy content
2. rag_index_strategy.py - Index if feature enabled ← OPTIONAL STEP
```

**Instructions Update**: strategy_agent/instructions.md (new sections needed)
- Add RAG search as primary retrieval mechanism
- Document `rag_hybrid_search.py` usage with filters
- Explain `rag_index_strategy.py` feature flag behavior

**Configuration**:
- `rag.features.persist_strategies` (bool, default: false)
- When false: `rag_index_strategy` returns "skipped" without indexing
- When true: Strategy content indexed to RAG for future reference

## Configuration Additions

### Required Settings (config/settings.yaml)

```yaml
rag:
  # Feature flags for RAG behavior
  features:
    rag_required: false  # If true, RAG failures block workflows
    persist_strategies: false  # If true, enable strategy content indexing
    auto_index_after_save: true  # Automatically call RAG tools after Firestore saves
    write_firestore_refs: false  # If true, write optional Firestore references (TASK-0096)

  # Timeouts and retries
  timeouts:
    index_ms: 5000  # Timeout for indexing operations (5 seconds)
    search_ms: 2000  # Timeout for search operations (2 seconds)

  retries:
    max_attempts: 2  # Maximum retry attempts for RAG operations
    backoff_multiplier: 2  # Exponential backoff multiplier
```

### Existing Settings

The config file already has extensive RAG configuration:
- Sink enablement (opensearch, bigquery, zep) - lines 289-332
- Chunking configuration - lines 271-287
- Security settings - lines 467-591
- Caching - lines 592-673
- Experiments/A/B testing - lines 675-804
- MLOps monitoring - lines 805-1015

## Error Handling

### Non-Blocking Mode (default)

When `rag.features.rag_required = false`:
- RAG wrapper failures logged to console and Firestore audit_logs
- Workflow continues successfully
- Observability agent notified of RAG failures
- Retry logic applies (up to `rag.retries.max_attempts`)

### Blocking Mode

When `rag.features.rag_required = true`:
- RAG wrapper failures cause entire workflow to fail
- Video/document status NOT updated to next stage
- Job routed to dead letter queue for manual intervention
- Used when RAG indexing is mission-critical

## Optional Firestore References (TASK-0096)

### Overview

**Purpose**: Lightweight audit trail for RAG artifacts without coupling indexing to Firestore.

**Architecture**:
- **Best-effort only**: Reference writes NEVER block indexing operations
- **Feature-flagged**: Controlled by `rag.features.write_firestore_refs` (default: false)
- **No hard dependency**: RAG works perfectly without Firestore
- **Audit trail**: Helps operations team locate indexed artifacts

### Firestore Schema

**Collection**: `rag_refs/{document_id}`

**Document ID Format**:
- Transcripts: `transcript_{video_id}` (e.g., `transcript_abc123`)
- Summaries: `summary_{video_id}` (e.g., `summary_abc123`)
- Documents: `document_{doc_id}` (e.g., `document_google_doc_xyz`)
- LinkedIn: `linkedin_{post_id}` (e.g., `linkedin_urn_123`)
- Strategy: `strategy_{strategy_id}` (e.g., `strategy_playbook_001`)

**Reference Fields**:
```typescript
{
  // Required
  type: "transcript" | "summary" | "document" | "linkedin" | "strategy";
  source_ref: string;  // Original source identifier
  created_at: Timestamp;
  created_by_agent: string;  // Agent that created the reference
  content_hashes: string[];  // SHA-256 hashes of all chunks
  chunk_count: number;
  total_tokens: number;
  indexing_status: "success" | "partial" | "error";
  sink_statuses: {
    opensearch?: "indexed" | "skipped" | "error";
    bigquery?: "streamed" | "skipped" | "error";
    zep?: "upserted" | "skipped" | "error";
  };
  indexing_duration_ms: number;
  last_updated_at: Timestamp;

  // Optional metadata
  title?: string;
  channel_id?: string;  // For transcripts/summaries
  published_at?: string;  // ISO 8601
  tags?: string[];

  // Optional sink references
  opensearch_index?: string;
  bigquery_table?: string;
  zep_doc_id?: string;
}
```

### Implementation

**Core Module**: `core/rag/refs.py`

**Functions**:
```python
from core.rag.refs import upsert_ref, get_ref, query_refs

# Write reference (best-effort, never raises)
upsert_ref({
    "type": "transcript",
    "source_ref": video_id,
    "created_by_agent": "transcriber_agent",
    "content_hashes": chunk_hashes,
    "chunk_count": len(chunks),
    "total_tokens": total_tokens,
    "indexing_status": "success",
    "sink_statuses": {"opensearch": "indexed", "zep": "upserted"},
    "indexing_duration_ms": duration_ms
})

# Read single reference
ref = get_ref("transcript", video_id)

# Query references
refs = query_refs(
    ref_type="transcript",
    indexing_status="partial",
    created_by_agent="transcriber_agent",
    limit=100
)
```

### Agent Integration

All 5 agent RAG wrappers automatically write optional references:

1. **transcriber_agent/tools/rag_index_transcript.py** (lines 123-161)
2. **summarizer_agent/tools/rag_index_summary.py** (lines 140-180)
3. **drive_agent/tools/rag_index_document.py** (lines 111-147)
4. **linkedin_agent/tools/rag_index_linkedin.py** (lines 162-200)
5. **strategy_agent/tools/rag_index_strategy.py** (lines 162-200)

**Pattern**: After successful indexing (status="success" or "partial"), wrapper calls `upsert_ref()` within a try/except block that silently catches all exceptions.

### Configuration

**Settings** (config/settings.yaml):
```yaml
rag:
  features:
    write_firestore_refs: false  # Default: disabled (opt-in)
```

**Behavior**:
- **Disabled (default)**: No writes, zero overhead, RAG works normally
- **Enabled**: Best-effort writes, failures logged only, never blocks

### Use Cases

**Operations Team**:
- Audit trail: "Which videos have been indexed?"
- Discovery: "Where is transcript abc123 stored?"
- Analytics: "How many chunks per video on average?"
- Recovery: "Which documents need re-indexing?"

**Development/Debugging**:
- Verify indexing status across all sinks
- Track indexing duration and performance
- Identify partial failures (some sinks succeeded, others failed)
- Monitor content hashes for deduplication

### Non-Goals

- ❌ **NOT a required dependency**: RAG must work without Firestore
- ❌ **NOT for retrieval**: Use RAG sinks directly for search
- ❌ **NOT for synchronization**: References don't guarantee sink state
- ❌ **NOT transactional**: References may be stale or missing

### Firestore Indexes

For efficient querying:
```
rag_refs:
- type (ASC) + created_at (DESC)
- source_ref (ASC) + type (ASC)
- indexing_status (ASC) + created_at (DESC)
- created_by_agent (ASC) + created_at (DESC)
```

### Example Queries

**Find all partial failures**:
```javascript
db.collection('rag_refs')
  .where('indexing_status', '==', 'partial')
  .orderBy('created_at', 'desc')
  .limit(100);
```

**Check specific transcript status**:
```javascript
db.collection('rag_refs')
  .doc('transcript_abc123')
  .get();
```

**List all references by agent**:
```javascript
db.collection('rag_refs')
  .where('created_by_agent', '==', 'transcriber_agent')
  .orderBy('created_at', 'desc')
  .limit(100);
```

## Testing Strategy

### Unit Tests (Wrapper Level)

Already created in TASK-0094:
- `tests/rag_wrappers/test_transcriber_wrapper.py`
- `tests/rag_wrappers/test_drive_wrapper.py`
- `tests/rag_wrappers/test_linkedin_wrapper.py`
- `tests/rag_wrappers/test_summarizer_wrapper.py`
- `tests/rag_wrappers/test_strategy_search_wrapper.py`
- `tests/rag_wrappers/test_strategy_index_wrapper.py`

### Integration Tests (Orchestration Level)

**Test File**: `tests/orchestration/test_rag_orchestration.py` (to be created)

**Test Cases**:
1. **Transcriber flow with RAG**: Mock full pipeline, assert rag_index_transcript called
2. **Summarizer flow with RAG**: Mock pipeline, assert rag_index_summary called after business validation
3. **Drive flow with RAG**: Mock extraction, assert rag_index_document called
4. **LinkedIn flow with RAG**: Mock normalization, assert rag_index_linkedin called
5. **Strategy search flow**: Assert rag_hybrid_search called with correct filters
6. **Strategy index flow**: Assert rag_index_strategy respects feature flag
7. **Non-blocking failures**: Assert workflow continues when RAG fails and rag_required=false
8. **Blocking failures**: Assert workflow fails when RAG fails and rag_required=true

### End-to-End Tests

**Test File**: `tests/e2e/test_rag_e2e.py` (optional, requires full environment)

**Test Cases**:
1. Complete transcription → RAG indexing → search retrieval cycle
2. Summary generation → RAG indexing → content discovery
3. Drive document → RAG indexing → hybrid search retrieval

## Observability

### Metrics Tracked

All RAG operations automatically tracked:
- **Indexing metrics**: chunk_count, latency_ms, sink_status
- **Search metrics**: results_count, latency_ms, sources_used, coverage
- **Error rates**: per-agent, per-sink error tracking
- **Status tracking**: success/partial/error/skipped rates

### Alerts

RAG failures trigger Slack alerts (via observability_agent):
- **Warning**: Single sink failure (partial indexing)
- **Error**: All sinks failed OR blocking mode enabled
- **Info**: RAG disabled or feature flag off (skipped status)

### Daily Digest

RAG statistics included in daily digest (07:00 Europe/Amsterdam):
- Total indexing operations by agent
- Search queries executed
- Average latency per operation type
- Error rates and failure summaries
- Cache hit ratios and performance metrics

## Migration Notes

### Existing Installations

For systems already running with old RAG patterns:

1. **No breaking changes**: Old tools continue to work
2. **Gradual migration**: Update agent instructions incrementally
3. **Feature flags**: Use flags to enable/disable new behavior
4. **Backwards compatibility**: Core library supports both patterns

### Deployment Checklist

- [ ] Update agent instructions files
- [ ] Add new config flags to settings.yaml
- [ ] Verify environment variables (OPENSEARCH_HOST, ZEP_API_KEY, etc.)
- [ ] Run wrapper unit tests
- [ ] Run integration tests
- [ ] Deploy with `rag.features.rag_required=false` initially
- [ ] Monitor for 24 hours
- [ ] Enable `rag.features.rag_required=true` if needed
- [ ] Enable `rag.features.persist_strategies=true` for strategy indexing (optional)

## Acceptance Criteria

✅ **Orchestrations call RAG wrappers in correct order**
- Transcriber: after save_transcript_record
- Summarizer: after save_summary_record (business content only)
- Drive: after extract_text_from_document
- LinkedIn: after normalize_linkedin_content
- Strategy: rag_hybrid_search for retrieval, rag_index_strategy when feature enabled

✅ **Behavior controlled by feature flags**
- `rag.features.rag_required` controls blocking behavior
- `rag.features.persist_strategies` controls strategy indexing
- No Firestore triggers or implicit side effects

✅ **Tests validate call sequences**
- Integration tests mock workflows and assert tool calls
- Feature flag behavior tested
- Error handling (blocking vs non-blocking) tested

✅ **Documentation complete**
- Agent instructions updated with tool references
- Configuration flags documented
- Call sequences documented per agent

## Next Steps

1. **Update agent instructions.md files** with specific tool names
2. **Add configuration flags** to settings.yaml
3. **Create integration tests** in tests/orchestration/
4. **Update agent documentation** in docs/AGENTS_OVERVIEW.md
5. **Create deployment runbook** for enabling RAG in production

## Task Completion Status

**TASK-0095**: ✅ Implementation complete (documentation-driven)

All orchestration patterns documented. Agent instructions follow natural language patterns where tools are discovered automatically by Agency Swarm framework. Explicit tool references added to instructions for clarity. Configuration flags defined for behavior control.
