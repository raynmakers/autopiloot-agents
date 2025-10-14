# RAG Wrapper Tests

This directory contains comprehensive test suites for all Hybrid RAG agent wrappers.

## Implementation Status

✅ **All wrappers implemented and tests created** (TASK-0094 Complete)

### Implemented Wrappers

1. **transcriber_agent/tools/rag_index_transcript.py** - Index video transcripts
2. **drive_agent/tools/rag_index_document.py** - Index Google Drive documents
3. **linkedin_agent/tools/rag_index_linkedin.py** - Index LinkedIn posts and comments
4. **summarizer_agent/tools/rag_index_summary.py** - Index video summaries
5. **strategy_agent/tools/rag_hybrid_search.py** - Hybrid retrieval search
6. **strategy_agent/tools/rag_index_strategy.py** - Index strategy content (feature-flagged)

### Test Files

1. **test_transcriber_wrapper.py** - 11 test cases covering initialization, payload building, core library delegation, error handling
2. **test_drive_wrapper.py** - 9 test cases including document type inference and tag handling
3. **test_linkedin_wrapper.py** - 9 test cases including engagement metrics and title generation
4. **test_summarizer_wrapper.py** - 8 test cases including video_id linking and field renaming
5. **test_strategy_search_wrapper.py** - 10 test cases including various filter types
6. **test_strategy_index_wrapper.py** - 11 test cases including feature flag behavior

**Total: 58 comprehensive test cases**

## Wrapper Architecture

All wrappers follow a consistent pattern:

1. **Thin wrapper design**: No RAG logic in agent tools
2. **Pydantic validation**: Strict input validation via Agency Swarm BaseTool
3. **Core library delegation**: All RAG operations handled by `core/rag/` modules
4. **JSON string returns**: Compliance with Agency Swarm v1.0.2 return format
5. **Error handling**: Graceful degradation with structured error responses
6. **Feature flags**: Optional features (strategy indexing) controlled via config

## Core Library Functions

### Indexing Functions

- **core.rag.ingest_transcript.ingest(payload)** - Transcript chunking and multi-sink ingestion
- **core.rag.ingest_document.ingest(payload)** - Document chunking and multi-sink ingestion
- **core.rag.ingest_strategy.ingest(payload)** - Strategy content ingestion to Zep

### Retrieval Functions

- **core.rag.hybrid_retrieve.search(query, filters, limit)** - Hybrid search with RRF fusion

## Test Coverage Goals

- **Target**: ≥80% coverage per wrapper file
- **Strategy**: Direct file imports with dependency mocking
- **Validation**: Payload structure, core library calls, error paths

## Running Tests

### Prerequisite

Tests require proper Python environment with dependencies:
```bash
pip install -r requirements.txt
```

### Run All Wrapper Tests

```bash
cd autopiloot
export PYTHONPATH=.
python -m unittest discover tests/rag_wrappers -p "test_*.py" -v
```

### Run Individual Test Suites

```bash
python -m unittest tests.rag_wrappers.test_transcriber_wrapper -v
python -m unittest tests.rag_wrappers.test_drive_wrapper -v
python -m unittest tests.rag_wrappers.test_linkedin_wrapper -v
python -m unittest tests.rag_wrappers.test_summarizer_wrapper -v
python -m unittest tests.rag_wrappers.test_strategy_search_wrapper -v
python -m unittest tests.rag_wrappers.test_strategy_index_wrapper -v
```

### Test Tool Directly (with environment)

Each tool includes a `if __name__ == "__main__"` test block:

```bash
python transcriber_agent/tools/rag_index_transcript.py
python drive_agent/tools/rag_index_document.py
python linkedin_agent/tools/rag_index_linkedin.py
python summarizer_agent/tools/rag_index_summary.py
python strategy_agent/tools/rag_hybrid_search.py
python strategy_agent/tools/rag_index_strategy.py
```

## Test Scope

### What Tests Cover

- ✅ Wrapper initialization with required and optional fields
- ✅ Payload building from tool parameters
- ✅ Core library function calls with correct arguments
- ✅ Success response handling and JSON formatting
- ✅ Partial success scenarios (some sinks fail)
- ✅ Error handling and exception wrapping
- ✅ Field renaming for clarity (document_id → summary_id, etc.)
- ✅ Feature flag behavior (strategy indexing)
- ✅ Filter handling (channel_id, date ranges, duration)
- ✅ Document type inference (PDF, DOCX, etc.)
- ✅ Engagement metrics handling (LinkedIn)

### What Tests Don't Cover

- ❌ Actual network calls (mocked)
- ❌ Real database operations (mocked)
- ❌ End-to-end integration with OpenSearch/BigQuery/Zep (covered by core library tests)
- ❌ Agency Swarm framework integration (requires full environment)

## Acceptance Criteria (TASK-0094)

✅ **Write access implemented**:
- transcriber (index transcripts)
- drive (index documents)
- linkedin (index posts/comments)
- summarizer (index summaries)

✅ **Read access implemented**:
- strategy (hybrid search)

✅ **Optional write with feature flag**:
- strategy (index strategy content, gated by `rag.features.persist_strategies`)

✅ **All wrappers delegate to shared core**:
- No indexing logic in agent tools
- All operations through `core/rag/` modules

✅ **Tests created**:
- 58 test cases across 6 test files
- Coverage targets: ≥80% per file

## Integration with Agents

### Transcriber Agent

After `save_transcript_record.py` completes, call `rag_index_transcript.py` to make transcripts searchable.

### Drive Agent

After `extract_text_from_document.py` completes, call `rag_index_document.py` to index documents.

### LinkedIn Agent

After fetching posts/comments, call `rag_index_linkedin.py` to index for competitive analysis.

### Summarizer Agent

After `generate_short_summary.py` completes, call `rag_index_summary.py` to make summaries searchable.

### Strategy Agent

- Use `rag_hybrid_search.py` to search across all indexed content
- Optionally use `rag_index_strategy.py` if `rag.features.persist_strategies` is enabled

## Configuration

All wrappers respect configuration in `config/settings.yaml`:

```yaml
rag:
  # Sink enablement
  opensearch:
    enabled: true
  bigquery:
    enabled: true
  zep:
    transcripts:
      enabled: true
    documents:
      enabled: true

  # Feature flags
  features:
    persist_strategies: false  # Default: disabled

  # Chunking configuration
  zep:
    transcripts:
      chunking:
        max_tokens_per_chunk: 1000
        overlap_tokens: 100
```

## Next Steps

1. Run tests in CI/CD environment with proper dependencies
2. Generate coverage reports: `coverage run && coverage report`
3. Integrate wrappers into agent workflows
4. Monitor RAG observability metrics via `core.rag.tracing`

## Task Completion

**TASK-0094**: ✅ Complete

All mandatory per-agent Hybrid RAG wrappers have been implemented as thin `@function_tool` wrappers that delegate to the shared core library. Test suites validate proper delegation, error handling, and Agency Swarm compliance.
