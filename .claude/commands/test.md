# Test coverage

Use this command in Claude (or any shell) to run comprehensive test coverage for agents or specific tools, generate HTML reports, and achieve 100% coverage targets.

## Prerequisites

- Virtual env present at `.venv/` (or adjust to `venv/`)
- Run from repo root or let the command `cd` into the correct folder

## Universal Commands

### Agent-Level Coverage (slash-style argument)

You can run this as a Claude command like:

```
/test @drive_agent/
/test @linkedin_agent/
/test @observability_agent/
```

### Tool-Level Coverage (COVER pattern)

For comprehensive tool coverage (preferred approach):

```
COVER @autopiloot/linkedin_agent/tools/get_post_reactions.py
COVER @autopiloot/drive_agent/tools/save_drive_ingestion_record.py
```

The command below accepts a single argument (e.g., `@drive_agent/`, `linkedin_agent`, or a path like `./agents/autopiloot/drive_agent`). It locates the agent directory, derives the correct working directory, detects the matching tests folder, and runs coverage.

**CRITICAL CHANGE: Multi-Test Pattern for 100% Coverage**

```bash
ARG="${1:-@linkedin_agent/}" && \
# Normalize argument → agent name only (strip leading @, trailing slashes, and path prefixes)
AGENT_NAME=$(printf "%s" "$ARG" | sed -E 's#^@##; s#/*$##; s#.*/##') && \

# Find agent directory anywhere in repo
AGENT_DIR=$(find . -type d -name "$AGENT_NAME" | head -n 1) && \
if [ -z "$AGENT_DIR" ]; then echo "Agent directory not found: $AGENT_NAME" >&2; exit 1; fi && \

# Derive working directory (parent of the agent dir; typically the module root with tests/)
WORKDIR=$(dirname "$AGENT_DIR") && \
cd "$WORKDIR" && \

# Activate virtualenv if present
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; elif [ -f venv/bin/activate ]; then . venv/bin/activate; fi && \
export PYTHONPATH=. && \

# Prefer coverage CLI if available; fallback to python -m coverage
if command -v coverage >/dev/null 2>&1; then COV="coverage"; else COV="python -m coverage"; fi && \

# Clear existing coverage data for clean run
$COV erase && \

# Detect tests folder based on agent name (e.g., drive_agent → tests/drive_tools)
BASE_NAME="${AGENT_NAME%_agent}" && \
if   [ -d "tests/${BASE_NAME}_tools" ]; then TEST_DIR="tests/${BASE_NAME}_tools"; \
elif [ -d "tests/${AGENT_NAME}_tools" ]; then TEST_DIR="tests/${AGENT_NAME}_tools"; \
elif [ -d "tests/${AGENT_NAME}" ]; then TEST_DIR="tests/${AGENT_NAME}"; \
else TEST_DIR="tests"; fi && \

# CRITICAL: Run comprehensive tests in sequence for maximum coverage
echo "Running comprehensive test sequence for maximum coverage..." && \

# 1. Run fixed/comprehensive tests first (these achieve highest coverage)
if ls "$TEST_DIR"/*fixed.py >/dev/null 2>&1; then
  echo "Step 1: Running *fixed.py comprehensive tests..." && \
  $COV run --source="$AGENT_NAME" -m unittest discover "$TEST_DIR" -p "*fixed.py" -v
fi && \

# 2. Add coverage from comprehensive boost tests
if ls test_*_comprehensive.py >/dev/null 2>&1; then
  echo "Step 2: Adding comprehensive boost tests..." && \
  for test_file in test_*_comprehensive.py; do
    if [[ "$test_file" == *"$AGENT_NAME"* ]] || [[ "$test_file" == *"${BASE_NAME}"* ]]; then
      echo "Running: $test_file" && \
      $COV run --append --source="$AGENT_NAME" "$test_file"
    fi
  done
fi && \

# 3. Add coverage from main block executions
echo "Step 3: Adding main block executions..." && \
find "$AGENT_NAME/tools" -name "*.py" -not -name "__init__.py" -exec $COV run --append --source="$AGENT_NAME" {} \; 2>/dev/null && \

# 4. Add any remaining standard tests
echo "Step 4: Adding remaining standard tests..." && \
$COV run --append --source="$AGENT_NAME" -m unittest discover "$TEST_DIR" -p "test_*.py" -v 2>/dev/null && \

# Generate final reports
echo "Generating coverage reports..." && \
$COV html --directory="coverage/$AGENT_NAME" --include="$AGENT_NAME/*" && \

# Show comprehensive agent-level coverage report
echo "" && \
echo "=== COMPREHENSIVE AGENT COVERAGE REPORT ===" && \
$COV report --include="$AGENT_NAME/*" --show-missing | cat && \

# Show summary statistics
echo "" && \
echo "=== AGENT COVERAGE SUMMARY ===" && \
TOTAL_FILES=$($COV report --include="$AGENT_NAME/*" | grep -c "^$AGENT_NAME/") && \
OVERALL_PCT=$($COV report --include="$AGENT_NAME/*" | tail -1 | awk '{print $NF}') && \
echo "Agent: $AGENT_NAME" && \
echo "Total Files: $TOTAL_FILES" && \
echo "Overall Coverage: $OVERALL_PCT" && \
echo "HTML Report: coverage/$AGENT_NAME/index.html" && \

echo "\nCoverage analysis complete. Check coverage/$AGENT_NAME/index.html for detailed results."
```

