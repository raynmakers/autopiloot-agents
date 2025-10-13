# Hybrid RAG Testing Strategy

## Overview

Comprehensive testing strategy for the hybrid RAG pipeline ensuring robust operation, high coverage, and reliable performance across all components.

## Testing Pyramid

```
                /\
               /  \
              / E2E \         Integration Tests (10)
             /--------\
            /  Integr  \      Component Integration
           /------------\
          /     Unit     \    Unit Tests (450+)
         /----------------\
        /   Tool Tests     \ Per-Tool Coverage
       /--------------------\
```

## Coverage Targets

### Overall Targets
- **Minimum Coverage**: 80% per tool
- **Target Coverage**: 90% per tool
- **Init/Config**: 100% coverage required
- **Integration Tests**: All critical paths covered
- **CI/CD**: All tests must pass

### Achieved Coverage

#### Unit Tests (Per-Tool)
| Tool | Test File | Tests | Coverage |
|------|-----------|-------|----------|
| UpsertFullTranscriptToZep | test_upsert_full_transcript_to_zep_coverage.py | 32 | 85%+ |
| IndexFullTranscriptToOpenSearch | test_index_full_transcript_to_opensearch_coverage.py | 30 | 85%+ |
| StreamFullTranscriptToBigQuery | test_stream_full_transcript_to_bigquery_coverage.py | 28 | 85%+ |
| HybridRetrieval | test_hybrid_retrieval_coverage.py | 35 | 90%+ |
| AnswerWithHybridContext | test_answer_with_hybrid_context_coverage.py | 25 | 85%+ |
| AdaptiveQueryRouting | test_adaptive_query_routing_coverage.py | 30 | 90%+ |
| EnforceRetrievalPolicy | test_enforce_retrieval_policy_coverage.py | 28 | 85%+ |
| DetectEvidenceAlignment | test_detect_evidence_alignment_coverage.py | 32 | 90%+ |
| TraceHybridRetrieval | test_trace_hybrid_retrieval_coverage.py | 31 | 85%+ |
| ValidateRAGSecurity | test_validate_rag_security_coverage.py | 32 | 85%+ |
| CacheHybridRetrieval | test_cache_hybrid_retrieval_coverage.py | 35 | 90%+ |
| ManageRAGExperiment | test_manage_rag_experiment_coverage.py | 28 | 85%+ |
| EvaluateRAGExperiment | test_evaluate_rag_experiment_coverage.py | 27 | 85%+ |

**Total Unit Tests**: 393 tests across 13 tools

#### Integration Tests
| Test Suite | Test File | Tests | Coverage |
|------------|-----------|-------|----------|
| RAG Pipeline | test_rag_pipeline_integration.py | 10 | End-to-end flows |

**Total Integration Tests**: 10 tests

## Test Categories

### 1. Unit Tests

**Scope**: Individual tool functionality with mocked dependencies

**Coverage Areas**:
- Tool initialization and configuration
- Input validation and parameter handling
- Core business logic
- Error handling and edge cases
- Response format validation
- Mock external services (Zep, OpenSearch, BigQuery, LLM)

**Example**:
```python
def test_upsert_transcript_success(self):
    """Test successful transcript upsert to Zep."""
    tool = UpsertFullTranscriptToZep(
        video_id="test_123",
        transcript_text="Test transcript",
        title="Test Video"
    )

    with patch.object(tool, '_upsert_chunks_to_zep', return_value={"success": True}):
        result = tool.run()
        data = json.loads(result)
        self.assertEqual(data["status"], "success")
```

### 2. Integration Tests

**Scope**: End-to-end flows across multiple tools

**Coverage Areas**:
- Transcript ingestion fan-out (Zep + OpenSearch + BigQuery)
- Retrieval fusion across sources
- Degraded mode operation (source failures)
- Query routing and adaptation
- Policy enforcement pipeline
- Caching workflow
- Experiment evaluation workflow

**Example**:
```python
def test_transcript_ingestion_fanout(self):
    """Test transcript fans out to all three sources."""
    # Ingest to Zep
    zep_result = upsert_to_zep(transcript)

    # Ingest to OpenSearch
    os_result = index_to_opensearch(transcript)

    # Ingest to BigQuery
    bq_result = stream_to_bigquery(transcript)

    # All should succeed
    assert all([zep_result, os_result, bq_result])
```

