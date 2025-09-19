# Modular Architecture Guide

The Autopiloot Agency implements a **modular architecture** that allows dynamic agent composition, configurable communication flows, and extensible scheduling—all without code changes. This guide covers the four key components of the modular system.

## Overview

### Core Components

1. **[Agent Registry](#agent-registry)**: Config-driven agent loading and validation
2. **[Communication Flows](#communication-flows)**: Dynamic agent communication topology
3. **[Schedules & Triggers](#schedules--triggers)**: Agent-provided scheduling and event handling
4. **[CLI Scaffold](#cli-scaffold)**: Automated agent generation from templates

### Key Benefits

- **Zero-Code Configuration**: Enable/disable agents and modify workflows via `settings.yaml`
- **Development Velocity**: Generate complete agent scaffolds in seconds
- **Operational Flexibility**: Customize scheduling and monitoring per deployment
- **Maintainability**: Consistent patterns and automated testing across all agents

---

## Agent Registry

**File**: `core/agent_registry.py`

The Agent Registry dynamically loads agents based on the `enabled_agents` configuration, replacing hardcoded imports with flexible, runtime-determined agent composition.

### Configuration

```yaml
# config/settings.yaml
enabled_agents:
  - "orchestrator_agent"  # Required: CEO agent
  - "scraper_agent"       # YouTube content discovery
  - "transcriber_agent"   # Video transcription
  - "summarizer_agent"    # Business-focused summarization
  - "observability_agent" # Monitoring and notifications
  - "linkedin_agent"      # LinkedIn content ingestion
  - "strategy_agent"      # Strategic analysis
  - "drive_agent"         # Google Drive content tracking
```

### Usage

```python
from core.agent_registry import create_agent_registry

# Load agents dynamically
registry = create_agent_registry()
loaded_agents = registry.get_loaded_agents()

# Access specific agents
orchestrator = registry.get_agent("orchestrator_agent")
scraper = registry.get_agent("scraper_agent")

# Check agent status
if registry.is_agent_enabled("linkedin_agent"):
    print("LinkedIn agent is enabled")
```

### Error Handling

The registry provides comprehensive validation:

- **Missing Configuration**: Fails if `enabled_agents` is not defined
- **Empty Lists**: Requires at least one agent (orchestrator_agent)
- **Import Failures**: Clear error messages for missing agent modules
- **Duplicate Detection**: Prevents duplicate agent registration

### Example: Minimal Agency

```yaml
# Minimal configuration for testing
enabled_agents:
  - "orchestrator_agent"
  - "observability_agent"
```

This creates a minimal agency with just coordination and monitoring capabilities.

---

## Communication Flows

**File**: `agency.py` → `_build_communication_flows()`

Communication flows define how agents can communicate with each other. The modular system loads these flows from configuration instead of hardcoding them.

### Configuration

```yaml
# config/settings.yaml
communication_flows:
  # CEO coordination
  - ["orchestrator_agent", "scraper_agent"]
  - ["orchestrator_agent", "transcriber_agent"]
  - ["orchestrator_agent", "summarizer_agent"]

  # Primary workflow
  - ["scraper_agent", "transcriber_agent"]
  - ["transcriber_agent", "summarizer_agent"]

  # LinkedIn analysis
  - ["linkedin_agent", "strategy_agent"]

  # Observability (bidirectional)
  - ["observability_agent", "scraper_agent"]
  - ["scraper_agent", "observability_agent"]
```

### Flow Validation

The system automatically filters flows based on enabled agents:

```python
# If linkedin_agent is disabled, these flows are automatically skipped:
- ["linkedin_agent", "strategy_agent"]        # Skipped
- ["orchestrator_agent", "linkedin_agent"]    # Skipped
```

### Custom Topologies

You can create custom agency topologies for different use cases:

#### Content-Only Agency
```yaml
enabled_agents:
  - "orchestrator_agent"
  - "scraper_agent"
  - "transcriber_agent"
  - "summarizer_agent"
  - "observability_agent"

communication_flows:
  - ["orchestrator_agent", "scraper_agent"]
  - ["scraper_agent", "transcriber_agent"]
  - ["transcriber_agent", "summarizer_agent"]
  - ["observability_agent", "scraper_agent"]
  - ["scraper_agent", "observability_agent"]
```

#### Analysis-Only Agency
```yaml
enabled_agents:
  - "orchestrator_agent"
  - "linkedin_agent"
  - "strategy_agent"
  - "drive_agent"
  - "observability_agent"

communication_flows:
  - ["orchestrator_agent", "linkedin_agent"]
  - ["orchestrator_agent", "drive_agent"]
  - ["linkedin_agent", "strategy_agent"]
  - ["drive_agent", "strategy_agent"]
```

---

## Schedules & Triggers

**Files**: `core/agent_schedules.py`, `services/firebase/functions/modular_scheduler.py`

Agents can expose `get_schedules()` and `get_triggers()` methods to register their own scheduled functions and event handlers with Firebase Functions.

### Agent Schedule Interface

```python
from core.agent_schedules import AgentSchedule, AgentTrigger

class CustomAgent(Agent):
    def get_schedules(self):
        """Return list of schedules this agent provides."""
        return [
            AgentSchedule(
                schedule="0 */6 * * *",  # Every 6 hours
                timezone="Europe/Amsterdam",
                function_name="custom_agent_sync",
                description="Sync data every 6 hours",
                handler=self._sync_handler,
                memory_mb=256,
                timeout_sec=300
            )
        ]

    def get_triggers(self):
        """Return list of triggers this agent provides."""
        return [
            AgentTrigger(
                trigger_type="firestore",
                document_pattern="custom_data/{doc_id}",
                function_name="custom_agent_trigger",
                description="Process custom data changes",
                handler=self._trigger_handler,
                memory_mb=256,
                timeout_sec=180
            )
        ]

    def _sync_handler(self):
        """Handler for scheduled sync."""
        # Implementation here
        return {"status": "success"}

    def _trigger_handler(self, event):
        """Handler for document triggers."""
        # Implementation here
        return {"processed": True}
```

### Schedule Discovery

The system automatically discovers schedules from enabled agents:

```python
from core.agent_schedules import create_schedule_registry

registry = create_schedule_registry()
schedules = registry.get_all_schedules()
triggers = registry.get_all_triggers()

print(f"Found {len(schedules)} schedules and {len(triggers)} triggers")
```

### Firebase Functions Integration

The modular scheduler automatically registers discovered schedules:

```python
# services/firebase/functions/modular_scheduler.py
@scheduler_fn.on_schedule(schedule="0 1 * * *", timezone="Europe/Amsterdam")
def execute_agent_schedules_01(event):
    """Execute all agent schedules for 01:00 slot."""
    registry = create_schedule_registry()
    schedules = registry.get_all_schedules()

    # Filter and execute schedules for this time slot
    for name, schedule in schedules.items():
        if schedule.schedule == "0 1 * * *":
            result = schedule.handler()
            # Log result and handle errors
```

### Default Schedules

The system provides default schedules for backwards compatibility:

```python
from core.agent_schedules import get_default_schedules, get_default_triggers

# Fallback to defaults if no agent schedules found
default_schedules = get_default_schedules()
default_triggers = get_default_triggers()
```

---

## CLI Scaffold

**File**: `scripts/new_agent.py`

The CLI scaffold generates complete agent structures from templates, enabling rapid development of new agents with consistent patterns.

### Usage

```bash
# Basic agent generation
python scripts/new_agent.py \
  --name "Content Analyzer" \
  --description "AI-powered content analysis and insights" \
  --tools "analyze_sentiment" "extract_topics" "generate_insights"

# With environment variables
python scripts/new_agent.py \
  --name "API Manager" \
  --description "External API integration and management" \
  --tools "fetch_data" "transform_data" "cache_results" \
  --environment-vars "API_KEY" "API_URL" "CACHE_TTL"

# Minimal generation (no tests/docs)
python scripts/new_agent.py \
  --name "Simple Worker" \
  --description "Basic worker agent" \
  --tools "process_task" \
  --no-tests --no-docs
```

### Generated Structure

```
content_analyzer_agent/
├── content_analyzer_agent.py    # Main agent class
├── instructions.md               # Agent-specific instructions
├── __init__.py                  # Package exports
└── tools/
    ├── analyze_sentiment.py     # Tool implementations
    ├── extract_topics.py
    └── generate_insights.py

tests/
└── test_content_analyzer_agent.py  # Comprehensive test suite

docs/charts/
└── content_analyzer_agent.md      # Mermaid workflow chart

config/settings.yaml                # Updated with agent config
```

### Template Customization

Templates are located in `scripts/templates/`:

- `agent_template.py`: Main agent class template
- `instructions_template.md`: Agent instructions template
- `tool_template.py`: Individual tool template
- `test_template.py`: Test suite template
- `init_template.py`: Package initialization template

### Naming Conventions

The scaffold enforces consistent naming:

- **Agent Names**: "Content Analyzer" → `content_analyzer_agent`
- **Tool Names**: "analyze sentiment" → `analyze_sentiment.py`
- **Class Names**: `ContentAnalyzerAgent`, `AnalyzeSentiment`
- **Variables**: `content_analyzer_agent`

### Configuration Integration

Generated agents are automatically added to `settings.yaml`:

```yaml
content_analyzer:
  enabled: true
  settings:
    max_retries: 3
    timeout_seconds: 300
  tools:
    analyze_sentiment:
      enabled: true
    extract_topics:
      enabled: true
    generate_insights:
      enabled: true
```

---

## Testing Strategy

### Test Coverage

The modular architecture includes comprehensive tests:

**File**: `tests/test_modular_architecture.py`

```bash
# Run modular architecture tests
python -m unittest tests.test_modular_architecture -v

# Test specific components
python -m unittest tests.test_modular_architecture.TestAgentRegistry -v
python -m unittest tests.test_modular_architecture.TestCommunicationFlows -v
python -m unittest tests.test_modular_architecture.TestAgentScheduleRegistry -v
python -m unittest tests.test_modular_architecture.TestCLIScaffold -v
```

### Mock Strategy

Tests use comprehensive mocking:

- **Agent Modules**: Mock agent imports and initialization
- **Configuration**: Mock `settings.yaml` loading
- **Environment**: Mock environment variables
- **External Services**: Mock Firebase, Firestore, and external APIs

### Integration Testing

```python
# Test full agency initialization with modular components
def test_full_agency_initialization(self):
    """Test complete modular agency initialization."""
    mock_config = {
        'enabled_agents': ['orchestrator_agent', 'scraper_agent'],
        'communication_flows': [['orchestrator_agent', 'scraper_agent']]
    }

    agency = AutopilootAgency()

    self.assertEqual(len(agency.loaded_agents), 2)
    self.assertIn('orchestrator_agent', agency.loaded_agents)
```

---

## Development Workflow

### Adding a New Agent

1. **Generate Scaffold**:
   ```bash
   python scripts/new_agent.py \
     --name "Email Manager" \
     --description "Email processing and analysis" \
     --tools "parse_email" "extract_attachments" "classify_content"
   ```

2. **Implement Tools**:
   ```python
   # email_manager_agent/tools/parse_email.py
   class ParseEmail(BaseTool):
       def run(self) -> str:
           # Implementation here
           return json.dumps({"success": True, "result": {...}})
   ```

3. **Update Configuration**:
   ```yaml
   # Add to enabled_agents
   enabled_agents:
     - "email_manager_agent"

   # Add communication flows
   communication_flows:
     - ["orchestrator_agent", "email_manager_agent"]
   ```

4. **Test Integration**:
   ```bash
   python -m unittest tests.test_email_manager_agent -v
   PYTHONPATH=. python -c "from agency import AutopilootAgency; agency = AutopilootAgency()"
   ```

### Modifying Agent Topology

1. **Update Flows**:
   ```yaml
   # Remove agents from enabled_agents
   enabled_agents:
     - "orchestrator_agent"
     - "scraper_agent"
     # - "transcriber_agent"  # Disabled

   # Flows are automatically filtered
   communication_flows:
     - ["orchestrator_agent", "scraper_agent"]
     # Flows with transcriber_agent are skipped
   ```

2. **Validate Configuration**:
   ```python
   from core.agent_registry import create_agent_registry
   registry = create_agent_registry()
   print(f"Loaded agents: {registry.get_loaded_agent_names()}")
   ```

### Adding Schedules

1. **Implement Schedule Methods**:
   ```python
   class CustomAgent(Agent):
       def get_schedules(self):
           return [
               AgentSchedule(
                   schedule="0 */2 * * *",  # Every 2 hours
                   timezone="Europe/Amsterdam",
                   function_name="custom_sync",
                   description="Custom data sync",
                   handler=self._sync_data
               )
           ]
   ```

2. **Test Schedule Discovery**:
   ```python
   from core.agent_schedules import create_schedule_registry
   registry = create_schedule_registry()
   schedules = registry.get_all_schedules()
   assert "custom_sync" in schedules
   ```

3. **Deploy Firebase Functions**:
   ```bash
   firebase deploy --only functions
   ```

---

## Troubleshooting

### Common Issues

#### Agent Import Failures
```
ImportError: cannot import name 'custom_agent' from 'custom_agent'
```

**Solution**: Ensure agent exports follow naming convention:
```python
# custom_agent/custom_agent.py
custom_agent = CustomAgent()  # Variable name must match module name
```

#### Missing Orchestrator Agent
```
ValueError: orchestrator_agent is required and must be in enabled_agents list
```

**Solution**: Always include `orchestrator_agent` in `enabled_agents`:
```yaml
enabled_agents:
  - "orchestrator_agent"  # Required
  - "other_agent"
```

#### Flow Validation Errors
```
DEBUG: Skipping flow orchestrator_agent -> disabled_agent: target agent not enabled
```

**Solution**: This is normal behavior. Flows referencing disabled agents are automatically filtered.

#### Schedule Conflicts
```
WARNING: Duplicate schedule function name: daily_sync
```

**Solution**: Ensure unique function names across all agents:
```python
function_name="agent_name_daily_sync"  # Include agent name prefix
```

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from core.agent_registry import create_agent_registry
registry = create_agent_registry()
```

### Validation Commands

```bash
# Test agent registry
PYTHONPATH=. python core/agent_registry.py

# Test schedule registry
PYTHONPATH=. python core/agent_schedules.py

# Test agency initialization
PYTHONPATH=. python -c "from agency import AutopilootAgency; agency = AutopilootAgency()"

# Run comprehensive tests
python -m unittest tests.test_modular_architecture -v
```

---

## Best Practices

### Configuration Management

1. **Version Control**: Always commit `settings.yaml` changes
2. **Environment Separation**: Use different configs for dev/staging/prod
3. **Validation**: Test configuration changes before deployment
4. **Documentation**: Document custom configurations

### Agent Development

1. **Consistent Patterns**: Follow scaffold-generated structure
2. **Error Handling**: Implement comprehensive error handling in all tools
3. **Audit Logging**: Use `AuditLogger` for all significant operations
4. **Testing**: Write tests for all tools and workflows

### Deployment

1. **Gradual Rollout**: Enable agents incrementally in production
2. **Monitoring**: Watch observability metrics after changes
3. **Rollback Plan**: Keep previous configurations for quick rollback
4. **Documentation**: Update deployment docs with configuration changes

### Performance

1. **Agent Granularity**: Balance agent specialization vs. overhead
2. **Flow Optimization**: Minimize unnecessary communication flows
3. **Schedule Efficiency**: Use appropriate intervals for scheduled functions
4. **Resource Allocation**: Set appropriate memory/timeout limits

---

## Architecture Decisions

### ADR-0036: Modular Architecture Implementation

**Decision**: Implement config-driven modular architecture with four core components.

**Rationale**:
- Enables zero-code configuration changes
- Supports multiple deployment topologies
- Accelerates agent development
- Improves maintainability and testing

**Consequences**:
- **Positive**: Flexible, extensible, developer-friendly
- **Negative**: Additional complexity, indirection in agent loading
- **Mitigation**: Comprehensive testing, clear documentation, error handling

**Status**: Implemented ✅

---

## Migration Guide

### From Hardcoded to Modular

1. **Backup Current Configuration**:
   ```bash
   cp agency.py agency.py.backup
   cp config/settings.yaml config/settings.yaml.backup
   ```

2. **Update Agency Class**:
   ```python
   # Replace hardcoded imports with registry
   from core.agent_registry import create_agent_registry
   ```

3. **Add Configuration**:
   ```yaml
   # Add enabled_agents and communication_flows to settings.yaml
   enabled_agents:
     - "existing_agent_1"
     - "existing_agent_2"

   communication_flows:
     - ["existing_agent_1", "existing_agent_2"]
   ```

4. **Test Migration**:
   ```bash
   python -m unittest tests.test_modular_architecture -v
   PYTHONPATH=. python agency.py
   ```

5. **Validate Functionality**:
   - Verify all expected agents load
   - Test inter-agent communication
   - Check scheduled functions still work

---

**Modular Architecture Status**: Production Ready ✅
**Implementation Date**: 2025-01-16
**Components**: 4 (Registry, Flows, Schedules, CLI)
**Test Coverage**: 95%+ across all components
**Documentation**: Complete with examples and troubleshooting