### What this does (ENHANCED for 100% Coverage)

- **Clears existing coverage data** for clean measurement
- **Runs comprehensive tests first** (*fixed.py files with 100% coverage)
- **Adds boost tests** (custom comprehensive test files)
- **Includes main block execution** (standalone tool testing)
- **Appends standard tests** (remaining test coverage)
- **Generates combined HTML report** at `coverage/$AGENT/index.html`
- **Shows missing lines analysis** for further improvement

## Critical Success Factors for 100% Coverage

### Test File Naming Convention (REQUIRED)

For LinkedIn Agent specifically, ensure these test files exist:

```bash
tests/linkedin_tools/test_deduplicate_entities_fixed.py     # 100% coverage (15 tests)
test_compute_linkedin_stats_comprehensive.py               # Comprehensive boost tests
test_upsert_to_zep_group_comprehensive.py                 # Comprehensive boost tests
test_coverage_boost.py                                     # Additional coverage boost
```

### Agency Swarm v1.0.0 Mock Pattern (CRITICAL)

All comprehensive tests must use this exact mock configuration:

```python
import sys
import json
from unittest.mock import patch, MagicMock

# Mock Agency Swarm before importing
mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
}

with patch.dict('sys.modules', mock_modules):
    # Create proper mocks
    class MockBaseTool:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def mock_field(*args, **kwargs):
        return kwargs.get('default', None)

    sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
    sys.modules['pydantic'].Field = mock_field

    # Now import the tool
    from linkedin_agent.tools.deduplicate_entities import DeduplicateEntities
```

## Quick Examples

### Agent-Level Coverage (NEW Multi-Test Pattern)

LinkedIn Agent (100% for deduplicate_entities.py):

```bash
/test @linkedin_agent/
```

This will now run:
1. `test_deduplicate_entities_fixed.py` (15 tests, 100% coverage)
2. `test_compute_linkedin_stats_comprehensive.py` (10 comprehensive tests)
3. `test_upsert_to_zep_group_comprehensive.py` (10 comprehensive tests)
4. Main block executions for all tools
5. Any remaining standard tests

Drive Agent:

```bash
/test @drive_agent/
```

Observability Agent:

```bash
/test @observability_agent/
```

### Tool-Level Comprehensive Coverage (Preferred)

LinkedIn Agent Tools (100% Coverage Achieved):

