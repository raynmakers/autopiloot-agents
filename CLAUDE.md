# Claude Code Guidelines for Autopiloot Agency

## Core Principles from Cursor Rules

### Agency Swarm Framework (v1.0.0)
- Use Agency Swarm v1.0.0 patterns - **the latest version** 
- Official docs: <https://agency-swarm.ai>
- Source code: <https://github.com/VRSEN/agency-swarm>
- Examples: <https://github.com/VRSEN/agency-swarm/tree/main/examples>

### File Creation Rules
- **NEVER output code snippets in chat** - Always create/modify actual files
- Use appropriate file syntax: ```python:path/to/file.py
- Write full file content, not snippets or placeholders
- Include all necessary imports and dependencies
- Follow creation order: 1. tools, 2. agents, 3. agency, 4. requirements.txt

### Tool Development Standards

#### Tool Class Structure
```python
from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv

load_dotenv()  # always load environment variables

class MyTool(BaseTool):
    """
    Clear description of what the tool does.
    This docstring helps agents understand when to use this tool.
    """
    
    field_name: str = Field(
        ..., 
        description="Clear description for the agent"
    )
    
    def run(self):
        """Implementation with actual functional code."""
        # Get secrets from environment, never as tool inputs
        api_key = os.getenv("API_KEY")
        
        # Actual implementation - no placeholders
        return "Actual result string"

if __name__ == "__main__":
    tool = MyTool(field_name="test")
    print(tool.run())
```

#### Tool Best Practices
- **Use agency_swarm.tools.BaseTool** - not custom implementations
- **Environment secrets only** - Never API keys as tool inputs
- **Functional code only** - No mocks, placeholders, or hypothetical examples
- **Test blocks required** - Every tool must have `if __name__ == "__main__":` test
- **Python packages preferred** - Use SDKs over direct requests
- **Global constants** - Define constant values above the tool function

### Folder Structure Requirements

```
autopiloot/
├── ScraperAgent/
│   ├── __init__.py
│   ├── ScraperAgent.py
│   ├── instructions.md
│   └── tools/
│       ├── __init__.py
│       ├── ToolName.py  # Class name matches file name
├── TranscriberAgent/
├── SummarizerAgent/
├── AssistantAgent/
├── planning/
│   ├── prd.mdc
│   └── tasks/
├── tests/
├── agency.py
├── requirements.txt
└── .env
```

### Agent Creation
```python
from agency_swarm import Agent, ModelSettings

agent = Agent(
    name="AgentName",
    description="Brief role description",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model="gpt-4o",
        temperature=0.5,
        max_completion_tokens=25000,
    ),
)
```

### Agency Creation
```python
from agency_swarm import Agency
from dotenv import load_dotenv

load_dotenv()

agency = Agency(
    entry_agent,
    communication_flows=[
        (agent_a, agent_b),  # agent_a can initiate with agent_b
    ],
    shared_instructions="agency_manifesto.md",
)
```

### Task Template Requirements
- Use provided task template structure
- Information-dense keywords (exact file paths, function signatures)
- Self-contained scope - one task = one file
- Testable acceptance criteria
- Context plan with read-only dependencies
- Integration tests preferred over unit tests

### Testing Requirements
1. **Tool Testing**: Each tool must run standalone with test block
2. **Integration Testing**: Create comprehensive integration tests
3. **No Placeholder Tests**: Tests must call real APIs/services
4. **Coverage**: Test error conditions and edge cases

### Implementation Order
1. **PRD Creation** - Gather requirements and create planning/prd.mdc
2. **Task Breakdown** - Create individual task files in planning/tasks/
3. **Folder Structure** - Create agent folders and templates
4. **Tool Development** - Implement all tools with agency_swarm.tools.BaseTool
5. **Agent Creation** - Create agent classes and instructions
6. **Agency Assembly** - Wire agents together in agency.py
7. **Testing** - Test tools, agents, and full agency
8. **Iteration** - Repeat until user satisfaction

### Critical Requirements for This Project

#### Environment Configuration
- Use centralized `core/env_loader.py` for environment variable access
- Load configuration from `config/settings.yaml`
- Validate all environment variables and configuration on startup

#### Agency Swarm Integration
- **Must use agency_swarm.tools.BaseTool** for all tools
- **Must use Pydantic Field validation** for tool parameters
- **Must return strings directly** from tool run() methods (not Dict)
- **Must have working test blocks** in every tool file

#### API Integration Standards
- YouTube Data API v3: Use google-api-python-client
- AssemblyAI: Use official assemblyai SDK
- Google Drive/Sheets: Use google-api-python-client
- Slack: Use slack_sdk
- Firestore: Use firebase-admin SDK
- OpenAI: Use openai SDK

#### Error Handling
- Comprehensive error handling in all tools
- Dead Letter Queue (DLQ) for failed jobs after retries
- Quota management and graceful degradation
- Structured logging for operational monitoring

#### Security Requirements
- All API keys from environment variables only
- No secrets in code, logs, or tool parameters
- Firestore security rules enforce server-only access
- Service account authentication for Google services

## Quick Reference Commands

### Testing Tools
```bash
# Test individual tool
python autopiloot/agent_name/tools/ToolName.py

# Run integration tests
python -m unittest discover autopiloot/tests -v

# Test agency
python autopiloot/agency.py
```

### File Naming Conventions
- Tool files: `ToolName.py` (matches class name exactly)
- Agent files: `agent_name.py` (lowercase with underscores)
- Task files: `kebab-case.mdc` in planning/tasks/
- Test files: `test_module_name.py` in tests/

Remember: **Write actual, functional code immediately**. No placeholders, no hypothetical examples, no code snippets in chat responses.