# Testing Guide - Autopiloot Agency

This document provides comprehensive instructions for running and understanding the test suite for the Autopiloot Agency.

## Test Overview

The Autopiloot project uses Python's `unittest` framework for comprehensive testing of all components. Tests are organized in the `tests/` directory and focus on deterministic testing with external service mocking.

### Test Philosophy

- **Deterministic testing**: All external APIs mocked for consistent CI results
- **Comprehensive mocking**: External services (Slack, Firestore, AssemblyAI, YouTube) mocked by default
- **Coverage tracking**: Minimum 80% coverage for all modules; ideal 100%
- **Exception coverage**: Always include tests that trigger and assert exceptions and error paths
- **Fast execution**: Test suite optimized for CI with parallel execution
- **Security validation**: No secrets in tests, secure mock patterns

## Test Structure

```
tests/
├── __init__.py
├── test_config.py
├── test_env_loader.py
├── test_audit_logger.py
├── test_reliability.py
├── test_sheets.py
├── test_send_slack_message.py
├── test_send_error_alert.py
└── ... (additional agent tool tests)
```

## Coverage Standards

- **Minimum coverage (required): 80%** per module and per PR.
- **Ideal coverage (target): 100%**. Strive for full coverage where practical.
- **Critical modules** (agent initialization files, configuration loaders, core initialization paths): **100% required**.
- **Tools and integrations**: **≥ 80% required**, 100% ideal.
- **Stability rule**: If a module’s tests achieve **100% coverage**, do not modify those tests unless the implementation or requirements change.
- **Reporting**: Always generate HTML and text coverage reports and commit them under the appropriate coverage folder (e.g., `coverage/<area>/`).
- **CI policy**: Pull requests should fail if any touched module falls below **80%** coverage.

## Exception Testing Requirements

Exceptions and error paths must be explicitly tested. Every public function, tool `run()` method, and critical code path requires at least one negative test case that asserts the expected failure behavior.

### What to Test

- Invalid inputs and boundary values (empty strings, `None`, out-of-range numbers)
- Missing configuration or environment variables
- External dependency failures (HTTP errors, SDK exceptions, timeouts)
- Permission/authorization failures
- Serialization/parsing errors (YAML/JSON)
- Retry/backoff and DLQ routing conditions (where applicable)

### How to Test

- Use `unittest.TestCase.assertRaises` (or context managers) to assert the exact exception type
- Assert exception message contains actionable context with `self.assertIn("expected", str(cm.exception))`
- For tools that return error payloads (JSON), assert the schema:
  - keys: `error`, `message`, `details`
  - details include context (e.g., `file_name`, `mime_type`, `type`)
- Verify side-effects do not occur on failure (no writes, no state changes)
- For retry flows, assert number of attempts/backoff boundaries using mocks

### Example Patterns

```python
with self.assertRaises(ConfigValidationError) as cm:
    load_app_config("/bad/path.yaml")
self.assertIn("not found", str(cm.exception))

# Tool error schema validation
result = json.loads(tool.run())
self.assertIn("error", result)
self.assertIn("message", result)
self.assertIn("details", result)
self.assertEqual(result["error"], "extraction_error")
```

### Policy

- PRs introducing new logic must include both success and failure tests
- Refactors must preserve existing exception tests; if behavior changes, update tests accordingly
- Modules at **100% coverage**: do not modify tests unless implementation or requirements change

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

### Local Testing

```bash
# From autopiloot directory with PYTHONPATH set
cd /path/to/autopiloot
PYTHONPATH=. python -m unittest discover tests -v

# Run with coverage tracking
pip install pytest pytest-cov
PYTHONPATH=. python -m pytest tests/ --cov=. --cov-report=html

# Run specific test modules
PYTHONPATH=. python -m unittest tests.test_config -v
PYTHONPATH=. python -m unittest tests.test_observability_ops -v
```

### CI/CD Testing

The CI workflow automatically runs on:

- **Push to main/develop branches**
- **Pull requests**
- **Multiple Python versions** (3.9, 3.10, 3.11)

CI pipeline includes:

- **Unit tests** with external service mocking
- **Linting** with ruff
- **Type checking** with mypy
- **Security scanning** with bandit
- **Coverage reporting** to Codecov
- **Documentation validation**

### Method 1: Run All Tests (Recommended)

```bash
# Discover and run all tests with verbose output
PYTHONPATH=. python -m unittest discover tests -v
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

## External API Mocking

### Mocked Services in CI

All external integrations are automatically mocked in CI to ensure deterministic test results:

#### API Services Mocked

- **OpenAI API**: LLM calls mocked with sample responses and token usage
- **AssemblyAI API**: Transcription jobs mocked with status progression
- **YouTube Data API**: Video metadata mocked with sample data
- **Slack API**: Message sending mocked with success responses
- **Zep API**: GraphRAG operations mocked with acknowledgments

#### Google Cloud Services Mocked

- **Firestore**: Document operations mocked with in-memory storage
- **Google Drive**: File uploads mocked with generated IDs
- **Google Sheets**: Spreadsheet operations mocked with sample data

#### Mock Implementation Pattern

```python
import unittest
from unittest.mock import patch, Mock

