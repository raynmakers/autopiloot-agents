# Test Coverage Quick Reference

## The Golden Rule

**ALWAYS isolate tests by agent-specific directory to prevent coverage interference.**

## Quick Commands

```bash
# Drive Agent
coverage erase && coverage run --source=drive_agent -m unittest discover tests/drive_tools -p "test_*.py" && coverage report --include="drive_agent/*" && coverage html --include="drive_agent/*" -d coverage/drive_agent

# Summarizer Agent  
coverage erase && coverage run --source=summarizer_agent -m unittest discover tests/summarizer_tools -p "test_*.py" && coverage report --include="summarizer_agent/*" && coverage html --include="summarizer_agent/*" -d coverage/summarizer_agent

# Orchestrator Agent
coverage erase && coverage run --source=orchestrator_agent -m unittest discover tests/orchestrator_tools -p "test_*.py" && coverage report --include="orchestrator_agent/*" && coverage html --include="orchestrator_agent/*" -d coverage/orchestrator_agent

# LinkedIn Agent
coverage erase && coverage run --source=linkedin_agent -m unittest discover tests/linkedin_tools -p "test_*.py" && coverage report --include="linkedin_agent/*" && coverage html --include="linkedin_agent/*" -d coverage/linkedin_agent

# Observability Agent
coverage erase && coverage run --source=observability_agent -m unittest discover tests/observability_tools -p "test_*.py" && coverage report --include="observability_agent/*" && coverage html --include="observability_agent/*" -d coverage/observability_agent

# Strategy Agent
coverage erase && coverage run --source=strategy_agent -m unittest discover tests/strategy_tools -p "test_*.py" && coverage report --include="strategy_agent/*" && coverage html --include="strategy_agent/*" -d coverage/strategy_agent

# Transcriber Agent (legacy - use specific modules)
coverage erase && coverage run --source=transcriber_agent -m unittest tests.test_get_video_audio_url tests.test_poll_transcription_job tests.test_save_transcript_record tests.test_store_transcript_to_drive tests.test_submit_assemblyai_job && coverage report --include="transcriber_agent/*" && coverage html --include="transcriber_agent/*" -d coverage/transcriber_agent

# Scraper Agent (legacy - use specific modules)
coverage erase && coverage run --source=scraper_agent -m unittest tests.test_extract_youtube_from_page tests.test_resolve_channel_handles tests.test_list_recent_uploads tests.test_save_video_metadata tests.test_read_sheet_links tests.test_remove_sheet_row tests.test_enqueue_transcription && coverage report --include="scraper_agent/*" && coverage html --include="scraper_agent/*" -d coverage/scraper_agent
```

## ✅ DO

- Use `coverage erase` before each test run
- Specify agent-specific test directory with `discover`
- Run specific test modules for legacy tests in root `tests/`
- Check HTML report: `coverage/{agent}/index.html`
- Verify "Module was never imported" warnings are absent

## ❌ DON'T

- Use `discover tests -p "test_*.py"` without subdirectory (picks up 296+ files!)
- Mix tests from different agents in the same run
- Skip `coverage erase` (causes cumulative data corruption)
- Trust coverage numbers without checking HTML report

## Test Directory Mapping

| Agent | Test Directory | Command Pattern |
|-------|---------------|-----------------|
| drive_agent | `tests/drive_tools/` | `discover tests/drive_tools` |
| summarizer_agent | `tests/summarizer_tools/` | `discover tests/summarizer_tools` |
| orchestrator_agent | `tests/orchestrator_tools/` | `discover tests/orchestrator_tools` |
| linkedin_agent | `tests/linkedin_tools/` | `discover tests/linkedin_tools` |
| observability_agent | `tests/observability_tools/` | `discover tests/observability_tools` |
| strategy_agent | `tests/strategy_tools/` | `discover tests/strategy_tools` |
| transcriber_agent | `tests/` (legacy) | Specific module names |
| scraper_agent | `tests/` (legacy) | Specific module names |

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| Coverage drops from 90% to 32% | Test interference | Use agent-specific directory |
| "Module was never imported" | Import strategy conflict | Isolate tests by agent |
| Coverage shows 0% | Over-mocking | Check import strategy in tests |
| Inconsistent results | Mixing agent tests | Separate test runs per agent |
| HTML ≠ Terminal | Old .coverage data | Run `coverage erase` first |

## View Results

```bash
# Open HTML report in browser
open coverage/{agent}/index.html

# Or on Linux
xdg-open coverage/{agent}/index.html

# Quick terminal view
coverage report --include="{agent}/*" --show-missing
```

## Coverage Targets

- ✅ **Perfect (100%)**: Fully covered, production ready
- ✅ **Excellent (90%+)**: High confidence, minimal risk  
- ✅ **Good (80%+)**: Meets minimum threshold
- ⚠️ **Needs Improvement (<80%)**: Add tests before shipping

## One-Liner Check

```bash
# Quick status check for all agents
for agent in drive summarizer orchestrator linkedin observability strategy; do
  echo "=== ${agent}_agent ===" 
  coverage erase && coverage run --source=${agent}_agent -m unittest discover tests/${agent}_tools -p "test_*.py" 2>/dev/null && coverage report --include="${agent}_agent/*" | tail -1
done
```

---

**Quick Tip**: Bookmark this file or add these commands to your shell aliases for instant access!
