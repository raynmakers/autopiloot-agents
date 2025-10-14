# TASK-0075 Progress Notes: Standardize env/config loading

## Status: IN PROGRESS

## Completed Work (2025-10-14)

### Phase 1: Core Utilities Fixed ✅

Fixed critical direct `os.getenv` usage in core utilities that are widely used across the codebase:

1. **core/slack_utils.py** - Fixed 8 channel mapping calls
   - Added `get_optional_env_var` import with fallback
   - Replaced all `os.getenv` calls in `get_channel_for_alert_type()` with proper env_loader calls
   - Lines affected: 64-73 (8 environment variables)
   - All calls now include descriptive documentation strings

2. **core/time_utils.py** - Fixed 2 timezone configuration calls
   - Added `get_optional_env_var` import with fallback
   - Replaced `os.getenv` in `get_default_timezone()` and `get_business_timezone()`
   - Lines affected: 307, 317

3. **core/sheets.py** - Fixed 1 credentials path call
   - Added `get_optional_env_var` import with fallback
   - Replaced `os.getenv('GOOGLE_APPLICATION_CREDENTIALS')` in `GoogleSheetsClient.__init__()`
   - Line affected: 94

4. **linkedin_agent/tools/upsert_to_zep_group.py** - Fixed 1 Zep URL call
   - Added `get_optional_env_var` to imports
   - Replaced `os.getenv("ZEP_BASE_URL", ...)` with proper env_loader call
   - Line affected: 85

## Remaining Work

### Phase 2: Agent Tools (20+ files)

Direct `os.getenv` usage still present in agent tools:

**Strategy Agent (6 files)**:
- `generate_content_briefs.py` - Line ~85: `os.getenv("OPENAI_API_KEY")`
- `save_strategy_artifacts.py` - Lines ~90, ~120, ~150: Multiple `os.getenv` calls
- `analyze_tone_of_voice.py` - Line ~80: `os.getenv("OPENAI_API_KEY")`
- `fetch_corpus_from_zep.py` - Line ~75: `os.getenv("ZEP_BASE_URL", ...)`
- `synthesize_strategy_playbook.py` - Line ~90: `os.getenv("OPENAI_API_KEY")`

**Summarizer Agent (3 files)**:
- `generate_short_summary.py` - Lines ~85, ~90: `os.getenv("OPENAI_API_KEY")`, `os.getenv("GCP_PROJECT_ID")`
- `store_short_in_zep.py` - Lines ~80, ~85: `os.getenv("ZEP_BASE_URL", ...)`, `os.getenv("GCP_PROJECT_ID")`
- `save_summary_record.py` - Line ~75: `os.getenv("GCP_PROJECT_ID")`

**Drive Agent (1 file)**:
- `upsert_drive_docs_to_zep.py` - Line ~80: `os.getenv("ZEP_BASE_URL", ...)`

**Scraper Agent (1 file)**:
- `list_recent_uploads.py` - Line 331: `os.getenv("GOOGLE_APPLICATION_CREDENTIALS")`

### Phase 3: sys.path Manipulation (200+ files)

Pattern found throughout codebase:
```python
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
```

**Locations**:
- All agent tool files (~86 tools × 2 path appends = 172 occurrences)
- Test files (~30+ test files with path manipulation)
- Core modules (~10+ files)

**Root Cause**: Circular import issues and config module access from deeply nested tool directories.

**Recommended Approach**:
1. Investigate package structure improvements (proper `__init__.py` files)
2. Consider relative imports where appropriate
3. Use `PYTHONPATH=.` in all execution contexts (documented in CLAUDE.md)
4. Create migration script for bulk cleanup after structure improvements

## Testing Impact

**Tests Run**: None yet - changes are backwards compatible
**Risks**: Low - fallback mechanism maintains compatibility

## Recommendations

### Priority 1: Complete Agent Tools Cleanup
- Fix remaining ~20 agent tool files with direct `os.getenv`
- Pattern is consistent, can be scripted
- Estimated effort: 1-2 hours

### Priority 2: Create Detection Script
- Script to find all direct `os.getenv` usage (excluding config/env_loader.py)
- Script to find all `sys.path` manipulation
- Report locations and suggest fixes
- Estimated effort: 30 minutes

### Priority 3: Test Thoroughly
- Run full test suite after changes
- Verify no import errors
- Check Firebase Functions deployment
- Estimated effort: 1 hour

### Priority 4: Address sys.path (Future)
- Requires deeper architectural analysis
- May need package structure refactoring
- Consider as separate task after env_loader work complete
- Estimated effort: 4-8 hours

## Rollback Plan

If issues arise, changes are easily reversible:
- All changes are in isolated functions
- Fallback mechanism maintains compatibility
- Git history preserved for easy revert

## Next Steps

1. Complete Phase 2 (agent tools)
2. Run comprehensive test suite
3. Create detection/validation script
4. Update TASK-0075 status based on results
5. Consider sys.path work as separate follow-up task
