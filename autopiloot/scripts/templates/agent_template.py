"""
{agent_name_title} Agent - {description}

{description}
"""

from agency_swarm import Agent
from agency_swarm.tools import BaseTool
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class {agent_class_name}(Agent):
    """
    {agent_name_title} agent implementation for {description}.

    Responsibilities:
    {responsibilities}

    Tools:
    {tools_list}
    """

    def __init__(self):
        from agency_swarm import ModelSettings
        super().__init__(
            name="{agent_name_title}",
            description="{description}",
            instructions=Path(__file__).parent / "instructions.md",
            tools_folder=Path(__file__).parent / "tools",
            model_settings=ModelSettings(
                model="gpt-4o",
                temperature=0.2,
                max_completion_tokens=25000,
            ),
        )


# Export the agent instance
{agent_variable_name} = {agent_class_name}()

if __name__ == "__main__":
    # Test agent initialization
    print(f"{agent_name_title} agent initialized successfully")
    print(f"Description: {description}")
    print(f"Tools: {{{agent_variable_name}.get_available_tools()}}")