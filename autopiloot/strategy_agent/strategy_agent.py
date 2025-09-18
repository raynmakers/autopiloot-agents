"""
Strategy Agent for Autopiloot Agency
Analyzes LinkedIn corpus to generate actionable content strategy and playbooks
"""

from agency_swarm import Agent, ModelSettings

strategy_agent = Agent(
    name="StrategyAgent",
    description="Analyzes LinkedIn corpus to identify high-engagement patterns, content strategies, and actionable insights for content optimization and audience growth.",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model="gpt-4o",
        temperature=0.3,  # Balanced for analytical creativity and consistency
        max_completion_tokens=25000,
    ),
)