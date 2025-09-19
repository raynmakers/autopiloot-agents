#!/usr/bin/env python3
"""
New Agent Scaffold CLI

Generate a complete agent structure with tools, tests, and documentation
from templates for the Autopiloot Agency modular architecture.

Usage:
    python scripts/new_agent.py --name "Content Analyzer" --description "Analyzes content for sentiment and topics" --tools "analyze_sentiment" "extract_topics" "generate_insights"

Example:
    python scripts/new_agent.py \
        --name "Content Analyzer" \
        --description "AI-powered content analysis and insights" \
        --tools "analyze_sentiment" "extract_topics" "generate_insights" \
        --environment-vars "CONTENT_API_KEY" "NLP_MODEL_URL"
"""

import argparse
import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Any


def to_snake_case(text: str) -> str:
    """Convert text to snake_case."""
    # Replace spaces and hyphens with underscores
    text = re.sub(r'[\s\-]+', '_', text)
    # Convert camelCase to snake_case
    text = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', text)
    # Convert to lowercase and remove extra underscores
    text = re.sub(r'_+', '_', text.lower())
    return text.strip('_')


def to_pascal_case(text: str) -> str:
    """Convert text to PascalCase."""
    words = re.split(r'[\s\-_]+', text)
    return ''.join(word.capitalize() for word in words if word)


def to_title_case(text: str) -> str:
    """Convert text to Title Case."""
    words = re.split(r'[\s\-_]+', text)
    return ' '.join(word.capitalize() for word in words if word)


def validate_agent_name(name: str) -> str:
    """Validate and normalize agent name."""
    if not name or not name.strip():
        raise ValueError("Agent name cannot be empty")

    # Check for invalid characters
    if re.search(r'[^\w\s\-]', name):
        raise ValueError("Agent name can only contain letters, numbers, spaces, and hyphens")

    return name.strip()


def validate_tool_names(tools: List[str]) -> List[str]:
    """Validate tool names follow snake_case convention."""
    validated_tools = []

    for tool in tools:
        if not tool or not tool.strip():
            continue

        # Convert to snake_case
        snake_tool = to_snake_case(tool.strip())

        # Validate snake_case format
        if not re.match(r'^[a-z][a-z0-9_]*[a-z0-9]$', snake_tool):
            print(f"Warning: Tool name '{tool}' converted to '{snake_tool}' for snake_case compliance")

        validated_tools.append(snake_tool)

    return validated_tools


def create_agent_directory(agent_name: str, base_dir: Path) -> Path:
    """Create agent directory structure."""
    agent_snake = to_snake_case(agent_name)
    agent_dir = base_dir / f"{agent_snake}_agent"

    # Create directories
    agent_dir.mkdir(exist_ok=True)
    (agent_dir / "tools").mkdir(exist_ok=True)

    return agent_dir


def load_template(template_name: str) -> str:
    """Load template content from templates directory."""
    template_path = Path(__file__).parent / "templates" / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template {template_name} not found at {template_path}")

    return template_path.read_text()


def generate_agent_variables(agent_name: str, description: str, tools: List[str], env_vars: List[str]) -> Dict[str, str]:
    """Generate template variables for agent creation."""
    agent_snake = to_snake_case(agent_name)
    agent_pascal = to_pascal_case(agent_name)
    agent_title = to_title_case(agent_name)

    # Generate tool-related content
    tools_list = "\\n".join(f"    - {tool}: {tool.replace('_', ' ').title()}" for tool in tools)
    tool_imports = "\\n".join(f"from {agent_snake}_agent.tools.{tool} import {to_pascal_case(tool)}" for tool in tools)
    test_imports = "\\n".join(f"from {agent_snake}_agent.tools.{tool} import {to_pascal_case(tool)}" for tool in tools)

    # Generate responsibilities
    responsibilities = f"""- {description}
    - Process requests and coordinate with other agents
    - Maintain audit logs and error handling
    - Integrate with shared configuration and environment"""

    # Generate environment variables
    env_vars_list = "\\n".join(f"- `{var}`: Description of {var.lower().replace('_', ' ')}" for var in env_vars)

    # Generate tool test methods
    tool_test_methods = ""
    for tool in tools:
        tool_pascal = to_pascal_case(tool)
        tool_test_methods += f"""
    def test_{tool}(self):
        \"\"\"Test {tool.replace('_', ' ')} functionality.\"\"\"
        tool = {tool_pascal}()
        # Add specific test logic for {tool}
        # result = tool.run()
        # self.assertIsNotNone(result)
        pass
"""

    return {
        'agent_name': agent_name,
        'agent_name_title': agent_title,
        'agent_class_name': f"{agent_pascal}Agent",
        'agent_variable_name': f"{agent_snake}_agent",
        'agent_file_name': f"{agent_snake}_agent",
        'agent_import_path': f"{agent_snake}_agent",
        'description': description,
        'responsibilities': responsibilities,
        'tools_list': tools_list,
        'tool_imports': tool_imports,
        'test_imports': test_imports,
        'tool_test_methods': tool_test_methods,
        'environment_vars': env_vars_list,
    }