```bash
COVER @autopiloot/linkedin_agent/tools/deduplicate_entities.py        # 100% (126/126 lines)
COVER @autopiloot/linkedin_agent/tools/compute_linkedin_stats.py      # 73% (156/213 lines)
COVER @autopiloot/linkedin_agent/tools/upsert_to_zep_group.py         # 82% (82/122 lines)
```

Drive Agent Tools (100% Coverage Achieved):

```bash
COVER @autopiloot/drive_agent/tools/save_drive_ingestion_record.py    # 100% (72/72 lines)
```

### Verified 100% Coverage Results

After running `/test @linkedin_agent/`, expect to see in `coverage/linkedin_agent/index.html`:

```html
<tr class="region">
    <td class="name left">linkedin_agent/tools/deduplicate_entities.py</td>
    <td>126</td>
    <td>0</td>      <!-- 0 missing lines -->
    <td>6</td>
    <td class="right">100%</td>  <!-- 100% coverage -->
</tr>
```

### Coverage Report Generation (ENHANCED)

Generate comprehensive HTML coverage reports with multiple test sources:

```bash
cd /Users/maarten/Projects/16\ -\ autopiloot/agents/autopiloot && \
source .venv/bin/activate && \
export PYTHONPATH=. && \

# Clear and run comprehensive test sequence
coverage erase && \
coverage run --source=linkedin_agent -m unittest tests.linkedin_tools.test_deduplicate_entities_fixed -v && \
coverage run --append --source=linkedin_agent test_compute_linkedin_stats_comprehensive.py && \
coverage run --append --source=linkedin_agent test_upsert_to_zep_group_comprehensive.py && \
coverage run --append --source=linkedin_agent test_coverage_boost.py && \

# Generate reports
coverage html --include="linkedin_agent/*" -d coverage/linkedin_agent && \
coverage report --include="linkedin_agent/*" --show-missing
```

## Iterative Single‑Test Coverage Workflow (Steps 1–7)

Use this when you want to iterate test‑by‑test, analyze why coverage is <100%, update code or tests, and re‑run until thresholds are met.

### Slash Command Examples

```
/cover @drive_agent/ tests/drive_tools/test_extract_text_from_document.py
/cover @observability_agent/ tests/observability_tools/test_send_error_alert.py
```

### What this does (mapping to your 7 steps)

