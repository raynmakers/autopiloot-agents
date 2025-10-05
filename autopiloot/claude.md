# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Autopiloot is a production-ready Agency Swarm v1.0.0 multi-agent system for automated YouTube content processing. The system discovers videos, transcribes them via AssemblyAI, generates business-focused summaries, and manages operational monitoring with strict cost controls.

**Key Architecture Pattern**: Event-driven broker architecture where Firestore serves as both data store and event broker, with Firebase Functions v2 for scheduling and automation.

## Common Development Commands

### Testing

```bash
# Run all tests with coverage (comprehensive test suite)
cd autopiloot
export PYTHONPATH=.
coverage run --source=. -m unittest discover tests -v
coverage report
coverage html  # Generate HTML report in htmlcov/index.html

# CRITICAL: Test Interference Prevention
# Running tests across multiple agent directories simultaneously causes coverage interference.
# Different agents use different import strategies (direct file imports, module mocking patterns)
# that conflict when run together, causing coverage.py to misreport line execution.
#
# ALWAYS use agent-specific test directories to prevent interference:
# - tests/drive_tools/ for drive_agent
# - tests/summarizer_tools/ for summarizer_agent
# - tests/orchestrator_tools/ for orchestrator_agent
# - tests/observability_tools/ for observability_agent
# - tests/linkedin_tools/ for linkedin_agent
# - tests/strategy_tools/ for strategy_agent
#
# NEVER use "discover tests -p 'test_*.py'" without a specific subdirectory
# as it will pick up ALL 296+ test files across agents and cause interference.

# Run agent-specific tests with coverage
# Replace [AGENT_NAME] with the agent to test (e.g., drive_agent, scraper_agent, etc.)
# Replace [TEST_DIR] with the test directory (e.g., drive_tools, scraper_tools, etc.)
export PYTHONPATH=.
coverage erase  # Always clear old coverage data first
coverage run --source=[AGENT_NAME] -m unittest discover tests/[TEST_DIR] -p "test_*.py"
coverage report --include="[AGENT_NAME]/*"
coverage html --include="[AGENT_NAME]/*" -d coverage/[AGENT_NAME]

# Example: Drive Agent (85% coverage achieved)
export PYTHONPATH=.
coverage erase
coverage run --source=drive_agent -m unittest discover tests/drive_tools -p "test_*.py"
coverage report --include="drive_agent/*"
coverage html --include="drive_agent/*" -d coverage/drive_agent

# Example: Scraper Agent
export PYTHONPATH=.
coverage erase
coverage run --source=scraper_agent -m unittest discover tests/scraper_tools -p "test_*.py"
coverage report --include="scraper_agent/*"
coverage html --include="scraper_agent/*" -d coverage/scraper_agent

# Example: Observability Agent
export PYTHONPATH=.
coverage erase
coverage run --source=observability_agent -m unittest discover tests/observability_tools -p "test_*.py"
coverage report --include="observability_agent/*"
coverage html --include="observability_agent/*" -d coverage/observability_agent

# Example: Transcriber Agent
# IMPORTANT: Transcriber tests are in root tests/ directory (legacy organization)
# Use specific test module names to avoid picking up other agents' tests
export PYTHONPATH=.
coverage erase
coverage run --source=transcriber_agent -m unittest \
  tests.test_get_video_audio_url \
  tests.test_poll_transcription_job \
  tests.test_save_transcript_record \
  tests.test_store_transcript_to_drive \
  tests.test_submit_assemblyai_job
coverage report --include="transcriber_agent/*"
coverage html --include="transcriber_agent/*" -d coverage/transcriber_agent

# Example: Summarizer Agent
export PYTHONPATH=.
coverage erase
coverage run --source=summarizer_agent -m unittest discover tests/summarizer_tools -p "test_*.py"
coverage report --include="summarizer_agent/*"
coverage html --include="summarizer_agent/*" -d coverage/summarizer_agent

# Example: LinkedIn Agent (95% coverage achieved)
export PYTHONPATH=.
coverage erase
coverage run --source=linkedin_agent -m unittest discover tests/linkedin_tools -p "test_*.py"
coverage report --include="linkedin_agent/*"
coverage html --include="linkedin_agent/*" -d coverage/linkedin_agent

# Example: Orchestrator Agent (99% coverage achieved)
export PYTHONPATH=.
coverage erase
coverage run --source=orchestrator_agent -m unittest discover tests/orchestrator_tools -p "test_*.py"
coverage report --include="orchestrator_agent/*"
coverage html --include="orchestrator_agent/*" -d coverage/orchestrator_agent

# Example: Strategy Agent
export PYTHONPATH=.
coverage erase
coverage run --source=strategy_agent -m unittest discover tests/strategy_tools -p "test_*.py"
coverage report --include="strategy_agent/*"
coverage html --include="strategy_agent/*" -d coverage/strategy_agent

# Run specific test modules
python -m unittest tests.test_config -v           # Configuration tests
python -m unittest tests.test_env_loader -v       # Environment validation tests
python -m unittest tests.test_audit_logger -v     # Audit logging tests (TASK-AUDIT-0041)
python -m unittest tests.test_observability_ops -v # Observability ops suite (TASK-OBS-0040)
python -m unittest tests.test_send_error_alert -v  # Error alerting tests (TASK-OBS-0041)
python -m unittest tests.test_llm_observability -v # LLM observability (TASK-LLM-0007)
python -m unittest tests.test_remove_sheet_row -v # Tool-specific tests
python -m unittest tests.test_get_video_audio_url -v # Audio extraction tests
python -m unittest tests.test_submit_assemblyai_job -v # AssemblyAI job submission tests
python -m unittest tests.test_poll_transcription_job -v # Transcript polling tests
python -m unittest tests.test_store_transcript_to_drive -v # Drive storage tests
python -m unittest tests.test_save_transcript_record -v # Firestore metadata tests

# Test individual tools (each has test block)
python scraper_agent/tools/RemoveSheetRow.py
python transcriber_agent/tools/get_video_audio_url.py
python transcriber_agent/tools/submit_assemblyai_job.py
python transcriber_agent/tools/poll_transcription_job.py
python transcriber_agent/tools/store_transcript_to_drive.py
python transcriber_agent/tools/save_transcript_record.py
python observability_agent/tools/monitor_quota_state.py
python observability_agent/tools/alert_engine.py
python observability_agent/tools/stuck_job_scanner.py

# Validate environment setup
python config/env_loader.py
```