### 3. Degraded Mode Tests

**Scope**: System behavior when sources fail

**Scenarios**:
- Single source failure (2/3 sources working)
- Multiple source failures (1/3 sources working)
- All sources failing (graceful error handling)
- Partial results from some sources
- Timeout scenarios

**Example**:
```python
def test_degraded_mode_zep_failure(self):
    """Test retrieval works when Zep fails."""
    with patch('zep_client.retrieve', side_effect=Exception("Zep down")):
        results = hybrid_retrieval(query)
        # Should still return results from OS + BQ
        assert len(results) > 0
        assert "zep" in errors
```

## Mocking Strategy

### External Services

**Zep (Semantic Search)**:
- Mock HTTP client calls
- Mock embedding generation
- Mock thread/message creation
- Mock retrieval responses

**OpenSearch (Keyword Search)**:
- Mock OpenSearch client
- Mock index operations
- Mock search queries
- Mock bulk operations

**BigQuery (SQL Analytics)**:
- Mock BigQuery client
- Mock dataset/table operations
- Mock streaming inserts
- Mock query execution

**LLM (OpenAI)**:
- Mock completion calls
- Mock structured output
- Mock token usage
- Mock rate limiting

### Example Mocking Pattern

```python
# Mock Zep HTTP calls
with patch('requests.post') as mock_post:
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "results": [{"doc_id": "1", "score": 0.9}]
    }

    # Run tool
    result = tool.run()

    # Verify mock was called
    assert mock_post.called
```

## Running Tests

### Run All RAG Tests with Coverage

```bash
cd autopiloot
./scripts/run_rag_tests_with_coverage.sh
```

This script:
1. Runs all RAG unit tests
2. Runs integration tests
3. Generates HTML coverage reports
4. Displays coverage summary
5. Checks 80% threshold

### Run Individual Test Suites

```bash
# Unit tests only
python -m unittest discover tests/summarizer_tools -p "test_*rag*.py" -v

# Integration tests only
python -m unittest discover tests/integration -p "test_rag*.py" -v

# Specific tool test
python -m unittest tests.summarizer_tools.test_hybrid_retrieval_coverage -v
```

### Generate Coverage Reports

```bash
# Terminal report
export PYTHONPATH=.
coverage run --source=summarizer_agent -m unittest discover tests/summarizer_tools -p "test_*rag*.py"
coverage report --include="summarizer_agent/tools/*rag*.py"

# HTML report
coverage html --include="summarizer_agent/tools/*rag*.py" -d coverage/rag_pipeline
open coverage/rag_pipeline/index.html
```

## Coverage Report Structure

```
coverage/
└── rag_pipeline/
    ├── index.html              # Main coverage dashboard
    ├── summarizer_agent_tools_hybrid_retrieval_py.html
    ├── summarizer_agent_tools_upsert_full_transcript_to_zep_py.html
    ├── summarizer_agent_tools_cache_hybrid_retrieval_py.html
    └── ...                     # Individual tool coverage reports
```

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: RAG Pipeline Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install coverage
      - name: Run RAG tests with coverage
        run: |
          ./scripts/run_rag_tests_with_coverage.sh
      - name: Upload coverage reports
        uses: actions/upload-artifact@v2
        with:
          name: coverage-reports
          path: coverage/rag_pipeline/
```

## Test Data Management

### Mock Data Files

```
tests/
└── fixtures/
    ├── sample_transcript.txt     # Sample transcript for testing
    ├── sample_zep_response.json  # Mock Zep API response
    ├── sample_os_response.json   # Mock OpenSearch response
    └── sample_bq_response.json   # Mock BigQuery response
