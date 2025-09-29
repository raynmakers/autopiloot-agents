# Test Coverage Commands

Simple commands to run comprehensive test coverage for agents and tools.

## Prerequisites

- Virtual environment at `.venv/` (or `venv/`)
- Run from repo root or let commands handle directory changes
- Install packages: `pip install coverage pytest unittest-mock`

## Quick Commands

### Agent Coverage

```bash
/test @<agent>/
```

### Focused Tool Analysis

```bash
/test @<agent>/tools/<tool>.py
```

### Autonomous Coverage Loop (no manual approvals)

```bash
/test @<agent>/ --auto
```

When run with `--auto`, Claude repeatedly:

1. Runs agent coverage and parses the report
2. Identifies the lowest-coverage tool (below 80% or your configured threshold)
3. Executes `/test @<agent>/tools/<tool>.py` for that tool
4. Re-runs the agent coverage to verify improvement
5. Stops only when all tools meet the threshold or the iteration limit is reached

## What These Do

- **Agent Coverage**: Runs all tests for an agent, generates HTML report at `coverage/{agent}/index.html`
- **Tool Coverage**: Runs full agent coverage with focus on specific tool analysis
- **Auto-Improvement**: If coverage < 80%, runs deep analysis to find suggestions for test fixes or code improvements and executes them
- **HTML Reports**: Interactive coverage reports for visual analysis

## Coverage Expectations

- **Perfect (100%)**: Tool fully covered and production ready
- **Excellent (90%+)**: High confidence, minimal risk
- **Good (80%+)**: Meets minimum threshold for production
- **Needs Improvement (<80%)**: Add tests before shipping
- **Overall Project**: Maintain 80%+ minimum across all agents
- **Critical Modules**: Initialization/config files must stay at 100%

## Test File Organization

```
tests/{agent}_tools/
└── test_{tool}.py                 # One comprehensive test file per tool
```

**Simple rule:**

- One test file per tool that achieves 100% coverage
- No confusing naming schemes or multiple files
- Just `test_{tool}.py` - clear and simple

## Comprehensive Mocking Strategy

**Always mock external dependencies** to prevent real API calls and ensure reliable tests:

### Required Mocks (All Tests)

```python
import sys
from unittest.mock import patch, MagicMock

# Mock ALL external dependencies before any imports
mock_modules = {
    # Agency Swarm Framework
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),

    # Google Cloud Services
    'google': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
    'googleapiclient': MagicMock(),
    'googleapiclient.discovery': MagicMock(),
    'googleapiclient.errors': MagicMock(),

    # External APIs
    'slack_sdk': MagicMock(),
    'slack_sdk.web': MagicMock(),
    'requests': MagicMock(),
    'assemblyai': MagicMock(),
    'openai': MagicMock(),

    # Utilities
    'pytz': MagicMock(),
    'tiktoken': MagicMock(),
    'zep_python': MagicMock(),

    # Internal modules
    'config': MagicMock(),
    'config.env_loader': MagicMock(),
    'config.loader': MagicMock(),
    'core': MagicMock(),
    'core.audit_logger': MagicMock(),
}

with patch.dict('sys.modules', mock_modules):
    # Mock BaseTool and Field properly
    class MockBaseTool:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def mock_field(*args, **kwargs):
        return kwargs.get('default', None)

    sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
    sys.modules['pydantic'].Field = mock_field

    # Now import the tool safely
    from {agent}_agent.tools.{tool} import {ToolClass}
```

### Mocking Strategy by Tool Type

**Always Mock (External APIs):**

- `googleapiclient` - YouTube API, Drive API, Sheets API (quota limits, network calls)
- `slack_sdk` - Slack API (rate limits, requires tokens)
- `assemblyai` - Transcription API (costs money, network calls)
- `openai` - GPT API (costs money, rate limits)
- `requests` - HTTP calls (network dependency)

**Mock for Reliability (Internal but External Dependencies):**

- `google.cloud.firestore` - Database calls (requires credentials, network)
- `pytz` - Timezone handling (can be flaky in CI)
- `tiktoken` - Token counting (external library, can be slow)

**Optional Mocking (Framework Dependencies):**

- `agency_swarm` - Framework (can run without, but mocking ensures consistency)
- `pydantic` - Validation (can run without, but mocking prevents import issues)
- `zep_python` - GraphRAG (optional dependency, mock for safety)

**Can Run Without Mocking:**

- Pure Python logic tools (math, string processing, data transformation)
- Tools that only use standard library
- Configuration loading tools (if no external calls)

### When to Mock vs Not Mock

**Mock When:**

- Tool makes external API calls
- Tool requires credentials/tokens
- Tool has network dependencies
- Tool costs money to run
- Tool has rate limits

