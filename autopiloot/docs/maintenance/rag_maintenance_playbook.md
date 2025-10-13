# Hybrid RAG Maintenance Playbook

## Overview

Comprehensive maintenance procedures for the hybrid RAG pipeline ensuring optimal performance, data integrity, and system health across Zep (semantic search), OpenSearch (keyword search), and BigQuery (SQL analytics).

## Table of Contents

1. [Routine Maintenance](#routine-maintenance)
2. [Embeddings Refresh](#embeddings-refresh)
3. [Zep Health Checks](#zep-health-checks)
4. [OpenSearch Reindexing](#opensearch-reindexing)
5. [BigQuery Optimization](#bigquery-optimization)
6. [Performance Monitoring](#performance-monitoring)
7. [Troubleshooting Guide](#troubleshooting-guide)
8. [Rollback Procedures](#rollback-procedures)

---

## Routine Maintenance

### Daily Tasks

**Automated (via Observability Agent)**:
- Monitor retrieval latency percentiles (p50, p95, p99)
- Track error rates across all sources
- Check cache hit ratios
- Monitor source availability

**Manual Review**:
- Review daily digest for anomalies
- Check dead letter queue for failed operations
- Validate budget and cost tracking

### Weekly Tasks

1. **Health Check All Sources**
   ```bash
   # Zep health check
   python scripts/maintenance/health_check_zep.py --namespace autopiloot-prod

   # Review OpenSearch cluster health
   curl -X GET "https://opensearch-endpoint/_cluster/health?pretty"

   # Check BigQuery dataset statistics
   bq show --format=prettyjson autopiloot:youtube_transcripts
   ```

2. **Review Performance Metrics**
   - Check tracing data for degraded sources
   - Analyze query patterns and cache effectiveness
   - Review fusion weight performance

3. **Data Integrity Validation**
   - Sample retrieval queries across all sources
   - Verify document counts match expectations
   - Check for orphaned documents

### Monthly Tasks

1. **Embeddings Model Evaluation**
   - Review embedding model performance
   - Consider upgrading to newer models
   - Plan embeddings refresh if model changed

2. **Index Optimization**
   - Review OpenSearch index sizes and fragmentation
   - Consider reindexing if performance degraded
   - Optimize BigQuery table partitioning

3. **Capacity Planning**
   - Review storage growth trends
   - Forecast resource requirements
   - Plan scaling if needed

---

## Embeddings Refresh

### When to Refresh Embeddings

Refresh embeddings when:
- Upgrading to a new embedding model
- Embeddings corrupted or missing
- Changing embedding dimensions
- After bulk document imports

### Refresh Procedure

**Script**: `scripts/maintenance/refresh_embeddings.py`

#### Step 1: Dry Run (Required)

```bash
cd autopiloot
python scripts/maintenance/refresh_embeddings.py \
  --namespace autopiloot-prod \
  --dry-run
```

**Expected Output**:
```
🔄 Zep Embeddings Refresh
⚠️  DRY RUN MODE - No changes will be made

📋 Scanning namespace: autopiloot-prod
   Found 5000 total documents
   1200 need embedding refresh

💾 [DRY RUN] Would create backup: backup_autopiloot-prod_20250115_143022

🔄 Refreshing embeddings (batch size: 100)
   [DRY RUN] Would refresh 1200 documents in 12 batches
```

#### Step 2: Review Dry Run Output

- Verify document counts are expected
- Check backup ID format
- Estimate time: ~5-10 documents per second

#### Step 3: Execute Refresh

```bash
# Standard batch size (100 documents)
python scripts/maintenance/refresh_embeddings.py \
  --namespace autopiloot-prod

# Larger batch size for faster processing
python scripts/maintenance/refresh_embeddings.py \
  --namespace autopiloot-prod \
  --batch-size 200
```

#### Step 4: Validate Results

**Automatic Validation**:
- Document count comparison
- Embedding dimension check
- Sample retrieval test

**Manual Validation**:
```bash
# Test retrieval with sample queries
python -c "
from summarizer_agent.tools.hybrid_retrieval import HybridRetrieval
tool = HybridRetrieval(query='business growth strategies', use_zep=True, top_k=5)
result = tool.run()
print(result)
"
```

### Troubleshooting

**Issue: Embeddings refresh fails mid-process**
- Check `backup_autopiloot-prod_TIMESTAMP` backup exists
- Review error logs for specific failures
- Retry with smaller `--batch-size`
- See [Rollback Procedures](#rollback-procedures)

**Issue: Validation fails after refresh**
- Document count mismatch may indicate partial failure
- Check Zep API logs for rate limiting or timeouts
- Consider rollback and retry with smaller batches

---

## Zep Health Checks

### When to Run Health Checks

- Weekly routine maintenance
- After embeddings refresh
- When retrieval performance degrades
- Before major updates

### Health Check Procedure

**Script**: `scripts/maintenance/health_check_zep.py`

#### Quick Health Check

```bash
python scripts/maintenance/health_check_zep.py \
  --namespace autopiloot-prod \
  --dry-run
```

**Checks Performed**:
1. ✅ Connectivity - Zep service reachable
2. ✅ Namespace Health - Document count and configuration
3. ✅ Embedding Integrity - Embeddings present and valid
4. ✅ Retrieval Performance - Query latency < 500ms
5. ✅ Orphaned Documents - Missing metadata or duplicates

**Example Output**:
```
🏥 Zep Health Check

🔌 Checking Zep connectivity...
   ✅ Connectivity check passed

📁 Checking namespace health: autopiloot-prod
   ✅ Namespace health OK (5000 documents)

🔍 Checking embedding integrity
   ✅ All embeddings intact (5000/5000)

⚡ Checking retrieval performance
   ✅ Retrieval performance OK (avg: 245ms)

🗑️  Checking for orphaned documents
   ⚠️  3 orphaned documents; 1 duplicate documents

📊 Health Check Summary
Overall Status: ⚠️ WARNING
Checks Run: 5
Issues Found: 0
Warnings: 1
```

#### Fix Issues Automatically

```bash
# Automatically fix detected issues
python scripts/maintenance/health_check_zep.py \
  --namespace autopiloot-prod \
  --fix
```

**Fixes Applied**:
- Remove orphaned documents
- Deduplicate duplicate entries
- Restore missing metadata from source

#### Export Health Report

```bash
# Export detailed report for audit trail
python scripts/maintenance/health_check_zep.py \
  --namespace autopiloot-prod \
  --output reports/zep_health_$(date +%Y%m%d).json
```

### Interpreting Health Status

**Status Levels**:
- ✅ **Healthy**: All checks passed, no issues
- ⚠️ **Warning**: Minor issues detected, system functional
- 🔶 **Degraded**: Multiple issues, performance impacted
- 🔴 **Critical**: Critical failures, immediate action required

**Critical Issues**:
- Zep service unreachable
- >10% documents missing embeddings
- Retrieval latency >2000ms

**Warning Issues**:
- <10 documents in namespace (low volume)
- 1-10% documents with missing metadata
- Retrieval latency 500-2000ms
- Orphaned or duplicate documents

---

## OpenSearch Reindexing

### When to Reindex

Reindex OpenSearch when:
- Updating index mappings or settings
- Optimizing index performance
- Changing analyzer configuration
- After bulk deletions (defragmentation)

### Reindex Procedure (Zero Downtime)

**Script**: `scripts/maintenance/reindex_opensearch.py`

#### Step 1: Dry Run

```bash
python scripts/maintenance/reindex_opensearch.py \
  --source transcripts_v1 \
  --target transcripts_v2 \
  --alias transcripts \
  --dry-run
```

**What Happens**:
- Creates new index with updated settings
- Copies documents in batches
- Validates document count
- Switches alias atomically
- Preserves old index for rollback

#### Step 2: Execute Reindex

```bash
# Reindex with alias switch (zero downtime)
python scripts/maintenance/reindex_opensearch.py \
  --source transcripts_v1 \
  --target transcripts_v2 \
  --alias transcripts \
  --batch-size 1000
```

**Expected Output**:
```
🔄 OpenSearch Reindex

Source Index: transcripts_v1
Target Index: transcripts_v2
Alias: transcripts

⚙️  Retrieving settings for index: transcripts_v1
   ✅ Retrieved settings

🏗️  Creating target index: transcripts_v2
   ✅ Created target index

📊 Source document count: 5000

🔄 Reindexing documents (batch size: 1000)
📦 Processing batch 1/5 (1000 documents)
   ✅ Reindexed 1000 documents
...

✅ Validating reindex
   Source documents: 5000
   Target documents: 5000
   ✅ Document counts match

🔄 Switching alias 'transcripts' from transcripts_v1 to transcripts_v2
   ✅ Alias 'transcripts' now points to transcripts_v2

📊 Reindex Summary
Status: SUCCESS
Source documents: 5000
Target documents: 5000
Documents copied: 5000
Documents failed: 0
```

#### Step 3: Validate Application

```bash
# Test retrieval with new index
python -c "
from summarizer_agent.tools.hybrid_retrieval import HybridRetrieval
tool = HybridRetrieval(query='test query', use_opensearch=True, top_k=5)
result = tool.run()
print(result)
"
```

#### Step 4: Delete Old Index (Optional)

```bash
# After validating new index works correctly (e.g., 24 hours)
python scripts/maintenance/reindex_opensearch.py \
  --source transcripts_v1 \
  --delete-source
```

⚠️ **Warning**: Only delete old index after thorough validation. Keep for rollback capability.

### Custom Batch Sizes

**Small Datasets (<10k docs)**:
```bash
--batch-size 500
```

**Large Datasets (>100k docs)**:
```bash
--batch-size 2000 --parallel-shards 3
```

**Memory-Constrained**:
```bash
--batch-size 250
```

---

## BigQuery Optimization

### Partition Management

**Check Partition Sizes**:
```bash
bq query --use_legacy_sql=false '
SELECT
  partition_id,
  total_rows,
  total_logical_bytes / 1024 / 1024 / 1024 AS size_gb
FROM
  `autopiloot.youtube_transcripts.INFORMATION_SCHEMA.PARTITIONS`
ORDER BY
  partition_id DESC
LIMIT 10
'
```

### Table Optimization

**Recreate Table with Optimized Schema**:
```bash
# Export data
bq extract --destination_format=AVRO \
  autopiloot:youtube_transcripts.transcripts_v1 \
  gs://autopiloot-backups/transcripts_export/*.avro

# Create new table with optimized schema
bq mk --table \
  --schema=config/bigquery/schema_v2.json \
  autopiloot:youtube_transcripts.transcripts_v2

# Load data
bq load --source_format=AVRO \
  autopiloot:youtube_transcripts.transcripts_v2 \
  gs://autopiloot-backups/transcripts_export/*.avro
```

### Cost Optimization

**Enable Query Cache**:
- Set `cache: enabled` in `config/settings.yaml`
- Use `cache_hybrid_retrieval.py` for frequent queries

**Partition Pruning**:
```python
# Use date filters to minimize scanned data
filters = {
    "date_range": {
        "start": "2025-01-01",
        "end": "2025-01-31"
    }
}
```

---

## Performance Monitoring

### Retrieval Latency

**Track Percentiles**:
```bash
# Check tracing data for latency trends
python -c "
from summarizer_agent.tools.trace_hybrid_retrieval import TraceHybridRetrieval
tool = TraceHybridRetrieval(
    operation='analyze',
    time_range_hours=24
)
result = tool.run()
print(result)
"
```

**Latency Thresholds**:
- p50 < 200ms: Excellent
- p95 < 500ms: Good
- p99 < 1000ms: Acceptable
- p99 > 2000ms: Action required

### Cache Performance

**Monitor Hit Ratios**:
```bash
python -c "
from summarizer_agent.tools.cache_hybrid_retrieval import CacheHybridRetrieval
tool = CacheHybridRetrieval(backend='memory', operation='stats')
result = tool.run()
print(result)
"
```

**Target Hit Ratios**:
- >60%: Excellent (cache working well)
- 40-60%: Good (typical workload)
- <40%: Review cache TTL and bypass rules

### Error Rate Tracking

**Check Error Rates by Source**:
```bash
# Use trace analysis
python summarizer_agent/tools/trace_hybrid_retrieval.py
```

**Error Rate Thresholds**:
- <1%: Normal operation
- 1-5%: Monitor closely
- >5%: Investigation required

---

## Troubleshooting Guide

### Issue: High Retrieval Latency

**Symptoms**:
- p95 latency >1000ms
- User complaints about slow responses

**Investigation**:
```bash
# Check source-specific latency
python -c "
from summarizer_agent.tools.trace_hybrid_retrieval import TraceHybridRetrieval
tool = TraceHybridRetrieval(operation='analyze', time_range_hours=24)
print(tool.run())
"
```

**Common Causes**:
1. **Zep**: Large namespace, need index optimization
2. **OpenSearch**: Index fragmentation, consider reindex
3. **BigQuery**: Large partition scans, add filters

**Solutions**:
- Run health checks on slow source
- Consider caching for frequent queries
- Optimize query patterns
- Scale infrastructure if needed

### Issue: Missing or Corrupted Embeddings

**Symptoms**:
- Zep returns empty results
- Health check shows missing embeddings

**Investigation**:
```bash
python scripts/maintenance/health_check_zep.py \
  --namespace autopiloot-prod
```

**Solution**:
```bash
# Refresh embeddings
python scripts/maintenance/refresh_embeddings.py \
  --namespace autopiloot-prod
```

### Issue: Degraded Mode Triggered

**Symptoms**:
- One or more sources consistently failing
- Error rate >5% for specific source

**Investigation**:
1. Check source health directly
2. Review error logs in `trace_hybrid_retrieval`
3. Verify credentials and connectivity

**Solutions**:
- **Zep**: Check API key, service status
- **OpenSearch**: Verify auth, check cluster health
- **BigQuery**: Check IAM permissions, quota limits

### Issue: Cache Not Improving Performance

**Symptoms**:
- Low cache hit ratio (<40%)
- No latency improvement

**Investigation**:
```bash
python -c "
from summarizer_agent.tools.cache_hybrid_retrieval import CacheHybridRetrieval
tool = CacheHybridRetrieval(backend='memory', operation='stats')
print(tool.run())
"
```

**Common Causes**:
1. TTL too short
2. Query patterns too diverse
3. Cache backend inadequate

**Solutions**:
- Increase TTL in `config/settings.yaml`
- Review query normalization
- Consider upgrading to Redis backend

---

## Rollback Procedures

### Embeddings Refresh Rollback

**When to Rollback**:
- Validation fails after refresh
- Critical errors during refresh
- Retrieval quality degraded

**Procedure**:
1. Identify backup ID from refresh output
2. Restore from backup (manual process)
3. Verify restoration with health check

**Note**: Current implementation creates backup ID but restoration requires manual Zep API calls. Future enhancement: automated rollback.

### OpenSearch Reindex Rollback

**When to Rollback**:
- New index has issues
- Performance degraded
- Data integrity problems

**Procedure**:
```bash
# Switch alias back to old index (instant)
curl -X POST "https://opensearch-endpoint/_aliases" -H 'Content-Type: application/json' -d'
{
  "actions": [
    { "remove": { "index": "transcripts_v2", "alias": "transcripts" }},
    { "add": { "index": "transcripts_v1", "alias": "transcripts" }}
  ]
}
'

# Verify alias switched
curl -X GET "https://opensearch-endpoint/_alias/transcripts"

# Delete problematic new index
curl -X DELETE "https://opensearch-endpoint/transcripts_v2"
```

**Validation**:
```bash
# Test retrieval with rolled-back index
python -c "
from summarizer_agent.tools.hybrid_retrieval import HybridRetrieval
tool = HybridRetrieval(query='test query', use_opensearch=True, top_k=5)
result = tool.run()
print(result)
"
```

### BigQuery Rollback

**When to Rollback**:
- Schema changes break queries
- Data loss detected
- Performance issues

**Procedure**:
```bash
# Restore from backup
bq load --source_format=AVRO \
  --replace \
  autopiloot:youtube_transcripts.transcripts \
  gs://autopiloot-backups/transcripts_backup_TIMESTAMP/*.avro
```

---

## Emergency Procedures

### Complete System Outage

**Symptoms**:
- All sources returning errors
- Critical services down

**Immediate Actions**:
1. Check service status pages (Zep, OpenSearch, BigQuery)
2. Verify credentials and API keys valid
3. Check network connectivity
4. Review recent configuration changes

**Communication**:
- Alert team via Slack
- Create incident ticket
- Update status page

### Data Loss Detected

**Symptoms**:
- Document count decreased unexpectedly
- Critical documents missing

**Immediate Actions**:
1. **DO NOT** run any maintenance scripts
2. Identify scope of data loss
3. Locate most recent backup
4. Assess restoration time

**Recovery**:
- Restore from most recent backup
- Verify data integrity post-restoration
- Conduct root cause analysis

---

## Backup Strategy

### Automated Backups

**Zep**:
- Backup created automatically during embeddings refresh
- Retention: 30 days

**OpenSearch**:
- Old indices preserved after reindex
- Manual deletion required
- Retention: Until manually removed

**BigQuery**:
- Snapshots via `bq extract` before schema changes
- Retention: 90 days in Cloud Storage

### Manual Backups

**Before Major Changes**:
```bash
# Zep: Export namespace (manual API calls required)
# OpenSearch: Snapshot repository
# BigQuery: Export to Cloud Storage
bq extract --destination_format=AVRO \
  autopiloot:youtube_transcripts.transcripts \
  gs://autopiloot-backups/manual_backup_$(date +%Y%m%d)/*.avro
```

---

## Maintenance Checklist

### Pre-Maintenance

- [ ] Review recent alerts and errors
- [ ] Check system health status
- [ ] Verify backups are current
- [ ] Schedule maintenance window
- [ ] Notify team of maintenance

### During Maintenance

- [ ] Run dry-run first
- [ ] Monitor progress and logs
- [ ] Validate at each step
- [ ] Be ready to rollback

### Post-Maintenance

- [ ] Validate all sources operational
- [ ] Test retrieval functionality
- [ ] Monitor performance metrics
- [ ] Document changes and results
- [ ] Update team on completion

---

## Contacts and Resources

**Internal**:
- Observability Agent: Automated monitoring
- Slack Channel: #ops-autopiloot
- On-Call: See PagerDuty rotation

**External**:
- Zep Documentation: https://docs.getzep.com/
- OpenSearch Documentation: https://opensearch.org/docs/
- BigQuery Documentation: https://cloud.google.com/bigquery/docs

---

## Appendix

### Script Reference

| Script | Purpose | Location |
|--------|---------|----------|
| `refresh_embeddings.py` | Refresh Zep embeddings | `scripts/maintenance/` |
| `health_check_zep.py` | Zep health validation | `scripts/maintenance/` |
| `reindex_opensearch.py` | OpenSearch reindexing | `scripts/maintenance/` |

### Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| `settings.yaml` | RAG configuration | `config/settings.yaml` |
| `.env` | Credentials and API keys | `.env` |

### Monitoring Tools

| Tool | Purpose | Agent |
|------|---------|-------|
| `trace_hybrid_retrieval.py` | Performance tracing | Summarizer |
| `cache_hybrid_retrieval.py` | Cache management | Summarizer |
| `validate_rag_security.py` | Security validation | Summarizer |

---

**Last Updated**: 2025-01-13
**Version**: 1.0
**Owner**: Autopiloot Ops Team