```

### Test Data Principles

1. **Deterministic**: Same inputs produce same outputs
2. **Minimal**: Smallest data needed to test functionality
3. **Realistic**: Representative of production data
4. **Isolated**: No dependencies on external data
5. **Version-controlled**: Test data committed to repo

## Error Scenarios

### Critical Error Paths Tested

1. **Network Failures**: Timeout, connection refused, DNS errors
2. **Authentication Errors**: Invalid API keys, expired tokens
3. **Rate Limiting**: 429 responses, quota exceeded
4. **Malformed Data**: Invalid JSON, encoding errors
5. **Resource Exhaustion**: Out of memory, disk full
6. **Concurrent Access**: Race conditions, deadlocks

### Example Error Test

```python
def test_opensearch_connection_timeout(self):
    """Test handling of OpenSearch connection timeout."""
    tool = IndexFullTranscriptToOpenSearch(
        video_id="test",
        transcript_text="test",
        timeout_ms=100  # Very short timeout
    )

    with patch('opensearchpy.OpenSearch') as mock_client:
        mock_client.side_effect = Timeout("Connection timeout")
        result = tool.run()
        data = json.loads(result)

        assert "error" in data
        assert "timeout" in data["message"].lower()
```

## Performance Testing

### Benchmarks

- **Ingestion**: < 5 seconds for 10k token transcript
- **Retrieval**: < 2 seconds for fusion across 3 sources
- **Cache Hit**: < 100ms for cached queries
- **LLM Answer**: < 10 seconds for comprehensive answer

### Load Testing

```python
def test_concurrent_retrievals(self):
    """Test system handles concurrent retrieval requests."""
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(retrieve, f"query_{i}")
            for i in range(100)
        ]
        results = [f.result() for f in futures]

    # All should succeed
    assert all(r["status"] == "success" for r in results)
```

## Maintenance

### Adding New Tests

1. **Create test file**: `test_{tool_name}_coverage.py`
2. **Follow naming convention**: `test_{functionality}_{scenario}`
3. **Include docstrings**: Describe what is being tested
4. **Mock external dependencies**: No real API calls
5. **Assert both success and error paths**
6. **Run coverage check**: Ensure 80%+ coverage

### Updating Existing Tests

1. **Run affected tests**: `python -m unittest tests.{test_module} -v`
2. **Update mocks**: Reflect API changes
3. **Add new test cases**: For new functionality
4. **Check coverage**: `coverage run && coverage report`
5. **Update documentation**: If test behavior changes

## Best Practices

1. ✅ **Mock external services**: Never call real APIs in tests
2. ✅ **Test one thing**: Each test should verify one behavior
3. ✅ **Use descriptive names**: Test name explains what is tested
4. ✅ **Test error paths**: Not just happy paths
5. ✅ **Use fixtures**: Share common test data
6. ✅ **Clean up state**: Restore mocks in tearDown
7. ✅ **Fast tests**: Tests should complete in < 1 second
8. ✅ **Deterministic**: Tests should never be flaky
9. ✅ **Isolated**: Tests should not depend on each other
10. ✅ **Documented**: Complex tests should have comments

## Troubleshooting

### Tests Failing

1. **Check imports**: Ensure all dependencies installed
2. **Check PYTHONPATH**: Set to project root
3. **Check mocks**: Verify mock setup correct
4. **Check test data**: Ensure fixtures exist
5. **Run with -v**: Verbose output shows details

### Low Coverage

1. **Identify uncovered lines**: `coverage html --show-contexts`
2. **Add tests for missing paths**: Focus on branches
3. **Test error handling**: Often missed
4. **Test edge cases**: Boundary conditions
5. **Test initialization**: Often overlooked

### Slow Tests

1. **Profile tests**: `python -m cProfile -m unittest ...`
2. **Reduce test data**: Use minimal data
3. **Mock expensive operations**: File I/O, network
4. **Run in parallel**: `pytest -n auto`
5. **Skip integration tests**: Run separately

## Resources

- **Coverage Documentation**: https://coverage.readthedocs.io/
- **Unittest Documentation**: https://docs.python.org/3/library/unittest.html
- **Mock Documentation**: https://docs.python.org/3/library/unittest.mock.html
- **Testing Best Practices**: https://docs.python-guide.org/writing/tests/

## Summary

This testing strategy ensures:
- ✅ High coverage (80%+ per tool, 90%+ target)
- ✅ Robust error handling (degraded mode tests)
- ✅ Fast feedback (unit tests < 1s each)
- ✅ Production readiness (integration tests)
- ✅ Maintainability (clear test structure)
- ✅ CI/CD integration (automated testing)
