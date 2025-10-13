# RAG System Rollback Procedures

## Overview

Comprehensive rollback procedures for the hybrid RAG pipeline to quickly recover from failed maintenance operations, configuration changes, or system issues.

## Table of Contents

1. [Rollback Decision Matrix](#rollback-decision-matrix)
2. [Embeddings Refresh Rollback](#embeddings-refresh-rollback)
3. [OpenSearch Reindex Rollback](#opensearch-reindex-rollback)
4. [BigQuery Schema Rollback](#bigquery-schema-rollback)
5. [Configuration Rollback](#configuration-rollback)
6. [Cache Rollback](#cache-rollback)
7. [Emergency Rollback](#emergency-rollback)

---

## Rollback Decision Matrix

### When to Rollback

| Situation | Severity | Rollback Required? | Type |
|-----------|----------|-------------------|------|
| Embeddings refresh validation fails | High | Yes | Zep |
| OpenSearch reindex performance degrades | High | Yes | OpenSearch |
| BigQuery query errors post-migration | Critical | Yes | BigQuery |
| Configuration change breaks retrieval | Critical | Yes | Config |
| Cache causing data inconsistency | Medium | Yes | Cache |
| Monitoring shows increased error rate | High | Consider | All |
| User reports retrieval quality issues | Medium | Investigate | All |

### Rollback Thresholds

**Automatic Rollback**:
- Error rate >10% for any source
- Critical validation failure
- Data loss detected

**Manual Rollback Decision**:
- Error rate 5-10%
- Performance degradation >50%
- User impact reports

**Monitor Without Rollback**:
- Error rate 1-5%
- Minor performance degradation
- No user impact

---

## Embeddings Refresh Rollback

### Scenario 1: Validation Fails After Refresh

**Symptoms**:
- Document count mismatch
- Embedding dimension errors
- Retrieval returns empty results

**Rollback Steps**:

#### Step 1: Identify Backup

```bash
# Find backup ID from refresh output logs
# Format: backup_{namespace}_{YYYYMMDD_HHMMSS}
# Example: backup_autopiloot-prod_20250113_143022
```

#### Step 2: Stop Ongoing Operations

```bash
# If refresh is still running, interrupt it
# Press Ctrl+C or kill process

# Verify no other processes are modifying Zep data
ps aux | grep refresh_embeddings
```

#### Step 3: Restore from Backup (Manual)

⚠️ **Current Limitation**: Automated restore not yet implemented. Manual API calls required.

**Manual Restoration via Zep API**:

```bash
# 1. Export backup data (if backup created via API)
curl -X GET "https://api.getzep.com/api/v1/namespaces/autopiloot-prod/backup/{backup_id}" \
  -H "Authorization: Bearer ${ZEP_API_KEY}" \
  > backup_data.json

# 2. Clear corrupted namespace (CAUTION: destructive)
curl -X DELETE "https://api.getzep.com/api/v1/namespaces/autopiloot-prod/documents" \
  -H "Authorization: Bearer ${ZEP_API_KEY}"

# 3. Restore documents from backup
curl -X POST "https://api.getzep.com/api/v1/namespaces/autopiloot-prod/documents/batch" \
  -H "Authorization: Bearer ${ZEP_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @backup_data.json
```

#### Step 4: Validate Restoration

```bash
# Run health check
python scripts/maintenance/health_check_zep.py \
  --namespace autopiloot-prod

# Test retrieval
python -c "
from summarizer_agent.tools.hybrid_retrieval import HybridRetrieval
tool = HybridRetrieval(query='business growth', use_zep=True, top_k=5)
result = tool.run()
print(result)
"
```

#### Step 5: Root Cause Analysis

**Investigate**:
- Why did validation fail?
- Was batch size too large?
- Network connectivity issues?
- API rate limiting?

**Document**:
- Record incident in `docs/maintenance/incidents/`
- Update runbook with lessons learned

### Scenario 2: Partial Refresh Failure

**Symptoms**:
- Some documents refreshed, others failed
- Mixed embedding versions in namespace

**Rollback Steps**:

1. **Identify Failed Documents**:
   ```bash
   # Review refresh_embeddings.py output for failed document IDs
   # Look for "❌ Error refreshing doc_XXX" messages
   ```

2. **Decision Point**:
   - **<10% failed**: Retry failed documents only
   - **>10% failed**: Full rollback recommended

3. **Retry Failed Documents**:
   ```bash
   # Implement selective retry (future enhancement)
   # Currently: full rollback and retry with smaller batch size
   ```

---

## OpenSearch Reindex Rollback

### Scenario 1: Zero-Downtime Alias Switch

**Symptoms**:
- New index has issues
- Performance degraded after switch
- Data integrity problems

**Rollback Steps** (< 5 minutes):

#### Step 1: Switch Alias Back

```bash
# Atomic alias switch back to old index
curl -X POST "https://opensearch-endpoint/_aliases" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Basic ${OS_CREDENTIALS}" \
  -d '{
    "actions": [
      {
        "remove": {
          "index": "transcripts_v2",
          "alias": "transcripts"
        }
      },
      {
        "add": {
          "index": "transcripts_v1",
          "alias": "transcripts"
        }
      }
    ]
  }'
```

**Expected Response**:
```json
{
  "acknowledged": true
}
```

#### Step 2: Verify Alias Switched

```bash
curl -X GET "https://opensearch-endpoint/_alias/transcripts" \
  -H "Authorization: Basic ${OS_CREDENTIALS}"
```

**Expected Response**:
```json
{
  "transcripts_v1": {
    "aliases": {
      "transcripts": {}
    }
  }
}
```

#### Step 3: Test Retrieval

```bash
# Verify retrieval works with old index
python -c "
from summarizer_agent.tools.hybrid_retrieval import HybridRetrieval
tool = HybridRetrieval(query='test query', use_opensearch=True, top_k=5)
result = tool.run()
import json
data = json.loads(result)
assert data['status'] == 'success'
print('✅ Retrieval working with rolled-back index')
"
```

#### Step 4: Delete Problematic Index

```bash
# After confirming old index works correctly
curl -X DELETE "https://opensearch-endpoint/transcripts_v2" \
  -H "Authorization: Basic ${OS_CREDENTIALS}"
```

#### Step 5: Investigate Root Cause

**Common Issues**:
- Mapping incompatibility
- Analyzer configuration errors
- Settings optimization backfired

**Document**:
- What went wrong?
- How to prevent in future?
- Update reindex script if needed

### Scenario 2: Reindex In Progress Failure

**Symptoms**:
- Reindex script crashes mid-process
- Partial document copy
- Target index incomplete

**Rollback Steps**:

#### Step 1: Stop Reindex Process

```bash
# Kill reindex process if still running
pkill -f reindex_opensearch.py

# Check for background reindex tasks
curl -X GET "https://opensearch-endpoint/_tasks?detailed=true&actions=*reindex*" \
  -H "Authorization: Basic ${OS_CREDENTIALS}"
```

#### Step 2: Delete Incomplete Target Index

```bash
curl -X DELETE "https://opensearch-endpoint/transcripts_v2" \
  -H "Authorization: Basic ${OS_CREDENTIALS}"
```

#### Step 3: Verify Source Index Intact

```bash
# Source index should be unchanged
curl -X GET "https://opensearch-endpoint/transcripts_v1/_count" \
  -H "Authorization: Basic ${OS_CREDENTIALS}"
```

#### Step 4: Retry with Smaller Batch Size

```bash
# Reduce batch size and retry
python scripts/maintenance/reindex_opensearch.py \
  --source transcripts_v1 \
  --target transcripts_v2 \
  --batch-size 500 \
  --dry-run

# If dry-run looks good, execute
python scripts/maintenance/reindex_opensearch.py \
  --source transcripts_v1 \
  --target transcripts_v2 \
  --batch-size 500
```

---

## BigQuery Schema Rollback

### Scenario: Schema Change Breaks Queries

**Symptoms**:
- SQL queries returning errors
- Missing or renamed columns
- Data type mismatches

**Rollback Steps**:

#### Step 1: Identify Backup

```bash
# List available backups
gsutil ls gs://autopiloot-backups/transcripts_*

# Example backup:
# gs://autopiloot-backups/transcripts_backup_20250113/
```

#### Step 2: Create Temporary Table

```bash
# Don't overwrite production table immediately
bq mk --table autopiloot:youtube_transcripts.transcripts_rollback

# Load backup data into temp table
bq load --source_format=AVRO \
  autopiloot:youtube_transcripts.transcripts_rollback \
  gs://autopiloot-backups/transcripts_backup_20250113/*.avro
```

#### Step 3: Validate Backup Data

```bash
# Check row count
bq query --use_legacy_sql=false '
SELECT COUNT(*) as row_count
FROM `autopiloot.youtube_transcripts.transcripts_rollback`
'

# Verify schema matches expected
bq show --schema --format=prettyjson \
  autopiloot:youtube_transcripts.transcripts_rollback
```

#### Step 4: Swap Tables (Atomic)

```bash
# Rename current table to _broken
bq cp --force \
  autopiloot:youtube_transcripts.transcripts \
  autopiloot:youtube_transcripts.transcripts_broken

# Rename rollback table to production
bq cp --force \
  autopiloot:youtube_transcripts.transcripts_rollback \
  autopiloot:youtube_transcripts.transcripts
```

#### Step 5: Test Queries

```bash
# Run sample queries
python -c "
from summarizer_agent.tools.hybrid_retrieval import HybridRetrieval
tool = HybridRetrieval(query='test', use_bigquery=True, top_k=5)
result = tool.run()
print(result)
"
```

#### Step 6: Cleanup

```bash
# After confirming rollback successful (24-48 hours)
bq rm -f autopiloot:youtube_transcripts.transcripts_broken
bq rm -f autopiloot:youtube_transcripts.transcripts_rollback
```

---

## Configuration Rollback

### Scenario: Settings.yaml Change Breaks RAG

**Symptoms**:
- Configuration loading errors
- Invalid parameter values
- Retrieval failures

**Rollback Steps**:

#### Step 1: Git Revert

```bash
# View recent config changes
git log --oneline config/settings.yaml

# Revert to previous version
git checkout HEAD~1 -- config/settings.yaml

# Or revert specific commit
git checkout <commit-hash> -- config/settings.yaml
```

#### Step 2: Validate Configuration

```bash
# Test configuration loads correctly
python -c "
from core.config_loader import ConfigLoader
config = ConfigLoader()
print('✅ Configuration valid')
"
```

#### Step 3: Restart Services

```bash
# If agency running, restart to load old config
# (Manual restart required)
```

#### Step 4: Verify Retrieval

```bash
python -c "
from summarizer_agent.tools.hybrid_retrieval import HybridRetrieval
tool = HybridRetrieval(query='test', top_k=5)
result = tool.run()
print(result)
"
```

#### Step 5: Document Issue

```bash
# Commit reverted config
git add config/settings.yaml
git commit -m "revert: rollback settings.yaml to previous version due to [issue]"
git push
```

---

## Cache Rollback

### Scenario: Cache Serving Stale Data

**Symptoms**:
- Retrieval returns outdated results
- Cache hit ratio unexpectedly high
- User reports stale content

**Rollback Steps**:

#### Step 1: Clear Cache Immediately

```bash
# Memory backend
python -c "
from summarizer_agent.tools.cache_hybrid_retrieval import CacheHybridRetrieval
tool = CacheHybridRetrieval(backend='memory', operation='clear')
result = tool.run()
print(result)
"

# Redis backend (if using)
redis-cli FLUSHDB
```

#### Step 2: Disable Cache Temporarily

```bash
# Edit config/settings.yaml
# Set cache.enabled: false

# Or set environment variable
export RAG_CACHE_ENABLED=false
```

#### Step 3: Verify Fresh Results

```bash
python -c "
from summarizer_agent.tools.hybrid_retrieval import HybridRetrieval
tool = HybridRetrieval(query='test', top_k=5)
result = tool.run()
# Should fetch fresh results from sources
print(result)
"
```

#### Step 4: Investigate Root Cause

**Common Issues**:
- TTL too long
- Cache invalidation logic broken
- Bypass rules not working

#### Step 5: Fix and Re-enable

```bash
# After fixing issue:
# - Adjust TTL in settings.yaml
# - Fix cache invalidation logic
# - Update bypass rules

# Re-enable cache
export RAG_CACHE_ENABLED=true
```

---

## Emergency Rollback

### Complete System Failure

**Symptoms**:
- All sources returning errors
- Multiple components failing
- Critical service disruption

**Emergency Steps**:

#### Step 1: Declare Incident

```bash
# Alert team immediately
# Slack: #ops-autopiloot
# Message: "🚨 RAG SYSTEM EMERGENCY - All sources down"
```

#### Step 2: Stop All Maintenance

```bash
# Kill all running maintenance scripts
pkill -f refresh_embeddings
pkill -f reindex_opensearch
pkill -f health_check

# Pause any scheduled jobs
# (Via Cloud Scheduler or cron)
```

#### Step 3: Check Recent Changes

```bash
# Review recent commits
git log --oneline --since="24 hours ago"

# Review recent deployments
# Check Cloud Console for function deployments
```

#### Step 4: Rollback Recent Changes

```bash
# Rollback code
git revert <problematic-commit>
git push

# Rollback configuration
git checkout HEAD~1 -- config/settings.yaml
git push

# Redeploy if needed
firebase deploy --only functions
```

#### Step 5: Validate Services

```bash
# Health check each source independently
python scripts/maintenance/health_check_zep.py --namespace autopiloot-prod

curl -X GET "https://opensearch-endpoint/_cluster/health"

bq ls autopiloot:youtube_transcripts
```

#### Step 6: Gradual Recovery

1. Enable one source at a time
2. Validate retrieval works
3. Monitor error rates
4. Enable next source

#### Step 7: Post-Mortem

- Document incident timeline
- Identify root cause
- Create prevention measures
- Update runbooks

---

## Rollback Validation Checklist

After any rollback, verify:

- [ ] All sources responding (Zep, OpenSearch, BigQuery)
- [ ] Health checks passing
- [ ] Retrieval returning expected results
- [ ] Error rates back to normal (<1%)
- [ ] Latency within acceptable range (p95 <500ms)
- [ ] Cache functioning correctly (if enabled)
- [ ] No data loss detected
- [ ] User-facing features working
- [ ] Monitoring and alerts operational

---

## Prevention Strategies

### Always Use Dry-Run First

```bash
# ALWAYS run dry-run before actual execution
python scripts/maintenance/refresh_embeddings.py --dry-run
python scripts/maintenance/reindex_opensearch.py --dry-run
```

### Maintain Current Backups

```bash
# Automate backup creation
# Schedule weekly backups via cron
0 2 * * 0 /path/to/backup_script.sh
```

### Use Gradual Rollouts

```bash
# Test on dev namespace first
python scripts/maintenance/refresh_embeddings.py \
  --namespace autopiloot-dev

# Then production
python scripts/maintenance/refresh_embeddings.py \
  --namespace autopiloot-prod
```

### Monitor Continuously

```bash
# Set up alerts for:
# - Error rate >5%
# - Latency p95 >1000ms
# - Document count drops
# - Service health failures
```

---

## Rollback Time Estimates

| Operation | Rollback Time | Downtime | Difficulty |
|-----------|---------------|----------|------------|
| OpenSearch Alias Switch | 1-2 minutes | None (zero-downtime) | Easy |
| Cache Clear | <1 minute | None | Easy |
| Configuration Revert | 5-10 minutes | None | Easy |
| BigQuery Schema | 15-30 minutes | Partial | Medium |
| Zep Embeddings | 30-60 minutes | Partial | Hard |
| Complete System | 1-2 hours | Full | Hard |

---

## Contacts and Escalation

**L1 Support**:
- Try automated rollback procedures
- Follow runbook step-by-step
- Document all actions

**L2 Escalation**:
- Complex rollback scenarios
- Multiple component failures
- Data integrity concerns

**L3 Escalation**:
- Complete system failure
- Data loss detected
- Architectural issues

**Emergency Contact**: See PagerDuty on-call rotation

---

## Appendix

### Rollback Scripts

Future enhancements to automate rollback:

```bash
# Proposed automated rollback script
scripts/maintenance/rollback_rag.py \
  --component zep \
  --backup-id backup_autopiloot-prod_20250113_143022

scripts/maintenance/rollback_rag.py \
  --component opensearch \
  --alias transcripts \
  --revert-to transcripts_v1
```

### Backup Retention Policy

- **Zep**: 30 days
- **OpenSearch**: Manual cleanup (keep until deleted)
- **BigQuery**: 90 days in Cloud Storage

### Compliance

- All rollbacks logged to audit trail
- Incident reports filed within 24 hours
- Root cause analysis completed within 1 week

---

**Last Updated**: 2025-01-13
**Version**: 1.0
**Owner**: Autopiloot Ops Team
