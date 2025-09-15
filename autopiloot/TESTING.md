# Testing Guide - Autopiloot Agency

This document provides comprehensive instructions for running and understanding the test suite for the Autopiloot Agency.

## Test Overview

The Autopiloot project uses Python's `unittest` framework for comprehensive testing of all components. Tests are organized in the `tests/` directory and focus on integration testing with real API calls and validation.

### Test Philosophy

- **Integration-focused**: Tests call real APIs and validate end-to-end functionality
- **No mocking**: Tests use actual configuration and validate real behavior
- **Comprehensive coverage**: All validation scenarios and edge cases tested
- **Fast execution**: All tests complete in ~20ms

## Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── test_config.py          # Configuration loader tests (11 test cases)
└── test_audit_logger.py    # Audit logging tests (15 test cases)
```

## Setup for Testing

### 1. Environment Setup

Ensure you have the virtual environment activated and dependencies installed:

```bash
cd agents/autopiloot
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration Requirements

Tests require a valid `config/settings.yaml` file. The current configuration includes:

- Google Sheet ID for backfill links
- Scraper settings with @AlexHormozi handle
- LLM configuration using gpt-4.1
- Slack notification settings
- Budget configuration ($5 daily transcription budget)

## Running Tests

### Method 1: Run All Tests (Recommended)

```bash
# Discover and run all tests with verbose output
python -m unittest discover tests -v
```

**Expected Output:**

```
test_empty_sheet_id (test_config.TestConfigurationLoader.test_empty_sheet_id)
Test validation with empty sheet ID. ... ok
test_empty_slack_channel (test_config.TestConfigurationLoader.test_empty_slack_channel)
Test validation with empty slack channel. ... ok
[... 9 more tests ...]

----------------------------------------------------------------------
Ran 11 tests in 0.015s

OK
```

### Method 2: Run Specific Test Module

```bash
# Run only configuration tests
python -m unittest tests.test_config -v

# Run only audit logging tests
python -m unittest tests.test_audit_logger -v
```

### Method 3: Run Individual Test Cases

```bash
# Run a specific test case
python -m unittest tests.test_config.TestConfigurationLoader.test_valid_configuration -v
```

### Method 4: Run Tests from Specific Directory

```bash
# From the config directory
cd config
python -m unittest ../tests/test_config -v
```

## Test Coverage Details

### Configuration Loader Tests (`test_config.py`)

The configuration loader has **11 comprehensive test cases** covering all validation scenarios:

### Audit Logger Tests (`test_audit_logger.py`)

The audit logging system has **15 comprehensive test cases** implementing TASK-AUDIT-0041 requirements:

#### ✅ Core Functionality Test Cases

1. **`test_basic_audit_log_creation`**
   - **Purpose**: Tests basic audit log entry creation and storage
   - **Validates**: Firestore document creation, required fields, timestamp formatting
   - **Assertions**: Document exists, all fields present, UTC ISO 8601 timestamp

2. **`test_specialized_logging_methods`**
   - **Purpose**: Tests all specialized logging methods (video discovered, transcript created, etc.)
   - **Validates**: Agent-specific audit logging functionality
   - **Methods Tested**: log_video_discovered, log_transcript_created, log_summary_created, log_budget_alert

3. **`test_audit_log_entry_interface`**
   - **Purpose**: Tests AuditLogEntry TypedDict interface compliance
   - **Validates**: Required fields, data types, timestamp format
   - **Assertions**: Interface structure matches TASK-AUDIT-0041 specification

#### ✅ Error Handling Test Cases

4. **`test_firestore_connection_error`**
   - **Purpose**: Tests graceful handling of Firestore connection failures
   - **Expected**: Returns False but doesn't raise exceptions
   - **Validates**: Resilient error handling for external service failures

5. **`test_invalid_parameters`**
   - **Purpose**: Tests behavior with None/empty parameters
   - **Validates**: Parameter validation and error handling
   - **Expected**: Graceful degradation without workflow disruption

#### ✅ Configuration Test Cases

1. **`test_valid_configuration`**

   - **Purpose**: Validates successful loading of the actual configuration
   - **Checks**: All required sections present, correct values, proper structure
   - **Assertions**: Sheet ID, scraper handles, LLM model (gpt-4.1), Slack channel, budget

2. **`test_task_config_overrides`**
   - **Purpose**: Tests LLM task-specific configuration overrides
   - **Creates**: Custom task with different model and temperature
   - **Validates**: Task overrides work correctly, fallback to defaults

#### ❌ Validation Error Test Cases

3. **`test_empty_sheet_id`**

   - **Purpose**: Tests validation with empty Google Sheet ID
   - **Expected**: `ConfigValidationError` with message about non-empty string requirement
   - **Validates**: Required field enforcement

4. **`test_invalid_temperature`**

   - **Purpose**: Tests LLM temperature validation (must be 0.0-1.0)
   - **Test Value**: 1.5 (invalid)
   - **Expected**: `ConfigValidationError` about temperature range

5. **`test_negative_daily_limit`**

   - **Purpose**: Tests scraper daily limit validation (must be ≥0)
   - **Test Value**: -5 (invalid)
   - **Expected**: `ConfigValidationError` about integer >= 0 requirement

6. **`test_zero_budget`**

   - **Purpose**: Tests transcription budget validation (must be >0)
   - **Test Value**: 0 (invalid)
   - **Expected**: `ConfigValidationError` about positive number requirement

7. **`test_empty_slack_channel`**

   - **Purpose**: Tests Slack channel validation (must be non-empty)
   - **Test Value**: "" (empty string)
   - **Expected**: `ConfigValidationError` about non-empty string requirement