class TestExternalIntegration(unittest.TestCase):

    @patch('requests.post')
    def test_api_call_success(self, mock_post):
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "id": "test_123"}
        mock_post.return_value = mock_response

        # Test the tool with mocked external service
        tool = ExternalServiceTool()
        result = tool.run()

        # Verify mock was called and result is correct
        mock_post.assert_called_once()
        self.assertIn("success", result)

    @patch('google.cloud.firestore.Client')
    def test_firestore_operation(self, mock_client):
        # Mock Firestore operations
        mock_doc = Mock()
        mock_doc.get.return_value.to_dict.return_value = {"field": "value"}
        mock_client.return_value.collection.return_value.document.return_value = mock_doc

        # Test Firestore-dependent functionality
        result = firestore_tool.run()
        self.assertIsNotNone(result)
```

### Environment Variables for Testing

CI sets mock environment variables to prevent real API calls:

```bash
export OPENAI_API_KEY="test-key-openai"
export ASSEMBLYAI_API_KEY="test-key-assemblyai"
export YOUTUBE_API_KEY="test-key-youtube"
export SLACK_BOT_TOKEN="test-token-slack"
export ZEP_API_KEY="test-key-zep"
export GCP_PROJECT_ID="test-project-123"
export GOOGLE_APPLICATION_CREDENTIALS="/tmp/test-credentials.json"
export GOOGLE_DRIVE_FOLDER_ID_TRANSCRIPTS="test-folder-transcripts"
export GOOGLE_DRIVE_FOLDER_ID_SUMMARIES="test-folder-summaries"
```

### OpenSearch Configuration Testing

OpenSearch provides keyword/boolean retrieval for Hybrid RAG (alongside Zep semantic search). Configuration testing ensures proper authentication setup and validation logic.

#### Configuration Structure

OpenSearch configuration is split across two layers:

1. **settings.yaml** (config/settings.yaml) - Operational settings:
   ```yaml
   rag:
     opensearch:
       enabled: true
       host: ""  # Set via OPENSEARCH_HOST environment variable
       index_transcripts: "autopiloot_transcripts"
       top_k: 20
       timeout_ms: 1500
       weights:
         semantic: 0.6  # Zep semantic search weight
         keyword: 0.4   # OpenSearch keyword search weight
       connection:
         verify_certs: true
         use_ssl: true
         max_retries: 3
         retry_on_timeout: true
   ```

2. **.env file** - Authentication credentials:
   ```bash
   # OpenSearch host (required to enable OpenSearch)
   OPENSEARCH_HOST=https://your-opensearch-instance.com:9200

   # Authentication: Use API Key OR Username+Password
   OPENSEARCH_API_KEY=your-api-key-here
   # OR
   OPENSEARCH_USERNAME=admin
   OPENSEARCH_PASSWORD=your-password-here
   ```

#### Authentication Requirements

The validation logic in `config/env_loader.py` ensures:

1. **Optional Feature**: If `OPENSEARCH_HOST` is empty, OpenSearch is disabled (no error)
2. **Authentication Required**: If `OPENSEARCH_HOST` is set, at least one auth method must be configured:
   - **Option A**: `OPENSEARCH_API_KEY` (API key authentication)
   - **Option B**: `OPENSEARCH_USERNAME` + `OPENSEARCH_PASSWORD` (basic authentication)
3. **Basic Auth Validation**: Both username AND password required together

#### Testing Configuration Validation

Test the OpenSearch validation logic using the `env_loader.py` test harness:

```bash
# Test with current environment
cd autopiloot
python config/env_loader.py

# Expected output when OpenSearch is not configured:
#   - OpenSearch configuration: ⚪ Not configured (optional)

# Expected output when OpenSearch is configured with API key:
#   - OpenSearch configuration: ✅ https://your-host.com:9200 (API Key)

