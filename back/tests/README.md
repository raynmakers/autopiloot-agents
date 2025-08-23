# Testing Guide for Python Firebase Template

This guide explains how to run tests in this Firebase Functions template project.

## Test Structure

The tests are organized into:

- `tests/integration/` - Integration tests that test complete workflows
- `tests/unit/` - Unit tests for individual components
- `tests/util/` - Test utilities and shared fixtures

## Test Types

### Unit Tests

Basic tests that don't require Firebase emulators:

```bash
# Run unit tests only
pytest tests/unit/ -v
```

### Function Logic Tests

Tests that only test function logic without database operations:

```bash
# Run tests that don't require database operations (example)
SKIP_EMULATORS=true pytest tests/integration/test_triggered_functions.py::TestTriggeredFunctions::test_on_item_created_error_handling -v
```

### Full Integration Tests with Emulators

Tests that require actual Firebase emulators running (most integration tests):

```bash
# Start emulators first (in separate terminal):
firebase emulators:start

# Then run tests:
pytest tests/integration/ -v
```

## Test Categories by Emulator Requirements

### ✅ Tests that work WITHOUT emulators:

- `test_on_item_created_error_handling` - Tests error handling with invalid data (no database needed)
- All tests in `tests/unit/` directory
- Tests that only validate function logic without database operations

### ⚠️ Tests that REQUIRE emulators:

- `test_on_item_created_trigger_execution` - Tests actual trigger execution with database
- `test_on_item_created_with_firestore_document_creation` - Tests document creation
- `test_triggered_function_with_different_event_types` - Tests event types
- `test_complete_item_lifecycle_with_triggers` - Tests complete workflows
- All tests that use `item_flow_setup` fixture (creates real Firestore documents in emulator)

## Important: Real Firebase Emulators, Not Mocks

This template uses **real Firebase emulators** for integration testing, not mocked Firebase calls. The tests:

- Connect to actual Firestore emulator running on localhost:8080
- Use real Firebase Functions emulator on localhost:5001
- Create and manipulate actual documents in the emulator database
- Test complete end-to-end workflows with real Firebase behavior

The only "mocking" is simulating Firestore trigger events for testing triggered functions.

## Running Tests

### Option 1: Function Logic Only (No Database)

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests that don't need database operations
SKIP_EMULATORS=true pytest tests/integration/test_triggered_functions.py::TestTriggeredFunctions::test_on_item_created_error_handling -v
```

### Option 2: Full Integration Testing (With Emulators)

```bash
# 1. Start Firebase emulators (in terminal 1)
firebase emulators:start

# 2. Run all tests (in terminal 2)
pytest tests/integration/ -v

# Or run specific test file
pytest tests/integration/test_triggered_functions.py -v
```

### Option 3: Automated Emulator Management

The template includes automatic emulator management:

```bash
# Tests will automatically start/stop emulators
pytest tests/integration/test_triggered_functions.py::TestTriggeredFunctions::test_on_item_created_trigger_execution -v
```

## Test Fixtures

### Available Fixtures

- `firebase_app` - Initialized Firebase admin app connected to emulators
- `firebase_emulator` - Emulator configuration and URLs
- `item_flow_setup` - Creates test user and category in emulator Firestore
- `mock_firestore_event` - Creates mock Firestore trigger event objects
- `setup_emulators` - Starts/stops emulators automatically

### Using Test Fixtures

```python
def test_example(firebase_app, item_flow_setup):
    # item_flow_setup provides real test data in emulator:
    # - item_flow_setup.db: ProjectDb instance connected to emulator
    # - item_flow_setup.user_id: Test user ID (real document in emulator)
    # - item_flow_setup.category_id: Test category ID (real document in emulator)

    # All database operations use real emulator, not mocks
    result = my_function_that_uses_firestore(item_flow_setup.user_id)
    assert result.success == True
```

## Environment Variables

- `SKIP_EMULATORS=true` - Skip automatic emulator startup
- `GCLOUD_PROJECT=test-project` - Firebase project ID for testing
- `FIRESTORE_EMULATOR_HOST=localhost:8080` - Firestore emulator host
- `FIREBASE_STORAGE_EMULATOR_HOST=localhost:9199` - Storage emulator host

## Troubleshooting

### Emulator Connection Issues

If tests fail with "Connection refused" errors:

1. Make sure Firebase CLI is installed: `npm install -g firebase-tools`
2. Start emulators manually: `firebase emulators:start`
3. Check ports 5001, 8080, 9199 are not in use
4. Verify emulators are running: `curl http://localhost:5001`

### Test Timeout Issues

If emulator startup times out:

```bash
# Increase timeout in firebase_emulator.py start_functions_emulator()
timeout = 120  # Increase from 60 to 120 seconds
```

### Credential Issues

The template uses a test service account file. Make sure:

- `blank-test-project-firebase-adminsdk-k2n85-7570e24581.json` exists
- File has proper JSON format
- Project ID matches in all configuration files

## Example Test Run Commands

```bash
# Run all tests with coverage
pytest --cov=src

# Run specific test class
pytest tests/integration/test_triggered_functions.py::TestTriggeredFunctions -v

# Run with verbose output and no capture
pytest tests/integration/test_triggered_functions.py -v -s

# Run tests matching pattern
pytest -k "test_error_handling" -v

# Run integration tests with emulators
firebase emulators:start &
pytest tests/integration/ -v
```

## Writing New Tests

### For tests that DON'T need Firestore:

```python
def test_my_function():
    # Test logic that doesn't require database
    # These tests validate function logic only
    assert my_function() == expected_result
```

### For tests that DO need Firestore (most integration tests):

```python
def test_my_function_with_db(item_flow_setup):
    # Use the provided test data from emulator
    user_id = item_flow_setup.user_id
    category_id = item_flow_setup.category_id
    db = item_flow_setup.db  # Connected to emulator

    # Test your database operations against real emulator
    result = my_function_that_uses_db(user_id, category_id)

    # Verify by reading from emulator database
    doc = db.collections["items"].document(result.item_id).get()
    assert doc.exists
    assert doc.to_dict()["name"] == "Expected Name"
```

### For testing triggered functions:

```python
def test_my_trigger(mock_firestore_event, item_flow_setup):
    # Create mock event (simulates Firestore trigger)
    event = mock_firestore_event("items/test-item", {
        "name": "Test Item",
        "categoryId": item_flow_setup.category_id
    })

    # Test the trigger function (uses real emulator database)
    result = my_trigger_function(event)

    # Verify side effects in emulator database
    category_doc = item_flow_setup.db.collections["categories"].document(
        item_flow_setup.category_id
    ).get()
    assert category_doc.to_dict()["itemCount"] == 1
```

## Key Principles

1. **Real Emulators**: All integration tests use real Firebase emulators
2. **No Mocking**: Database operations are real calls to emulator, not mocked
3. **Isolation**: Each test gets fresh test data via fixtures
4. **Cleanup**: Fixtures automatically clean up test data
5. **Speed**: Use `SKIP_EMULATORS=true` for tests that don't need database
