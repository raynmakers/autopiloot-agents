"""
Orchestrator Agent for Autopiloot Agency
CEO agent responsible for end-to-end pipeline coordination, policy enforcement, and cross-agent communication
"""

import os
import sys
from pathlib import Path
from agency_swarm import Agent, ModelSettings

# Add config directory to path for imports
config_dir = Path(__file__).parent.parent / "config"
# Import output guardrail for Agency Swarm v1.2.0
from core.guardrails import validate_orchestrator_output

try:
    from loader import get_config_value
    model = get_config_value("llm.default.model", default="gpt-4o")
    temperature = get_config_value("llm.default.temperature", default=0.2)
    max_tokens = get_config_value("llm.default.max_output_tokens", default=25000)
except Exception:
    # Fallback to default values if config loading fails
    model = "gpt-4o"
    temperature = 0.2
    max_tokens = 25000

orchestrator_agent = Agent(
    name="Orchestrator",
    description="CEO: End-to-end pipeline orchestration and policy enforcement. Coordinates workflows between Scraper, Transcriber, Summarizer, and Observability agents while enforcing budgets, quotas, and operational policies.",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model=model,
        temperature=temperature,
        max_completion_tokens=max_tokens,
    ),
    output_guardrails=validate_orchestrator_output,  # Agency Swarm v1.2.0 - validates JSON structure and required fields
)