### Agency Operations

```bash
# Run the agency (requires proper .env configuration)
python agency.py

# Deploy Firebase Functions (from autopiloot directory)
firebase deploy --only functions

# Test Firebase Functions locally
firebase emulators:start --only functions,firestore
```

### Development Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (REQUIRED before running)
cp .env.template .env
# Edit .env with actual API keys
```

## High-Level Architecture

### Agency Swarm v1.0.0 Framework

- **Inheritance Pattern**: All tools inherit from `agency_swarm.tools.BaseTool` with Pydantic Field validation
- **Return Convention**: All tool `run()` methods return JSON strings (not Dict objects)
- **Agent Structure**: Each agent is in `{agent_name}/` directory with `tools/` subdirectory
- **Communication Flow**: ScraperAgent (CEO) → TranscriberAgent → SummarizerAgent, with ObservabilityAgent monitoring all
- **Agent Count**: 4 production agents (31 total tools)
- **Complete Architecture**: All 30 planned tasks completed and archived

### Multi-Layer Configuration System

1. **Environment Variables** (`.env`): API keys, credentials, secrets
2. **settings.yaml**: Business rules, thresholds, operational parameters
3. **agency_manifesto.md**: Shared operational standards across all agents
4. **Agent instructions.md**: Agent-specific workflows and guidelines

### Firestore as Event Broker

- **Pattern**: All data mutations flow through Firestore exclusively
- **Collections**: `videos/`, `transcripts/`, `summaries/`, `jobs/transcription/`, `costs_daily/`, `audit_logs/`, `jobs_deadletter/`, `alert_throttling/`
- **Status Progression**: `discovered` → `transcription_queued` → `transcribed` → `summarized`
- **Idempotency**: Document IDs use YouTube video_id as natural key
- **Audit Trail**: All key actions logged to `audit_logs` collection (TASK-AUDIT-0041)

### Reliability & Error Handling Architecture

- **Dead Letter Queue**: Failed operations route to `jobs_deadletter` collection after 3 retries
- **Exponential Backoff**: 60s → 120s → 240s retry delays
- **Quota Management**: YouTube API (10k units/day), AssemblyAI ($5/day budget)
- **Checkpoint System**: `lastPublishedAt` persistence for incremental processing

### Firebase Functions Integration

- **Scheduled**: Daily scraping at 01:00 Europe/Amsterdam via Cloud Scheduler
- **Event-Driven**: Budget monitoring triggered by Firestore document writes
- **Deployment**: Manual via Firebase CLI with service account authentication (functions in services/firebase/)
- **Configuration**: Functions import agency classes directly, reuse environment config

## Critical Implementation Details

### Tool Development Rules

- **NEVER** include API keys as tool parameters - always use environment variables
- **ALWAYS** validate required environment variables in tool initialization
- **ALWAYS** include test block with `if __name__ == "__main__":` in every tool
- **ALWAYS** use JSON string returns from `run()` methods

### Agent Communication Patterns

```python
# Agency chart defines allowed communication flows
agency_chart = [
    scraper_agent,  # CEO can communicate with all
    [scraper_agent, transcriber_agent],  # Workflow pipeline
    [transcriber_agent, summarizer_agent],
    [observability_agent, scraper_agent],  # Monitoring flows
    [observability_agent, transcriber_agent, summarizer_agent],  # Observability monitoring
]
```

### Business Rule Enforcement

- **Duration Limit**: 70 minutes (4200 seconds) maximum video duration
- **Daily Limits**: 10 videos per channel, $5 transcription budget
- **Archive-First**: Google Sheets rows archived before deletion for audit trail
- **Quota Handling**: Graceful degradation when YouTube/AssemblyAI quotas exhausted

### Error Response Format

All tools return consistent JSON error structures:

```python
{
    "error": "error_type",
    "message": "Human-readable description",
    "details": {...}  # Optional additional context
}
```

## Test Coverage Achievements

### Drive Agent Module (59% Coverage)
The drive_agent module has comprehensive test coverage across all 10 files:

- **Perfect Coverage (100%)**:
  - `drive_agent.py` - Agent initialization

- **Excellent Coverage (80%+)**:
  - `list_tracked_targets_from_config.py` - 84% coverage
  - `list_drive_changes.py` - 80% coverage

- **Good Coverage (60%+)**:
  - `fetch_file_content.py` - 75% coverage
  - `extract_text_from_document.py` - 67% coverage

- **Moderate Coverage (25%+)**:
  - `save_drive_ingestion_record.py` - 43% coverage
  - `resolve_folder_tree.py` - 41% coverage
  - `upsert_drive_docs_to_zep.py` - 25% coverage

- **Low Coverage (0%)**:
  - `drive_agent/__init__.py` - 0% coverage
  - `drive_agent/tools/__init__.py` - 0% coverage

**Test Suite**: 37+ working tests across 8 coverage test files in `tests/drive_tools/`

## ADR and Documentation Maintenance

### Keep Updated

- **ADR.mdc**: Add new ADR entries for significant architectural decisions
- **folder-structure.mdc**: Update when directory structure changes
- Both files in `.cursor/rules/` are source of truth for architecture

### ADR Protocol

1. Read entire ADR.mdc file
2. Calculate next ID (max + 1, zero-padded to 4 digits)
3. Add entry at END of file with proper anchor
4. Update index table (sorted by ID descending)
5. Mark superseded ADRs if applicable

## Testing Strategy & Coverage Standards

### Coverage Requirements

**Minimum Standards:**
- Overall project coverage: 85%
- Individual file coverage: 80%
- Target per file: 90%
- Critical business logic files: 95%

**Coverage Commands:**
```bash
# Generate coverage reports with missing line analysis
export PYTHONPATH=.
coverage run --source=[AGENT_NAME] -m unittest discover tests/[TEST_DIR] -p "test_*.py" -v
coverage report --include="[AGENT_NAME]/*" --show-missing
coverage html --include="[AGENT_NAME]/*" -d coverage/[AGENT_NAME]