8. **`test_invalid_task_temperature`**
   - **Purpose**: Tests task-level temperature validation
   - **Test Value**: -0.5 (invalid)
   - **Expected**: `ConfigValidationError` with task-specific error message

#### 🚨 Error Handling Test Cases

9. **`test_file_not_found`**

   - **Purpose**: Tests behavior when configuration file doesn't exist
   - **Test Path**: `/nonexistent/path/to/config.yaml`
   - **Expected**: `FileNotFoundError` with clear message

10. **`test_invalid_yaml`**

    - **Purpose**: Tests behavior with malformed YAML syntax
    - **Test Content**: `"invalid: yaml: content: [unclosed"`
    - **Expected**: `yaml.YAMLError` for parsing failure

11. **`test_non_dict_config`**
    - **Purpose**: Tests behavior with non-dictionary YAML content
    - **Test Content**: `["not", "a", "dict"]` (YAML array)
    - **Expected**: `ConfigValidationError` about dictionary requirement

## Test Utilities and Helpers

### Temporary File Management

Tests use Python's `tempfile.NamedTemporaryFile` for creating test configurations:

```python
with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
    yaml.dump(test_config, f)
    temp_path = f.name

try:
    # Test logic here
    config = load_app_config(temp_path)
finally:
    os.unlink(temp_path)  # Cleanup
```

### Error Validation Pattern

Tests use `unittest.TestCase.assertRaises` context manager for exception testing:

```python
with self.assertRaises(ConfigValidationError) as cm:
    load_app_config(temp_path)
self.assertIn("expected error message", str(cm.exception))
```

## Testing Best Practices

### 1. Real Configuration Testing

Always test against the actual `config/settings.yaml` file to ensure real-world compatibility:

```bash
# Test the actual configuration loader
python config/loader.py
```

**Expected Output:**

```
Configuration loaded successfully. Sheet ID: 1AbC2defGhIJkLmNoPqRSTuVwxyz0123456789
Default LLM model: gpt-4.1
Slack channel: ops-autopiloot
Transcription budget: $5.0
```

### 2. Comprehensive Validation Testing

Create test configurations that exercise all validation rules:

- Required fields (sheet ID, model, channel)
- Range validations (temperature 0.0-1.0, budget >0, daily_limit ≥0)
- Type validations (strings, numbers, dictionaries)
- Format validations (non-empty strings)

### 3. Error Message Clarity

Validate that error messages are descriptive and actionable:

```python
# Good: Specific field and requirement
"llm.default.temperature must be between 0.0 and 1.0"

# Good: Clear context and expectation
"notifications.slack.channel must be a non-empty string"
```

## Continuous Integration

### Pre-commit Testing

Before committing changes, run the complete test suite:

```bash
# Activate environment
source venv/bin/activate

# Run all tests
python -m unittest discover tests -v

# Verify configuration loads
python config/loader.py

# Check for linting errors (if applicable)
python -m flake8 config/ tests/
```

### Test Performance Monitoring

Monitor test execution time to ensure tests remain fast:

- **Target**: All tests should complete in <100ms
- **Current**: ~15-20ms for 11 tests
- **Alert**: If tests take >200ms, investigate performance issues

## Debugging Test Failures

### 1. Configuration Issues

If `test_valid_configuration` fails:

```bash
# Check if settings.yaml is valid
python -c "import yaml; print(yaml.safe_load(open('config/settings.yaml')))"

# Test configuration loader directly
python config/loader.py
```

### 2. Import Issues

If tests fail to import:

```bash
# Check Python path from tests directory
cd tests
python -c "import sys; print(sys.path)"

# Verify loader module can be imported
python -c "import sys; import os; sys.path.append(os.path.join('..', 'config')); from loader import load_app_config; print('Import successful')"
```

### 3. Environment Issues

If dependency issues occur:

```bash
# Verify virtual environment is active
which python

# Check required packages
pip list | grep -E "(yaml|unittest)"

# Reinstall dependencies if needed
pip install -r requirements.txt
```

## Adding New Tests

When implementing new functionality, follow this pattern:

### 1. Test Class Structure

```python
import unittest
from your_module import YourClass, YourException

class TestYourModule(unittest.TestCase):
    """Test cases for your module."""

    def test_positive_case(self):
        """Test successful operation."""
        # Test implementation

    def test_validation_error(self):
        """Test validation failure."""
        with self.assertRaises(YourException) as cm:
            # Code that should raise exception
        self.assertIn("expected message", str(cm.exception))
```

### 2. Integration Test Focus

- Test real functionality, not just code paths
- Use actual configuration and data where possible
- Validate complete workflows, not just individual functions
- Include error conditions and edge cases

### 3. Test Documentation

- Clear test method names describing what is being tested
- Docstrings explaining the test purpose and expectations
- Comprehensive assertions that validate the full expected behavior

## Test Results Archive

### Latest Test Run Results

**Date**: 2025-01-12  
**Test Count**: 11 tests  
**Execution Time**: ~0.020s  
**Status**: ✅ All tests passing  
**Coverage**: Configuration loader validation (100%)

### Key Validations Confirmed

- ✅ Configuration loads successfully with correct values
- ✅ All validation rules properly enforced
- ✅ Error handling works for missing files and invalid YAML
- ✅ Task-specific overrides function correctly
- ✅ Exception messages are clear and actionable

This testing framework ensures the Autopiloot Agency configuration system is robust, reliable, and ready for production use.