# Expected output when OpenSearch is configured with basic auth:
#   - OpenSearch configuration: ✅ https://your-host.com:9200 (Basic Auth)
```

#### Error Scenarios to Test

1. **Missing Authentication**:
   ```bash
   # Set host but no auth credentials
   export OPENSEARCH_HOST="https://example.com:9200"
   export OPENSEARCH_API_KEY=""
   export OPENSEARCH_USERNAME=""
   export OPENSEARCH_PASSWORD=""

   python config/env_loader.py
   # Expected: ❌ Error about missing authentication method
   ```

2. **Incomplete Basic Auth**:
   ```bash
   # Username without password
   export OPENSEARCH_HOST="https://example.com:9200"
   export OPENSEARCH_USERNAME="admin"
   export OPENSEARCH_PASSWORD=""

   python config/env_loader.py
   # Expected: ❌ Error about requiring both username and password
   ```

3. **Valid API Key Authentication**:
   ```bash
   export OPENSEARCH_HOST="https://example.com:9200"
   export OPENSEARCH_API_KEY="valid-api-key"

   python config/env_loader.py
   # Expected: ✅ OpenSearch configuration valid
   ```

4. **Valid Basic Authentication**:
   ```bash
   export OPENSEARCH_HOST="https://example.com:9200"
   export OPENSEARCH_USERNAME="admin"
   export OPENSEARCH_PASSWORD="secret"

   python config/env_loader.py
   # Expected: ✅ OpenSearch configuration valid
   ```

#### Integration Testing

When implementing OpenSearch integration tools:

1. **Mock OpenSearch Client**:
   ```python
   from unittest.mock import patch, Mock

   @patch('opensearchpy.OpenSearch')
   def test_opensearch_connection(self, mock_client):
       # Mock successful connection
       mock_instance = Mock()
       mock_instance.info.return_value = {"version": {"number": "2.11.0"}}
       mock_client.return_value = mock_instance

       # Test connection logic
       client = create_opensearch_client()
       self.assertIsNotNone(client)
   ```

2. **Test Both Authentication Methods**:
   - Test API key authentication path
   - Test basic authentication path
   - Test authentication failure scenarios

3. **Test Hybrid Search Weights**:
   - Verify semantic and keyword weights sum to 1.0
   - Test weight configuration loading from settings.yaml

#### CI Environment Variables

For CI testing, add mock OpenSearch credentials:

```bash
# GitHub Actions / CI
export OPENSEARCH_HOST="https://test-opensearch.localhost:9200"
export OPENSEARCH_API_KEY="test-api-key-opensearch"
# Note: Leave OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD empty to test API key auth
```

### BigQuery Configuration Testing

BigQuery provides transcript chunk storage and SQL-based analytics for Hybrid RAG. Configuration testing ensures proper GCP prerequisites and validates schema setup.

#### Configuration Structure

BigQuery configuration is split across two layers:

1. **settings.yaml** (config/settings.yaml) - Dataset and table configuration:
   ```yaml
   rag:
     bigquery:
       enabled: true
       dataset: "autopiloot"  # BigQuery dataset name
       location: "EU"  # Dataset location (EU, US, etc.)
       tables:
         transcript_chunks: "transcript_chunks"  # Table name
       schema:
         # Auto-created schema if table doesn't exist:
         # - video_id: STRING (YouTube video ID)
         # - chunk_id: STRING (Unique chunk identifier)
         # - title: STRING (Video title)
         # - channel_id: STRING (YouTube channel ID)
         # - published_at: TIMESTAMP (Video publication date)
         # - duration_sec: INT64 (Video duration in seconds)
         # - content_sha256: STRING (SHA256 hash for idempotency)
         # - tokens: INT64 (Token count for chunk)
         # - text: STRING (Chunk text content)
       write_disposition: "WRITE_APPEND"
       batch_size: 500  # Rows per batch insert
   ```

2. **Environment variables** - Uses existing GCP credentials:
   ```bash
   # Already required for Firestore and Drive
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
   GCP_PROJECT_ID=your-gcp-project-id
   ```

#### Prerequisites

BigQuery requires the same GCP credentials used by Firestore and Google Drive:

1. **Service Account**: Must have BigQuery permissions:
   - `roles/bigquery.dataEditor` (read/write data)
   - `roles/bigquery.jobUser` (run queries and jobs)
2. **Project ID**: Must match the GCP project containing the dataset
3. **Dataset Location**: Must match your data residency requirements (EU, US, etc.)

#### Testing Configuration Validation

Test the BigQuery validation logic using the `env_loader.py` test harness:

```bash
# Test with current environment
cd autopiloot
venv/bin/python config/env_loader.py

# Expected output when GCP credentials are configured:
#   - BigQuery configuration: ✅ your-project-id (ready for use)

# Expected output when GCP credentials are missing:
#   - BigQuery configuration: ⚪ GCP credentials required (see settings.yaml)
```

#### Schema Design and Idempotency

The `transcript_chunks` table schema supports idempotent writes:

**Primary Deduplication Strategy**: Use `(video_id, chunk_id)` composite key
- Video ID uniquely identifies the source video
- Chunk ID identifies the chunk within the video

**Alternative Deduplication**: Use `content_sha256` hash
- SHA256 hash of chunk text ensures exact content matching
- Useful for detecting duplicate content across videos

**Example Query for Deduplication**:
```sql
-- Check for existing chunks before insert
SELECT video_id, chunk_id
FROM `autopiloot.transcript_chunks`
WHERE video_id = @video_id
  AND chunk_id IN UNNEST(@chunk_ids)