# Examples for each agent
coverage run --source=drive_agent -m unittest discover tests/drive_tools -p "test_*.py"
coverage run --source=observability_agent -m unittest discover tests/observability_tools -p "test_*.py"
coverage run --source=transcriber_agent -m unittest discover tests/transcriber_tools -p "test_*.py"
```

**CRITICAL: Always Generate HTML Reports**
After running coverage tests, you MUST ALWAYS generate the HTML coverage report:
```bash
# REQUIRED: Generate HTML report to update coverage/[AGENT_NAME]/index.html
coverage html --include="[AGENT_NAME]/*" -d coverage/[AGENT_NAME]
```
The HTML report provides:
- Visual line-by-line coverage display
- Clickable file navigation
- Detailed coverage statistics
- Missing line identification
- Updated timestamps for tracking progress

### Test Organization Standards

**File Naming Convention:**
- `test_[module_name]_minimal.py` - Basic functionality tests
- `test_[module_name]_coverage_boost.py` - Target missing coverage lines
- `test_[module_name]_integration.py` - End-to-end workflow tests
- `test_[module_name]_error_handling.py` - Exception path testing

**Test Method Naming:**
```python
def test_[functionality]_[scenario]_lines_[X_Y](self):
    """Test [description] (lines X-Y)."""
    # Example: test_pdf_page_extraction_error_lines_142_143
