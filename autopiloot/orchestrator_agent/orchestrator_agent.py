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
sys.path.append(str(config_dir))

# Import output guardrail for Agency Swarm v1.2.0
from core.guardrails import validate_orchestrator_output

try:
    from loader import load_app_config
    config = load_app_config()
    llm_config = config.get("llm", {}).get("default", {})
    model = llm_config.get("model", "gpt-4o")
    temperature = llm_config.get("temperature", 0.2)
    max_tokens = llm_config.get("max_output_tokens", 25000)
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