def generate_tool_variables(agent_name: str, tool_name: str) -> Dict[str, str]:
    """Generate template variables for tool creation."""
    agent_title = to_title_case(agent_name)
    tool_pascal = to_pascal_case(tool_name)
    tool_title = tool_name.replace('_', ' ').title()

    return {
        'agent_name_title': agent_title,
        'tool_name': tool_name,
        'tool_class_name': tool_pascal,
        'tool_description': f"{tool_title} for {agent_title} agent",
        'tool_entity': tool_name.split('_')[0],  # First word as entity
        'tool_attributes': f"    - parameter: Description of parameter",
        'tool_parameters': f'parameter: str = Field(..., description="Required parameter for {tool_title}")',
        'tool_parameter_names': f'["parameter"]',
        'tool_test_parameters': f'parameter="test_value"',
    }


def create_agent_file(agent_dir: Path, variables: Dict[str, str]) -> None:
    """Create main agent file."""
    template = load_template("agent_template.py")
    content = template.format(**variables)

    agent_file = agent_dir / f"{variables['agent_file_name']}.py"
    agent_file.write_text(content)
    print(f"Created agent file: {agent_file}")


def create_instructions_file(agent_dir: Path, variables: Dict[str, str]) -> None:
    """Create agent instructions file."""
    template = load_template("instructions_template.md")
    content = template.format(**variables)

    instructions_file = agent_dir / "instructions.md"
    instructions_file.write_text(content)
    print(f"Created instructions file: {instructions_file}")


def create_init_file(agent_dir: Path, variables: Dict[str, str]) -> None:
    """Create __init__.py file."""
    template = load_template("init_template.py")
    content = template.format(**variables)

    init_file = agent_dir / "__init__.py"
    init_file.write_text(content)
    print(f"Created __init__.py file: {init_file}")


def create_tool_files(agent_dir: Path, agent_name: str, tools: List[str]) -> None:
    """Create tool files for the agent."""
    tools_dir = agent_dir / "tools"
    template = load_template("tool_template.py")

    for tool_name in tools:
        variables = generate_tool_variables(agent_name, tool_name)
        content = template.format(**variables)

        tool_file = tools_dir / f"{tool_name}.py"
        tool_file.write_text(content)
        print(f"Created tool file: {tool_file}")


def create_test_file(agent_dir: Path, variables: Dict[str, str]) -> None:
    """Create test file for the agent."""
    # Create tests directory in project root
    project_root = agent_dir.parent
    tests_dir = project_root / "tests"
    tests_dir.mkdir(exist_ok=True)

    template = load_template("test_template.py")
    content = template.format(**variables)

    test_file = tests_dir / f"test_{variables['agent_file_name']}.py"
    test_file.write_text(content)
    print(f"Created test file: {test_file}")


def create_chart_file(agent_dir: Path, agent_name: str, description: str) -> None:
    """Create Mermaid chart documentation."""
    agent_title = to_title_case(agent_name)
    docs_dir = agent_dir.parent / "docs" / "charts"
    docs_dir.mkdir(parents=True, exist_ok=True)

    chart_content = f"""## {agent_title} Agent — {description}

```mermaid
flowchart TD
  subgraph Config
    CFG[settings.yaml<br/>{to_snake_case(agent_name)}_agent.config]
  end

  subgraph {agent_title}Agent
    MAIN[{agent_title}Agent<br/>Main Agent Class]
    TOOL1[Tool 1<br/>Processing]
    TOOL2[Tool 2<br/>Analysis]
    TOOL3[Tool 3<br/>Storage]
  end

  subgraph Storage
    FS[(Firestore<br/>Audit Logs)]
    EXT[(External API<br/>Data Source)]
  end

  %% Configuration flow
  CFG --> MAIN

  %% Processing flow
  MAIN --> TOOL1
  TOOL1 --> TOOL2
  TOOL2 --> TOOL3

  %% Storage flow
  TOOL3 --> FS
  TOOL1 --> EXT

  %% Styling
  classDef agent fill:#e1f5fe,stroke:#0277bd,color:#01579b;
  classDef storage fill:#f3e5f5,stroke:#7b1fa2,color:#4a148c;
  classDef config fill:#e8f5e8,stroke:#388e3c,color:#1b5e20;

  class {agent_title}Agent agent;
  class FS,EXT storage;
  class CFG config;
```

### Key Features

- **{description}**
- **Audit Logging**: Comprehensive Firestore logging with performance metrics
- **Error Handling**: Graceful error handling with retry logic
- **Configuration**: Dynamic configuration from settings.yaml

### Integration Points

1. **Agency Communication**: Integrates with OrchestratorAgent and ObservabilityAgent
2. **Configuration**: Loads settings from centralized configuration system
3. **Audit Trail**: Logs all operations to Firestore audit_logs collection
4. **Error Reporting**: Routes errors to ObservabilityAgent for monitoring
"""

    chart_file = docs_dir / f"{to_snake_case(agent_name)}_agent.md"
    chart_file.write_text(chart_content)
    print(f"Created chart file: {chart_file}")