```

### Missing Coverage Analysis & Targeting

**Required Before Implementation:**
1. Line-by-line analysis of missing coverage using `coverage report --show-missing`
2. Categorization of gaps: High/Medium/Low priority based on:
   - Error handling paths (High priority)
   - External library integration failures (High priority)
   - Edge cases and boundary conditions (Medium priority)
   - Alternative workflow paths (Medium priority)
   - Simple conditional branches (Low priority)
3. Expected coverage improvement estimates

**Must Target Coverage Gaps:**
- HTTP error scenarios (403, 404, 500 status codes)
- External API failures and timeouts
- File encoding and decoding errors
- Invalid input data and malformed content
- Permission and access denied scenarios
- Fallback mechanisms and alternative code paths

### Comprehensive Mocking Standards

**CRITICAL: Proper Coverage Measurement Strategy**

**ISSUE IDENTIFIED**: Module-level mocking prevents actual source code execution, resulting in 0% coverage.

**ROOT CAUSE**: Using `sys.modules['agency_swarm'] = MagicMock()` prevents importing and executing real source code.

**SOLUTION**: Use direct file imports with `importlib.util.spec_from_file_location()` while mocking only dependencies.

To ensure coverage tools properly measure source code execution, follow these guidelines:

1. **Import Real Source Code**: Always import actual source files, not mocked modules
2. **Use Direct File Imports**: When dependencies like `agency_swarm` are missing, use `importlib.util.spec_from_file_location()` to import specific tool files directly
3. **Mock Dependencies, Not Source**: Mock external dependencies (APIs, libraries) but import and execute the actual tool source code
4. **Verify Coverage Data**: If coverage reports show 0%, it means tests aren't executing real source code - fix the import strategy
5. **ALWAYS Generate HTML Reports**: After coverage measurement, run `coverage html` to update the index.html file

**Example of Correct Import Pattern for Coverage:**
```python
# WRONG: Module-level mocking that prevents source execution
sys.modules['agency_swarm'] = MagicMock()  # Prevents real imports

