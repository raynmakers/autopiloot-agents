"""
Observability Agent for Autopiloot Agency
Monitors budgets, sends alerts, and provides operational oversight via Slack
"""

from agency_swarm import Agent

observability_agent = Agent(
    name="ObservabilityAgent", 
    description="Monitors budgets, sends alerts, and provides operational oversight via Slack.",
    instructions="./instructions.md",
    tools_folder="./tools",
)