**Don't Mock When:**

- Pure logic/calculation tools
- File system operations (use temp files)
- Standard library only tools
- Configuration parsing tools

## Pre-Work Checklist (CRITICAL)

**Before making ANY changes to tests or code:**

1. **Run current coverage** to identify which tools already have 100%
2. **Document 100% tools** - list them and mark as "DO NOT TOUCH"
3. **Focus only on tools < 100%** - never modify files that already work
4. **Backup existing tests** - save working test files before changes
5. **Verify current state** - ensure you understand what's already working

**Example workflow:**

```bash
# 1. Check current coverage
/test @drive_agent/
# → Identifies: save_drive_ingestion_record.py (100%), extract_text_from_document.py (73%)

# 2. Document what NOT to touch
# ✅ DO NOT TOUCH: save_drive_ingestion_record.py (already 100%)
# 🎯 FOCUS ON: extract_text_from_document.py (needs improvement)

# 3. Only work on the 73% tool, leave 100% tool alone
```

## Preventing Coverage Measurement Failures

Infrastructure issues (bad imports, missing mocks, broken HTTP fakes) can make coverage look low even when business logic is tested. Apply these generic safeguards before writing new tests:

1. **Reuse proven templates** – copy patterns from a known good tool test (e.g., `deduplicate_entities`) so imports and mocks stay consistent.
2. **Import real source code** – use `importlib.util.spec_from_file_location` inside tests when direct imports fail, ensuring coverage tracks actual lines executed.
3. **Patch every external module before import** – mock SDKs/clients in `sys.modules` (see comprehensive mocking section) so the tool file imports cleanly.
4. **Standardize HTTP mocks** – build mocked responses with `status_code`, `json()`, `text`, and error raising helpers to exercise success/error paths without network calls.
5. **Validate test execution** – temporarily log or assert inside the tool to confirm the test reaches the real `run()` method (remove after verification).
6. **Run smoke coverage** – execute `/test @<agent>/ --analyze` after infrastructure fixes; if coverage stays near zero, re-check steps 2–4 before adding new tests.

Following this checklist keeps the testing infrastructure healthy so coverage numbers stay trustworthy.

## Diagnosing Low Coverage (Generic Workflow)

Use the same sequence for any agent or tool:

1. **Run a dry analysis**
   ```bash
   /test @<agent>/ --analyze
   ```
   - Lists current coverage percentage per tool
   - Flags anything below the 80% threshold
2. **Target the lowest tool first**
   ```bash
   /test @<agent>/tools/<tool>.py
   ```
   - Generates focused suggestions for missing scenarios
   - Produces an updated coverage report for the parent agent
3. **Iterate** until all tools meet or exceed the target
4. **Re-run the full agent** to confirm
   ```bash
   /test @<agent>/ --comprehensive
   ```

### Common Root Causes (apply to any tool)

- External API dependencies without mocks (HTTP requests, SDK calls)
- Untested error handling (HTTP status codes, retries, timeouts)
- Over-mocking that prevents real source code execution
- Missing test files or incomplete success-path coverage
- Data processing edge cases (empty payloads, pagination, rate limits)

### Generic Improvement Checklist

- Cover **success** paths with realistic sample payloads
- Cover **error** paths (400, 401, 403, 404, 429, 500+)
- Simulate **network failures** (timeouts, connection errors)
- Exercise **retry logic** and **rate limiting** branches
- Validate **data transformations** and edge inputs
- Assert that the tool returns the documented JSON structure

## Tool-Level Coverage Analysis

Use targeted coverage commands whenever a single tool needs deeper inspection:

```bash
coverage run --source=<agent>/tools/<tool>.py \
  -m unittest tests.<agent>_tools.test_<tool> -v
coverage report --include="<agent>/tools/<tool>.py" --show-missing
coverage html --include="<agent>/tools/<tool>.py" -d coverage/<agent>
```

## Coverage Report Validation

Always confirm the reports are meaningful:

1. HTML report exists: `coverage/<agent>/index.html`
2. No "module-not-imported" or "no data collected" warnings
3. Coverage percentage aligns with expectations
4. Missing-line listings identify remaining gaps

## Coverage Testing Best Practices

- Reuse known-good test files as templates for new tools
- Generate HTML reports (`coverage html`) for visual inspection
- Target error handling and edge cases for missing lines
- Use `importlib.util.spec_from_file_location` when standard imports fail
- Mock external dependencies, not the tool modules themselves

## Coverage Troubleshooting

- **0% coverage reported**: Revisit import strategy; avoid global module mocking that skips real execution
- **"No data collected" warnings**: Ensure `--source` paths and tests are correct
- **Import errors**: Confirm `patch.dict('sys.modules')` patches all dependencies before import
- **Unexpected percentages**: Clear old `.coverage` files (`coverage erase`) and rerun