# RIGHT: Direct file import with dependency mocking
import importlib.util
tool_path = os.path.join(os.path.dirname(__file__), '..', '..', 'agent_name', 'tools', 'tool_name.py')
spec = importlib.util.spec_from_file_location("tool_name", tool_path)
module = importlib.util.module_from_spec(spec)

# Mock only the dependencies in sys.modules BEFORE executing
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['external_api'] = mock_external_api

# Execute the real source code
spec.loader.exec_module(module)
ToolClass = module.ToolClassName
```

**External Dependencies:**
```python
# Module-level mocking for import issues
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'googleapiclient': MagicMock(),
    'googleapiclient.discovery': MagicMock(),
    'googleapiclient.errors': MagicMock(),
    'PyPDF2': MagicMock(),
    'docx': MagicMock()
}):
    pass
```

**HTTP Error Mocking:**
```python
# Create realistic HTTP error scenarios
class MockHttpError(Exception):
    def __init__(self, resp, content):
        self.resp = resp
        self.content = content
        super().__init__()

http_error_403 = MockHttpError(
    Mock(status=403, reason="Forbidden"),
    b'{"error": {"code": 403, "message": "Permission denied"}}'
)
```

### Agency Swarm Testing Requirements

**Tool Testing Standards:**
- Every tool must have standalone test with `if __name__ == "__main__":` block
- Test `run()` method return format (JSON strings, not Dict objects)
- Mock BaseTool inheritance: `sys.modules['agency_swarm.tools'].BaseTool = MagicMock()`
- Test Pydantic Field validation and parameter handling
- Validate error response structure consistency

**Agent Testing Standards:**
- Test agent initialization and configuration loading
- Test tool imports and availability in agent context
- Test communication patterns between agents
- Mock external service dependencies comprehensively

### Error Path & Edge Case Coverage

**Mandatory Error Scenarios:**
- Network failures and API timeouts
- Invalid authentication and authorization
- Malformed data and encoding issues
- File system errors and permission denials
- External service unavailability
- Configuration loading failures

**Edge Case Requirements:**
- Empty inputs and responses
- Maximum size limits and truncation
- Invalid file types and formats
- Concurrent access scenarios
- Resource exhaustion conditions

### Test Quality & Documentation Standards

**Test Documentation:**
```python
def test_pdf_extraction_error_handling_lines_142_143(self):
    """
    Test PDF page extraction error handling (lines 142-143).

    Covers scenario where PyPDF2 page.extract_text() raises exception.
    Should gracefully handle error and include error message in output.
    """
```

**Assertion Standards:**
- Use specific assertions: `assertIn`, `assertEqual`, not just `assertTrue`
- Validate both success and error response structures
- Check error messages contain meaningful information
- Verify proper JSON structure in tool responses

### Configuration & Environment Testing

**Core Configuration Tests:**
- `test_config.py`: YAML loading, validation, nested key access
- `test_env_loader.py`: Environment variable validation, API key getters
- Run `python config/env_loader.py` to validate current environment

**Agent-Specific Test Suites:**
- **Observability Agent**: Error alerting, budget monitoring, digest generation
- **Transcriber Agent**: AssemblyAI integration, exponential backoff, Drive storage
- **Summarizer Agent**: LLM integration, content processing, Zep storage
- **Drive Agent**: File processing, text extraction, change monitoring
- **Orchestrator Agent**: Workflow coordination, policy enforcement

### Performance & Execution Standards

**Test Performance Requirements:**
- Individual tests complete in <5 seconds
- Full agent test suite completes in <2 minutes
- Use parallel test execution where possible
- Mock file operations to avoid disk I/O
- Mock network calls to prevent external dependencies

**Resource Management:**
- Clean up mocks in tearDown() methods
- Use in-memory data structures for testing
- Avoid creating temporary files on disk
- Reset module state between test classes

## Firebase Deployment

### Functions Structure

```
services/firebase/functions/
├── main.py          # Entry points
├── scheduler.py     # Scheduled and event-driven functions
├── core.py          # Utilities
└── requirements.txt # Firebase-specific dependencies
```

### Deployment Commands

```bash
# Deploy functions only
firebase deploy --only functions

