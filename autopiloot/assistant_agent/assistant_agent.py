"""
Assistant Agent for Autopiloot Agency
Handles notifications, monitoring, and user communication via Slack
"""

from agency_swarm import Agent, ModelSettings

assistant_agent = Agent(
    name="AssistantAgent", 
    description="Manages notifications, budget monitoring, and user communication via Slack. Provides operational oversight and error alerting for the agency.",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model="gpt-4o",
        temperature=0.1,  # Low temperature for precise operational communications
        max_completion_tokens=25000,
    ),
)