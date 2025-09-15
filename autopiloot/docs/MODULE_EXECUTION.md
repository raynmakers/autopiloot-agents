# Module Execution Patterns

This document describes the proper execution patterns for Autopiloot Agency modules and tools to avoid import issues and ensure reliable operation.

## Overview

The Autopiloot Agency is structured as a proper Python package with:
- Consistent `__init__.py` files in all directories
- Centralized utilities in `core/` module
- Absolute imports throughout the codebase
- Support for `python -m` execution

## Execution Patterns

### 1. Agent Execution

Execute agents from the project root using the `-m` flag:

```bash
# From /path/to/autopiloot directory
python -m agency                    # Run complete agency
python -m orchestrator_agent       # Run specific agent (if standalone)
python -m scraper_agent            # Run specific agent (if standalone)
```

### 2. Tool Testing

Execute individual tools for testing:

```bash
# From autopiloot directory
python -m scraper_agent.tools.save_video_metadata
python -m transcriber_agent.tools.submit_assemblyai_job
python -m observability_agent.tools.monitor_dlq_trends
python -m orchestrator_agent.tools.plan_daily_run
```

### 3. Core Utilities Testing

Test core utilities directly:

```bash
python -m core.time_utils           # Test time utilities
python -m core.slack_utils          # Test slack utilities  
python -m core.reliability          # Test reliability utilities
python -m config.loader             # Test configuration loader
python -m config.env_loader         # Test environment validation
```

### 4. Configuration and Testing

Run configuration and tests:

```bash
python -m config.loader             # Validate configuration
python -m config.env_loader         # Validate environment variables
python -m unittest discover tests  # Run all tests
python -m tests.test_config         # Run specific test module
```

## Import Patterns

### Absolute Imports Only

❌ **Avoid relative imports:**
```python
from ..core import time_utils       # Don't do this
from .reliability import RetryPolicy # Don't do this
```

✅ **Use absolute imports:**
```python
from core.time_utils import now, to_iso8601_z
from core.slack_utils import format_alert_blocks
from core.reliability import RetryPolicy
```

### Core Utilities Import

✅ **Import from core package:**
```python
# Time utilities
from core.time_utils import (
    now, 
    to_iso8601_z, 
    calculate_exponential_backoff,
    format_duration_human
)

# Slack utilities
from core.slack_utils import (
    normalize_channel_name,
    format_alert_blocks,
    create_error_alert
)

# Reliability utilities  
from core.reliability import (
    RetryPolicy,
    DeadLetterQueue,
    JobRetryManager
)
```

### Configuration Import

✅ **Import configuration utilities:**
```python
from config.loader import (
    load_app_config,
    get_orchestrator_max_parallel_jobs,
    get_retry_max_attempts
)

from config.env_loader import (
    get_required_env_var,
    validate_gcp_project_access,
    get_api_key
)
```

## Directory Structure Requirements

### Required __init__.py Files

All these directories must have `__init__.py` files:

```
autopiloot/
├── __init__.py                     ✅ Root package
├── core/
│   └── __init__.py                 ✅ Core utilities package
├── config/
│   └── __init__.py                 ✅ Configuration package  
├── orchestrator_agent/
│   ├── __init__.py                 ✅ Agent package
│   └── tools/
│       └── __init__.py             ✅ Tools package
├── scraper_agent/
│   ├── __init__.py                 ✅ Agent package
│   └── tools/
│       └── __init__.py             ✅ Tools package
├── transcriber_agent/
│   ├── __init__.py                 ✅ Agent package
│   └── tools/
│       └── __init__.py             ✅ Tools package
├── summarizer_agent/
│   ├── __init__.py                 ✅ Agent package
│   └── tools/
│       └── __init__.py             ✅ Tools package
├── observability_agent/
│   ├── __init__.py                 ✅ Agent package
│   └── tools/
│       └── __init__.py             ✅ Tools package
└── tests/
    └── __init__.py                 ✅ Tests package
```