def update_settings_yaml(agent_name: str, tools: List[str]) -> None:
    """Add agent configuration section to settings.yaml."""
    project_root = Path(__file__).parent.parent
    settings_file = project_root / "config" / "settings.yaml"

    if not settings_file.exists():
        print(f"Warning: settings.yaml not found at {settings_file}")
        return

    agent_snake = to_snake_case(agent_name)
    agent_title = to_title_case(agent_name)

    # Read current settings
    current_content = settings_file.read_text()

    # Add agent to enabled_agents if not already present
    if f'- "{agent_snake}_agent"' not in current_content:
        # Find enabled_agents section and add new agent
        lines = current_content.split('\\n')
        for i, line in enumerate(lines):
            if 'enabled_agents:' in line:
                # Find the end of the enabled_agents list
                j = i + 1
                while j < len(lines) and (lines[j].startswith('  - ') or lines[j].strip() == ''):
                    j += 1
                # Insert new agent before the next section
                lines.insert(j - 1, f'  - "{agent_snake}_agent"  # {agent_title}: {agent_name}')
                break

        current_content = '\\n'.join(lines)

    # Add agent configuration section
    agent_config = f"""
{agent_snake}:
  enabled: true  # Enable/disable {agent_title} agent
  settings:
    # Agent-specific configuration
    max_retries: 3
    timeout_seconds: 300
  tools:
    # Tool-specific configuration
{chr(10).join(f'    {tool}:' + chr(10) + f'      enabled: true' for tool in tools)}
"""

    # Append configuration if not already present
    if f"{agent_snake}:" not in current_content:
        current_content += agent_config
        settings_file.write_text(current_content)
        print(f"Updated settings.yaml with {agent_snake} configuration")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate a new agent scaffold for Autopiloot Agency",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--name",
        required=True,
        help="Agent name (e.g., 'Content Analyzer')"
    )

    parser.add_argument(
        "--description",
        required=True,
        help="Agent description (e.g., 'AI-powered content analysis and insights')"
    )

    parser.add_argument(
        "--tools",
        nargs="+",
        required=True,
        help="List of tool names (e.g., 'analyze_sentiment' 'extract_topics')"
    )

    parser.add_argument(
        "--environment-vars",
        nargs="*",
        default=[],
        help="Required environment variables (e.g., 'API_KEY' 'MODEL_URL')"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Output directory (default: current directory)"
    )

    parser.add_argument(
        "--no-tests",
        action="store_true",
        help="Skip test file generation"
    )

    parser.add_argument(
        "--no-docs",
        action="store_true",
        help="Skip documentation generation"
    )

    args = parser.parse_args()

    try:
        # Validate inputs
        agent_name = validate_agent_name(args.name)
        tools = validate_tool_names(args.tools)

        if not tools:
            print("Error: At least one valid tool name is required")
            return 1

        # Generate template variables
        variables = generate_agent_variables(agent_name, args.description, tools, args.environment_vars)

        # Create agent directory
        agent_dir = create_agent_directory(agent_name, args.output_dir)

        print(f"Creating {to_title_case(agent_name)} agent in {agent_dir}")

        # Create all agent files
        create_agent_file(agent_dir, variables)
        create_instructions_file(agent_dir, variables)
        create_init_file(agent_dir, variables)
        create_tool_files(agent_dir, agent_name, tools)

        # Create optional files
        if not args.no_tests:
            create_test_file(agent_dir, variables)

        if not args.no_docs:
            create_chart_file(agent_dir, agent_name, args.description)

        # Update configuration
        try:
            update_settings_yaml(agent_name, tools)
        except Exception as e:
            print(f"Warning: Failed to update settings.yaml: {e}")

        print(f"\\n✅ {to_title_case(agent_name)} agent scaffold created successfully!")
        print(f"📁 Agent directory: {agent_dir}")
        print(f"🔧 Tools created: {', '.join(tools)}")
        print(f"\\n📋 Next steps:")
        print(f"1. Review and customize the generated files")
        print(f"2. Implement tool logic in {agent_dir}/tools/")
        print(f"3. Update {agent_dir}/instructions.md with specific workflows")
        print(f"4. Add {variables['agent_variable_name']} to agency.py enabled_agents")
        print(f"5. Run tests with: python -m unittest tests.test_{variables['agent_file_name']}")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())