# Deploy specific function
firebase deploy --only functions:daily_scraper

# Test locally with emulator
firebase emulators:start
```

## Common Troubleshooting

### Missing Environment Variables

- Check `.env` file exists and contains all variables from `.env.template`
- Run `python config/env_loader.py` to identify missing variables
- Ensure Google service account file exists at path specified

### Tool Import Errors

- Tool class name must match filename exactly
- Tools must be in `{agent_name}/tools/` directory
- All tools must inherit from `agency_swarm.tools.BaseTool`

### Firestore Connection Issues

- Verify `GCP_PROJECT_ID` environment variable is set
- Check service account has Firestore permissions
- Ensure `GOOGLE_APPLICATION_CREDENTIALS` points to valid JSON file

### Quota Exhaustion

- YouTube: Check `QuotaManager` status, wait for daily reset
- AssemblyAI: Monitor `costs_daily` collection for budget status
- Implement checkpoint-based resume from `lastPublishedAt`

### Observability Monitoring

- Use `monitor_quota_state.py` for real-time YouTube/AssemblyAI quota tracking
- Check `monitor_dlq_trends.py` for dead letter queue anomaly detection
- Run `stuck_job_scanner.py` to identify stale jobs across agent collections
- Generate operational reports with `report_daily_summary.py` (Slack-formatted)
- Track LLM usage and costs with `llm_observability_metrics.py`
- Manage centralized alerting via `alert_engine.py` with throttling and deduplication

### Task and Project Status

- All 80 planned tasks completed and archived in `planning/archive/`
- Production-ready status achieved with comprehensive test coverage (160+ tests)
- Complete ADR documentation in `.cursor/rules/ADR.mdc` (23+ architectural decisions)
- Folder structure documented in `.cursor/rules/folder-structure.mdc`

## Security Review Standards

### Required Security Checks
Every code change MUST pass these security gates:

#### 1. Automated Scanning
- SAST scan with zero CRITICAL findings
- Dependency vulnerability scan
- Secrets detection scan
- Configuration security check

#### 2. Manual Review Requirements
- Authentication/authorization logic reviewed by security-trained developer
- Cryptographic implementations reviewed by crypto-knowledgeable team member
- Database query construction verified for injection protection
- Input validation completeness confirmed

#### 3. Security Review Checklist
- [ ] No hardcoded secrets, API keys, or credentials
- [ ] All database queries use parameterization
- [ ] User input validation at application boundaries
- [ ] Authentication required for all protected endpoints
- [ ] Authorization checks at data access level
- [ ] HTTPS enforced for sensitive operations
- [ ] Error messages don't leak sensitive information
- [ ] Dependencies are up-to-date and vulnerability-free

### Severity Guidelines
- **CRITICAL**: Immediate RCE, data breach, or auth bypass - BLOCK merge
- **HIGH**: Significant security risk - Fix before merge
- **MEDIUM**: Security weakness - Fix within 1 week
- **LOW**: Security improvement - Fix in next sprint

### False Positive Handling
If security tool flags false positive:
1. Document why it's false positive in PR comments
2. Add suppression comment with justification
3. Update tool configuration if pattern recurring

### Emergency Override Process
For production hotfixes only:
1. Security team approval required
2. Temporary merge allowed
3. Security review within 24 hours
4. Follow-up fix within 72 hours