-- Or use content hash
SELECT content_sha256
FROM `autopiloot.transcript_chunks`
WHERE content_sha256 IN UNNEST(@hashes)
```

#### Dataset and Table Creation

Tools using BigQuery should follow this pattern:

```python
from google.cloud import bigquery
from config.env_loader import get_required_env_var
from config.loader import get_config_value

def initialize_bigquery():
    """Initialize BigQuery client and ensure dataset/table exist."""
    project_id = get_required_env_var("GCP_PROJECT_ID", "GCP project for BigQuery")
    dataset_name = get_config_value("rag.bigquery.dataset", "autopiloot")
    location = get_config_value("rag.bigquery.location", "EU")

    client = bigquery.Client(project=project_id)

    # Create dataset if not exists
    dataset_id = f"{project_id}.{dataset_name}"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = location
    dataset = client.create_dataset(dataset, exists_ok=True)

    # Create table if not exists
    table_name = get_config_value("rag.bigquery.tables.transcript_chunks", "transcript_chunks")
    table_id = f"{dataset_id}.{table_name}"

    schema = [
        bigquery.SchemaField("video_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("chunk_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("title", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("channel_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("published_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("duration_sec", "INT64", mode="NULLABLE"),
        bigquery.SchemaField("content_sha256", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("tokens", "INT64", mode="NULLABLE"),
        bigquery.SchemaField("text", "STRING", mode="REQUIRED"),
    ]

    table = bigquery.Table(table_id, schema=schema)
    table = client.create_table(table, exists_ok=True)

    return client, table_id
```

#### Integration Testing

When implementing BigQuery integration tools:

1. **Mock BigQuery Client**:
   ```python
   from unittest.mock import patch, Mock

   @patch('google.cloud.bigquery.Client')
   def test_bigquery_initialization(self, mock_client):
       # Mock dataset and table creation
       mock_instance = Mock()
       mock_instance.create_dataset.return_value = Mock()
       mock_instance.create_table.return_value = Mock()
       mock_client.return_value = mock_instance

       # Test initialization logic
       client, table_id = initialize_bigquery()
       self.assertIsNotNone(client)
       self.assertIn("transcript_chunks", table_id)
   ```

2. **Test Batch Insertion**:
   ```python
   @patch('google.cloud.bigquery.Client')
   def test_batch_insert_chunks(self, mock_client):
       # Mock insert_rows_json
       mock_instance = Mock()
       mock_instance.insert_rows_json.return_value = []  # Empty list = success
       mock_client.return_value = mock_instance

       # Test batch insertion
       chunks = [{"video_id": "test", "chunk_id": "1", "text": "content"}]
       errors = insert_transcript_chunks(chunks)
       self.assertEqual(len(errors), 0)
   ```

3. **Test Idempotency**:
   - Mock query to check existing chunks
   - Verify only new chunks are inserted
   - Test content hash collision handling

#### Local Development and Testing

For local development without affecting production data:

1. **Use a separate dataset**:
   ```yaml
   # config/settings.yaml (development)
   rag:
     bigquery:
       dataset: "autopiloot_dev"  # Separate dev dataset
       location: "EU"
   ```

2. **Test with emulator** (optional):
   ```bash
   # BigQuery emulator not officially supported
   # Instead, use separate dev dataset in GCP
   gcloud config set project your-dev-project-id
   ```

3. **Clean up test data**:
   ```sql
   -- Delete test chunks after development
   DELETE FROM `autopiloot_dev.transcript_chunks`
   WHERE video_id LIKE 'test_%'
   ```

#### Performance Considerations

1. **Batch Writes**: Use batch size of 500 rows (configurable in settings.yaml)
2. **Streaming Inserts**: Consider Storage Write API for high-volume ingestion
3. **Partitioning**: Add partitioning by `published_at` for large datasets:
   ```python
   table.time_partitioning = bigquery.TimePartitioning(
       type_=bigquery.TimePartitioningType.DAY,
       field="published_at"
   )
   ```

#### CI Environment Variables

For CI testing, BigQuery uses existing GCP credentials:

```bash
# GitHub Actions / CI
export GCP_PROJECT_ID="test-project-123"
export GOOGLE_APPLICATION_CREDENTIALS="/tmp/test-credentials.json"
# BigQuery configuration loaded from settings.yaml
```

### Security Testing

The CI pipeline includes security validation:

- **Secret scanning**: Prevents API keys from being committed
- **Bandit security analysis**: Identifies security vulnerabilities
- **Safety dependency checking**: Validates dependencies for known CVEs
- **Credential validation**: Ensures no real credentials in test code

This testing framework ensures the Autopiloot Agency configuration system is robust, reliable, and ready for production use.