## Coverage Analysis

The commands automatically analyze results and take action:

- **< 80%**: Runs deep analysis to identify issues:
  - **Test Problems**: Missing test cases, incorrect mocks, wrong assertions
  - **Code Problems**: Dead code, unreachable branches, missing error handling
  - **Auto-Fix**: Creates/updates test files, refactors code, adds missing error paths
  - **Re-runs**: Automatically re-tests after fixes to verify improvements
- **≥ 80%**: Primary threshold satisfied
- **≥ 90%**: Considered production-ready
- **100%**: Maintain and protect this status

## Coverage Success Criteria

- ✅ **Perfect (100%)** – fully covered, production ready
- ✅ **Excellent (90%+)** – small gaps remain, acceptable risk
- ✅ **Good (80%+)** – meets minimum bar, monitor uncovered lines
- ⚠️ **Needs Improvement (<80%)** – prioritize additional testing

## Automatic Low-Coverage Detection

When you ask Claude to "pick up low-coverage tests" or "fix low-coverage files," Claude will:

1. **Scan the coverage HTML report** at `coverage/{agent}/index.html`
2. **Identify all tools below 80% coverage**
3. **Automatically create comprehensive test suites** targeting 100% coverage
4. **Iterate through each low-coverage tool** until all reach 80%+ or 100%
5. **Generate final HTML report** showing overall improvement

### Example Workflow

```bash
# User: "I see a few low coverage tests, can these be picked up?"

# Claude automatically:
# 1. Reads coverage/orchestrator_agent/index.html
# 2. Finds: dispatch_scraper.py (32%), query_dlq.py (25%), emit_run_events.py (23%)
# 3. Creates test_dispatch_scraper_100_coverage.py → 100% ✅
# 4. Creates test_query_dlq_100_coverage.py → 100% ✅
# 5. Creates test_emit_run_events_100_coverage.py → 100% ✅
# 6. Runs all tests together
# 7. Overall coverage: 47% → 99% 🎉
```

### Triggering Automatic Improvement

Simply ask in natural language:
- "Can you pick up the low coverage tests?"
- "Fix the low-coverage files"
- "Improve coverage for tools below 80%"
- "Continue with remaining low-coverage tools"

Claude will:
- ✅ Read the HTML coverage report
- ✅ Identify tools < 80%
- ✅ Create comprehensive test files (targeting 100%)
- ✅ Run tests and verify coverage
- ✅ Iterate until all tools meet threshold
- ✅ Provide final summary with metrics

### What Claude Tests

Each comprehensive test file covers:
- ✅ Success paths with realistic data
- ✅ All validation checks and error messages
- ✅ Edge cases (empty inputs, invalid types, missing fields)
- ✅ Exception handling paths
- ✅ External API mocking (Firestore, HTTP, etc.)
- ✅ Business logic calculations
- ✅ Configuration overrides
- ✅ Integration points

### Coverage Improvement Standards

- **Target**: 100% coverage per tool
- **Minimum acceptable**: 80% coverage
- **Test count**: Typically 15-30 tests per tool
- **Naming**: `test_{tool}_100_coverage.py`
- **Pattern**: One comprehensive test file per tool

## Examples

### Agent Coverage (Full Agent)

```bash
/test @linkedin_agent/
# → Runs ALL tests for linkedin_agent
# → Generates coverage/linkedin_agent/index.html
# → Shows overall agent coverage percentage
```

### Tool Coverage (Specific Tool Focus)

```bash
/test @autopiloot/drive_agent/tools/save_drive_ingestion_record.py
# → Runs ALL drive_agent tests (full agent coverage)
# → Generates coverage/drive_agent/index.html
# → Provides detailed analysis of the specific tool mentioned
# → Shows missing lines for that specific tool
```

**What's the difference?**

- **Agent Coverage**: Focus on the entire agent's coverage
- **Tool Coverage**: Still runs full agent, but gives extra detail about one specific tool

## Verification Checklist

- [ ] Clear coverage data with `coverage erase` before starting
- [ ] Run all tests for the agent (one test file per tool)
- [ ] Check HTML report for 0 missing lines in `coverage/{agent}/index.html`
- [ ] Mock external dependencies (APIs, databases, external services)
- [ ] Test all paths: error handling, edge cases, alternative workflows
- [ ] Verify each tool achieves 100% coverage

## Maintenance

- **CRITICAL**: If a tool already has 100% coverage, DO NOT touch its test file
- When a tool reaches 100% coverage, maintain through comprehensive test files
- Don't modify tests unless requirements change
- Create documentation for achieved coverage milestones
- Ensure test commands run all comprehensive tests together for accurate results
