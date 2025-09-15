"""
Observability Agent for Autopiloot Agency
Monitors budgets, sends alerts, and provides operational oversight via Slack
"""

from agency_swarm import Agent, ModelSettings

observability_agent = Agent(
    name="ObservabilityAgent", 
    description="Monitors budgets, sends alerts, and provides operational oversight via Slack.",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model="gpt-4o",
        temperature=0.1,  # Low temperature for precise operational communications
        max_completion_tokens=25000,
    ),
)