## Common Utilities Usage

### Time and Date Handling

```python
from core.time_utils import now, to_iso8601_z, calculate_exponential_backoff

# Get current UTC time
current_time = now()

# Format for Firestore/API consumption
timestamp = to_iso8601_z(current_time)

# Calculate retry delays
delay = calculate_exponential_backoff(attempt=2, base_delay=60)
```

### Slack Message Formatting

```python
from core.slack_utils import format_alert_blocks, normalize_channel_name

# Create error alert
blocks = format_alert_blocks(
    title="System Error",
    message="Transcription job failed",
    alert_type="error",
    details={"video_id": "abc123", "error": "API timeout"}
)

# Normalize channel name
channel = normalize_channel_name("#ops-alerts")  # -> "ops-alerts"
```

### Retry and Backoff Logic

```python
from core.time_utils import calculate_exponential_backoff, get_next_retry_time
from core.reliability import RetryPolicy, JobRetryManager

# Standard retry configuration
retry_policy = RetryPolicy(max_attempts=3, base_delay_seconds=60)

# Calculate next retry time
next_retry = get_next_retry_time(attempt=2, base_delay=60)
```

## Error Handling

### Import Error Prevention

1. **Always use absolute imports** from the autopiloot root
2. **Set PYTHONPATH** when running modules directly:
   ```bash
   PYTHONPATH=. python -m core.time_utils
   ```
3. **Use the correct working directory** (autopiloot root)

### Common Import Issues

❌ **Problem: ModuleNotFoundError**
```
ModuleNotFoundError: No module named 'core.time_utils'
```

✅ **Solution: Run from correct directory with PYTHONPATH**
```bash
cd /path/to/autopiloot
PYTHONPATH=. python -m your_module
```

❌ **Problem: Relative import in non-package**
```
ImportError: attempted relative import with no known parent package
```

✅ **Solution: Use absolute imports and python -m**
```python
# Change from:
from ..core import time_utils

# To:
from core import time_utils
```

## Development Guidelines

### Adding New Tools

When creating new tools:

1. **Place in appropriate agent/tools/ directory**
2. **Use absolute imports only**
3. **Import utilities from core package**
4. **Add to tools/__init__.py for discoverability**
5. **Include test block for standalone execution**

Example tool structure:
```python
"""
New tool for agent functionality.
"""

import json
from typing import Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field

# Core utilities import
from core.time_utils import now, to_iso8601_z
from core.slack_utils import format_alert_blocks
from config.env_loader import get_required_env_var

class NewTool(BaseTool):
    """Tool description."""
    
    def run(self) -> str:
        # Implementation
        return json.dumps({"status": "success"})

if __name__ == "__main__":
    # Standalone test execution
    tool = NewTool()
    result = tool.run()
    print(result)
```

### Adding New Utilities

When adding shared utilities:

1. **Add to appropriate core/ module**
2. **Export from core/__init__.py**
3. **Include comprehensive docstrings**
4. **Add test coverage**
5. **Update this documentation**

## Testing Execution

### Run All Tests
```bash
cd /path/to/autopiloot
python -m unittest discover tests -v
```

### Run Specific Tests
```bash
python -m unittest tests.test_config -v
python -m unittest tests.test_time_utils -v
python -m unittest tests.test_slack_utils -v
```

### Test Individual Tools
```bash
# Each tool should support standalone execution
python -m scraper_agent.tools.save_video_metadata
python -m observability_agent.tools.alert_engine
```

## Production Deployment

### Environment Setup
```bash
# Set working directory
cd /path/to/autopiloot

# Set Python path
export PYTHONPATH=.

# Run agency
python -m agency
```

### Docker/Container Execution
```dockerfile
WORKDIR /app/autopiloot
ENV PYTHONPATH=.
CMD ["python", "-m", "agency"]
```

This modular execution pattern ensures:
- No relative import issues
- Consistent behavior across environments
- Easy testing and development
- Proper package structure
- Reliable production deployment