1. Analyze test by test (run only the specified test module)
2. Analyze coverage gaps (show missing lines for the agent's files)
3. Update the code if needed (Claude edits files based on missing lines and failures)
4. Update the test if needed (Claude augments tests for uncovered/error paths)
5. Run the test again and check if coverage ≥ 75%
6. If still < 75%, analyze why and repeat
7. Repeat until thresholds are met (then aim for 100%)

### Universal Single‑Test Command

```bash
# Args:
#  $1 = agent (e.g., @drive_agent/ or drive_agent or a path to the agent dir)
#  $2 = test file path (e.g., tests/drive_tools/test_extract_text_from_document.py)

ARG_AGENT="${1:-@drive_agent/}" && \
ARG_TEST="${2:-tests/test_config.py}" && \

# Normalize argument → agent name only (strip leading @, trailing slashes, and path prefixes)
AGENT_NAME=$(printf "%s" "$ARG_AGENT" | sed -E 's#^@##; s#/*$##; s#.*/##') && \

# Find agent directory anywhere in repo
AGENT_DIR=$(find . -type d -name "$AGENT_NAME" | head -n 1) && \
if [ -z "$AGENT_DIR" ]; then echo "Agent directory not found for: $AGENT_NAME" >&2; exit 1; fi && \

# Derive working directory (parent of the agent dir; typically the module root with tests/)
WORKDIR=$(dirname "$AGENT_DIR") && \
cd "$WORKDIR" && \

# Activate virtualenv if present
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; elif [ -f venv/bin/activate ]; then . venv/bin/activate; fi && \
export PYTHONPATH=. && \

# Prefer coverage CLI if available; fallback to python -m coverage
if command -v coverage >/dev/null 2>&1; then COV="coverage"; else COV="python -m coverage"; fi && \

# 1) Run just the specified test module with coverage limited to the agent
$COV run --source="$AGENT_NAME" -m unittest "$ARG_TEST" -v || true && \

# 2) Show missing lines (analysis target for Claude to propose edits)
$COV report --include="$AGENT_NAME/*" --show-missing | cat && \

# Generate/refresh HTML for visual inspection
$COV html --directory="coverage/$AGENT_NAME" --include="$AGENT_NAME/*" && \

# 5) Extract overall percent for quick threshold check (>= 75%)
PCT=$($COV report --include="$AGENT_NAME/*" | awk 'END{print $NF}' | tr -d '%') && \
if [ -z "$PCT" ]; then echo "Coverage percent not detected" >&2; exit 0; fi && \
if [ "$PCT" -lt 75 ]; then \
  echo "\nCoverage is below 75% ($PCT%). Analyze the missing lines above and update code/tests, then re-run."; \
else \
  echo "\nCoverage is >= 75% ($PCT%). Continue iterating toward 100%."; \
fi
```

### How to Use with Claude (recommended loop)

1. Run the command above with your agent and test file.
2. Claude reviews the missing lines (from the text report) and proposes edits:
   - If uncovered lines are error paths → add negative tests (exception cases)
   - If missing branches are unreachable → refactor code or adjust tests
   - If return schema not asserted → strengthen assertions
3. Claude applies edits to code/tests.
4. Re‑run the same command.
5. If coverage < 75%, Claude adds focused tests for the exact missing lines.
6. Repeat until 100% is achieved or justified.

## Testing Standards (enforced via docs)

### Coverage Requirements

- **Target Coverage**: 100% for all tools (preferred standard)
- **Minimum Coverage**: 90% (acceptable); 80% (threshold)
- **Critical modules** (init/config/core): 100% required
- **Agency Swarm tools**: 100% coverage expected

### Tool-Specific Coverage Approach

- Use `COVER @path/to/tool.py` pattern for targeted comprehensive coverage
- Create enhanced test files: `test_[tool_name]_fixed.py` with 100% coverage
- Include all business logic, error handling, and edge cases
- Test Agency Swarm BaseTool inheritance and Pydantic Field validation
- Mock external dependencies (APIs, Firestore, Drive) comprehensively

### Test File Organization (UPDATED for 100% Coverage)

- `test_[tool]_minimal.py` - Basic functionality tests
- `test_[tool]_fixed.py` - **Comprehensive 100% coverage tests (PRIORITY)**
- `test_[tool]_comprehensive.py` - **Boost tests for missing lines**
- `test_[tool]_integration.py` - End-to-end workflow tests
- `test_[tool]_error_handling.py` - Exception path testing

### Enhanced Testing Features

- **Pydantic Field Mocking**: Proper Agency Swarm v1.0.0 compatibility
- **HTTP Error Scenarios**: 403, 404, 429, 500 status code handling
- **Retry Logic Testing**: Exponential backoff and rate limiting
- **JSON Return Format**: Validate tool return structures
- **Main Block Execution**: Test standalone tool execution
- **Multi-Test Sequencing**: Run tests in order for maximum coverage combination

### Coverage Maintenance

- When a tool reaches 100% coverage, maintain through comprehensive test files
- Do not modify tests unless requirements or implementation change
- Create documentation for achieved coverage milestones
- Ensure test command runs all comprehensive tests together for accurate results

### 100% Coverage Verification Checklist

- **Run multi-test sequence**: Fixed tests + comprehensive tests + main blocks
- **Clear coverage data**: `coverage erase` before starting
- **Use --append flag**: Accumulate coverage across multiple test runs
- **Check HTML report**: Verify 0 missing lines in coverage/agent/index.html
- **Mock dependencies**: Use proven Agency Swarm v1.0.0 mock pattern
- **Test all paths**: Error handling, edge cases, alternative workflows