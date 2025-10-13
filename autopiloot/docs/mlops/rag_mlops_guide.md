# RAG MLOps Guide

## Overview

Comprehensive MLOps practices for the hybrid RAG pipeline to ensure production reliability, prevent regressions, and monitor system health over time.

## Table of Contents

1. [Embedding Model Version Tracking](#embedding-model-version-tracking)
2. [Drift Monitoring](#drift-monitoring)
3. [CI/CD Testing](#cicd-testing)
4. [Model Performance Tracking](#model-performance-tracking)
5. [Data Quality Monitoring](#data-quality-monitoring)
6. [Best Practices](#best-practices)

---

## Embedding Model Version Tracking

### Why Track Model Versions?

- **Targeted Re-embedding**: Identify documents needing refresh after model upgrades
- **Mixed Version Prevention**: Avoid mixing incompatible embedding versions
- **Audit Trail**: Track when and why models were changed
- **Quality Assurance**: Ensure all documents use optimal embedding models

### Current Model Configuration

**File**: `config/settings.yaml`
```yaml
rag:
  mlops:
    model_versioning:
      current_model:
        name: "text-embedding-3-small"  # OpenAI's embedding model
        version: "2024-01-15"  # Release date
        dimension: 1536  # Embedding dimensions
```

### Using the Version Tracking Tool

**Tool**: `summarizer_agent/tools/track_embedding_model_version.py`

#### Operations

**1. Set Version for Document**
```python
from summarizer_agent.tools.track_embedding_model_version import TrackEmbeddingModelVersion

tool = TrackEmbeddingModelVersion(
    operation="set",
    document_id="video_123_chunk_0",
    model_name="text-embedding-3-small",
    model_version="2024-01-15",
    embedding_dimension=1536
)
result = tool.run()
```

**2. Get Version for Document**
```python
tool = TrackEmbeddingModelVersion(
    operation="get",
    document_id="video_123_chunk_0"
)
result = tool.run()
```

**3. List All Versions in Use**
```python
tool = TrackEmbeddingModelVersion(
    operation="list_versions"
)
result = tool.run()

# Example output:
# {
#   "status": "success",
#   "total_documents": 5000,
#   "versions": [
#     {
#       "model_name": "text-embedding-3-small",
#       "model_version": "2024-01-15",
#       "embedding_dimension": 1536,
#       "document_count": 3000
#     },
#     {
#       "model_name": "text-embedding-ada-002",
#       "model_version": "1.0",
#       "embedding_dimension": 1536,
#       "document_count": 2000
#     }
#   ]
# }
```

**4. Check Migration Needed**
```python
tool = TrackEmbeddingModelVersion(
    operation="check_migration_needed",
    target_model_name="text-embedding-3-small",
    model_version="2024-01-15"
)
result = tool.run()

# Example output:
# {
#   "status": "success",
#   "analysis": {
#     "total_documents": 5000,
#     "needs_migration": 2000,
#     "up_to_date": 3000,
#     "migration_percentage": 40.0,
#     "estimated_time_minutes": 6.67
#   }
# }
```

### Model Migration Workflow

**Step 1: Assess Migration Need**
```bash
# Check which documents need migration
python -c "
from summarizer_agent.tools.track_embedding_model_version import TrackEmbeddingModelVersion
tool = TrackEmbeddingModelVersion(
    operation='check_migration_needed',
    target_model_name='text-embedding-3-small',
    model_version='2024-01-15'
)
print(tool.run())
"
```

**Step 2: Update Configuration**
```yaml
# Update config/settings.yaml
rag:
  mlops:
    model_versioning:
      current_model:
        name: "text-embedding-3-large"  # New model
        version: "2024-02-01"
        dimension: 3072  # New dimension
```

**Step 3: Run Migration**
```bash
# Use embeddings refresh script
python scripts/maintenance/refresh_embeddings.py \
  --namespace autopiloot-prod \
  --dry-run  # Preview changes first

# Execute migration
python scripts/maintenance/refresh_embeddings.py \
  --namespace autopiloot-prod
```

**Step 4: Validate Migration**
```bash
# Verify all documents using new model
python -c "
from summarizer_agent.tools.track_embedding_model_version import TrackEmbeddingModelVersion
tool = TrackEmbeddingModelVersion(operation='list_versions')
print(tool.run())
"
```

---

## Drift Monitoring

### What is Drift?

Drift occurs when retrieval behavior changes over time, potentially indicating:
- Data distribution shifts
- Query pattern changes
- Model quality degradation
- System configuration drift

### Drift Metrics Monitored

**Tool**: `summarizer_agent/tools/monitor_rag_drift.py`

#### 1. Token Length Drift

**What**: Changes in document token counts over time
**Why**: Indicates content length shifts or chunking changes
**Threshold**: 20% change triggers alert

**Usage**:
```python
from summarizer_agent.tools.monitor_rag_drift import MonitorRAGDrift

tool = MonitorRAGDrift(
    operation="analyze_drift",
    metric_type="token_length",
    time_range_hours=168  # 7 days
)
result = tool.run()

# Example output:
# {
#   "status": "success",
#   "drift_analysis": {
#     "baseline_average": 800,
#     "current_average": 950,
#     "percent_change": 18.75,
#     "drift_detected": false,
#     "trend": "increasing",
#     "severity": "low"
#   }
# }
```

#### 2. Coverage Drift

**What**: Percentage of queries returning results
**Why**: Declining coverage indicates retrieval quality issues
**Threshold**: 10% drop triggers alert

**Usage**:
```python
tool = MonitorRAGDrift(
    operation="analyze_drift",
    metric_type="coverage",
    time_range_hours=168
)
result = tool.run()
```

#### 3. Source Distribution Drift

**What**: Which retrieval sources (Zep/OpenSearch/BigQuery) are being used
**Why**: Shift indicates routing changes or source issues
**Threshold**: 25% shift triggers alert

**Usage**:
```python
tool = MonitorRAGDrift(
    operation="analyze_drift",
    metric_type="source_distribution",
    time_range_hours=168
)
result = tool.run()

# Example output:
# {
#   "drift_analysis": {
#     "baseline_distribution": {
#       "zep": 0.50,
#       "opensearch": 0.30,
#       "bigquery": 0.20
#     },
#     "current_distribution": {
#       "zep": 0.35,
#       "opensearch": 0.45,
#       "bigquery": 0.20
#     },
#     "drift_detected": true
#   }
# }
```

#### 4. Result Diversity Drift

**What**: Variety in retrieved results
**Why**: Declining diversity indicates result homogeneity
**Threshold**: 20% change triggers alert

**Usage**:
```python
tool = MonitorRAGDrift(
    operation="analyze_drift",
    metric_type="diversity",
    time_range_hours=168
)
result = tool.run()
```

### Recording Metrics

**Automatic Recording** (integrated into retrieval):
```python
# After each retrieval, record metrics
tool = MonitorRAGDrift(
    operation="record_metrics",
    query="business growth strategies",
    token_count=1200,
    results_returned=8,
    sources_used=["zep", "opensearch", "zep", "bigquery"],
    unique_doc_ids=7
)
tool.run()
```

### Analyzing Trends

**Get All Trends**:
```python
tool = MonitorRAGDrift(
    operation="get_trends",
    time_range_hours=168
)
result = tool.run()

# Example output:
# {
#   "trends": {
#     "token_length": { "drift_detected": false, ... },
#     "coverage": { "drift_detected": false, ... },
#     "source_distribution": { "drift_detected": true, ... },
#     "diversity": { "drift_detected": false, ... }
#   },
#   "drift_summary": {
#     "metrics_analyzed": 4,
#     "drift_detected_count": 1,
#     "overall_status": "drift_detected"
#   }
# }
```

### Anomaly Detection

**Detect Statistical Anomalies**:
```python
tool = MonitorRAGDrift(
    operation="detect_anomalies",
    metric_type="token_length",
    time_range_hours=168
)
result = tool.run()

# Example output:
# {
#   "statistics": {
#     "mean": 825,
#     "stdev": 75
#   },
#   "anomalies_detected": 2,
#   "anomalies": [
#     {
#       "timestamp": "2025-01-10T14:00:00Z",
#       "value": 1050,
#       "z_score": 3.0,
#       "deviation_from_mean": 225
#     }
#   ]
# }
```

### Drift Response Workflow

**When Drift is Detected**:

1. **Investigate Root Cause**:
   - Review recent configuration changes
   - Check data ingestion patterns
   - Analyze query patterns
   - Verify model performance

2. **Assess Impact**:
   - Low severity: Monitor
   - Medium severity: Investigate within 24 hours
   - High severity: Immediate investigation

3. **Take Action**:
   - **Token Length Drift**: Review chunking configuration
   - **Coverage Drift**: Check source health, review query routing
   - **Source Distribution Drift**: Investigate routing logic
   - **Diversity Drift**: Review fusion weights, check result deduplication

4. **Document Resolution**:
   - Record findings in incident log
   - Update runbooks if needed
   - Adjust thresholds if false positive

---

## CI/CD Testing

### Test Suite Overview

**File**: `tests/ci/test_hybrid_rag_ci.py`

**15 CI tests** across 5 categories:
- **Functional** (3 tests): Core retrieval and fusion logic
- **Performance** (2 tests): Latency and throughput benchmarks
- **Reliability** (2 tests): Error handling and degraded modes
- **Compatibility** (2 tests): Model version and API compatibility
- **Regression** (3 tests): Prevent known regressions
- **Smoke** (1 test): Quick sanity check

### Running CI Tests

**Manual Execution**:
```bash
cd autopiloot
export PYTHONPATH=.
python -m unittest tests.ci.test_hybrid_rag_ci -v
```

**GitHub Actions Integration**:
```yaml
# .github/workflows/ci.yml
name: RAG CI Tests

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
        run: pip install -r requirements.txt
      - name: Run RAG CI tests
        run: |
          export PYTHONPATH=.
          python -m unittest tests.ci.test_hybrid_rag_ci -v
```

### Performance Benchmarks

**Configured in** `config/settings.yaml`:
```yaml
rag:
  mlops:
    ci_tests:
      benchmarks:
        single_source_latency_ms: 500  # Max latency for single source
        multi_source_latency_ms: 2000  # Max latency for multi-source fusion
        cache_hit_latency_ms: 100  # Max latency for cache hits
        min_cache_hit_ratio: 40  # Minimum cache hit ratio (%)
```

### Test Categories

#### Functional Tests

**1. Retrieval Fusion Quality**:
- Verifies fusion maintains quality standards
- Checks source diversity
- Validates result deduplication
- Ensures relevance ordering

**2. Degraded Mode Handling**:
- Tests graceful handling of source failures
- Validates partial results returned
- Checks error logging

**3. Cache Consistency**:
- Validates cache returns same results
- Checks TTL expiration
- Verifies cache miss handling

#### Performance Tests

**1. Retrieval Latency Benchmark**:
- Single source < 500ms
- Multi-source fusion < 2000ms
- Cached queries < 100ms

**2. Cache Performance Improvement**:
- 80-95% latency reduction on cache hits
- >40% hit ratio on typical workload

#### Reliability Tests

**1. All Sources Failure Handling**:
- System doesn't crash when all sources fail
- Returns appropriate error status
- Logs all failures

**2. Timeout Handling**:
- Doesn't wait indefinitely for slow sources
- Returns results from faster sources
- Marks slow sources as error

#### Compatibility Tests

**1. Model Version Compatibility**:
- System handles mixed embedding versions
- Doesn't crash on version mismatch
- Logs version information

**2. Backward Compatibility**:
- Required parameters unchanged
- Optional parameters have defaults
- Response format consistent

#### Regression Tests

**1. No Empty Results Regression**:
- Prevents regression where fusion incorrectly filters all results

**2. Score Ordering Regression**:
- Ensures results ordered by score descending

**3. Smoke Test**:
- Full pipeline executes without errors

### CI Failure Response

**When CI Tests Fail**:

1. **Identify Category**:
   - Functional: Core logic broken
   - Performance: Performance degradation
   - Reliability: Error handling issue
   - Compatibility: Breaking API change
   - Regression: Known issue reintroduced

2. **Investigate**:
   - Review recent code changes
   - Check test logs for details
   - Reproduce locally

3. **Fix**:
   - Revert breaking change if needed
   - Fix issue and add test coverage
   - Update benchmarks if appropriate

4. **Verify**:
   - Run tests locally
   - Ensure all tests pass
   - Check performance hasn't regressed

---

## Model Performance Tracking

### Metrics Tracked

**Configured in** `config/settings.yaml`:
```yaml
rag:
  mlops:
    performance_tracking:
      metrics:
        relevance:
          methods:
            - "precision@5"
            - "recall@5"
            - "ndcg@10"
        latency:
          percentiles: [50, 95, 99]
        throughput:
          window_minutes: 5
        error_rate:
          track_per_source: true
```

### Baseline Comparison

**Set Baseline**:
```yaml
rag:
  mlops:
    performance_tracking:
      baseline:
        baseline_date: "2025-01-13"
        alert_on_degradation: true
        degradation_threshold: 10.0  # Alert if metrics drop >10%
```

### Performance Monitoring

**Integrated with** `trace_hybrid_retrieval.py`:
- Latency percentiles (p50, p95, p99)
- Per-source performance
- Error rates
- Coverage statistics

**Usage**:
```python
from summarizer_agent.tools.trace_hybrid_retrieval import TraceHybridRetrieval

tool = TraceHybridRetrieval(
    operation="analyze",
    time_range_hours=24
)
result = tool.run()
```

---

## Data Quality Monitoring

### Quality Checks

**1. Completeness**:
- Verify required fields present
- Check for missing embeddings
- Validate metadata completeness

**2. Consistency**:
- Verify embedding dimensions
- Check metadata format
- Validate data types

**3. Freshness**:
- Monitor data age
- Alert on stale data (>90 days)
- Track ingestion lag

### Quality Monitoring Tools

**Health Check Tool**: `scripts/maintenance/health_check_zep.py`
```bash
# Run comprehensive health check
python scripts/maintenance/health_check_zep.py \
  --namespace autopiloot-prod
```

**Checks Performed**:
- Connectivity
- Namespace health
- Embedding integrity
- Retrieval performance
- Orphaned documents

---

## Best Practices

### Model Version Management

1. **Always Track Versions**:
   - Set version on every document
   - Use consistent naming
   - Track dimension changes

2. **Plan Migrations Carefully**:
   - Test new model on sample first
   - Run migration during low-traffic periods
   - Keep old model documents for rollback

3. **Document Changes**:
   - Record why model was changed
   - Note performance differences
   - Update runbooks

### Drift Monitoring

1. **Review Drift Reports Daily**:
   - Check daily digest for drift alerts
   - Investigate medium+ severity drift
   - Document findings

2. **Tune Thresholds**:
   - Adjust based on false positive rate
   - Start conservative, relax as needed
   - Document threshold changes

3. **Proactive Investigation**:
   - Don't wait for critical alerts
   - Monitor trends before they become issues
   - Address root causes, not symptoms

### CI/CD Testing

1. **Never Skip CI**:
   - All code changes must pass CI
   - Don't merge on failing tests
   - Fix tests quickly

2. **Keep Tests Fast**:
   - Aim for <5 minutes total
   - Use mocks for external services
   - Parallel execution where possible

3. **Expand Coverage**:
   - Add tests for new features
   - Test edge cases
   - Update regression tests

### Performance Tracking

1. **Monitor Continuously**:
   - Check performance metrics daily
   - Compare against baseline
   - Alert on degradation

2. **Investigate Anomalies**:
   - Don't ignore performance spikes
   - Check for capacity issues
   - Optimize slow paths

3. **Benchmark Regularly**:
   - Run performance tests weekly
   - Track trends over time
   - Optimize bottlenecks

### Data Quality

1. **Validate on Ingestion**:
   - Check data quality at source
   - Fail fast on bad data
   - Log validation errors

2. **Regular Audits**:
   - Run health checks weekly
   - Sample data for spot checks
   - Fix quality issues promptly

3. **Maintain Freshness**:
   - Archive old data
   - Re-embed periodically
   - Keep data current

---

## Troubleshooting

### Issue: High Drift Detection Rate

**Symptoms**: Many drift alerts, difficult to prioritize

**Solutions**:
- Review and adjust thresholds
- Focus on high-severity drift first
- Check for false positives
- Verify data collection accuracy

### Issue: CI Tests Flaky

**Symptoms**: Tests pass/fail inconsistently

**Solutions**:
- Identify non-deterministic tests
- Fix timing dependencies
- Improve mock reliability
- Add test stability checks

### Issue: Performance Degradation

**Symptoms**: Latency increasing over time

**Solutions**:
- Check index sizes and fragmentation
- Review query patterns
- Optimize slow sources
- Scale infrastructure if needed

### Issue: Model Migration Fails

**Symptoms**: Re-embedding errors, incomplete migration

**Solutions**:
- Check API rate limits
- Reduce batch size
- Retry failed documents
- Verify backup before proceeding

---

## Configuration Reference

### Complete MLOps Configuration

**File**: `config/settings.yaml`
```yaml
rag:
  mlops:
    enabled: true
    model_versioning:
      enabled: true
      current_model:
        name: "text-embedding-3-small"
        version: "2024-01-15"
        dimension: 1536
    drift_monitoring:
      enabled: true
      metrics:
        token_length: { threshold_percentage: 20.0 }
        coverage: { threshold_percentage: 10.0 }
        source_distribution: { threshold_percentage: 25.0 }
        diversity: { threshold_percentage: 20.0 }
    ci_tests:
      enabled: true
      test_suite: "tests/ci/test_hybrid_rag_ci.py"
```

---

## Appendix

### Tools Reference

| Tool | Purpose | Location |
|------|---------|----------|
| `track_embedding_model_version.py` | Track model versions | `summarizer_agent/tools/` |
| `monitor_rag_drift.py` | Monitor drift metrics | `summarizer_agent/tools/` |
| `test_hybrid_rag_ci.py` | CI tests | `tests/ci/` |
| `trace_hybrid_retrieval.py` | Performance tracking | `summarizer_agent/tools/` |

### Metrics Reference

| Metric | Type | Threshold | Frequency |
|--------|------|-----------|-----------|
| Token Length | Drift | 20% change | Daily |
| Coverage | Drift | 10% drop | Daily |
| Source Distribution | Drift | 25% shift | Daily |
| Diversity | Drift | 20% change | Daily |
| Latency p95 | Performance | <2000ms | Real-time |
| Error Rate | Reliability | <5% | Real-time |
| Cache Hit Ratio | Performance | >40% | Hourly |

### Alert Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| **Low** | Minor drift, monitor | 7 days |
| **Medium** | Noticeable drift, investigate | 24 hours |
| **High** | Significant drift, action required | 4 hours |
| **Critical** | System degraded, immediate action | 1 hour |

---

**Last Updated**: 2025-01-13
**Version**: 1.0
**Owner**: Autopiloot Ops Team
