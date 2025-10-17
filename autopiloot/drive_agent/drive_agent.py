"""
Google Drive Agent for Autopiloot Agency
Tracks configured Drive files/folders and indexes content into Zep GraphRAG
"""

import os
import sys
from pathlib import Path
from agency_swarm import Agent, ModelSettings

# Add config directory to path for imports
config_dir = Path(__file__).parent.parent / "config"
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

drive_agent = Agent(
    name="DriveAgent",
    description="Tracks configured Google Drive files and folders recursively, indexes new/updated content into Zep GraphRAG for knowledge retrieval.",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model=model,
        temperature=temperature,
        max_completion_tokens=max_tokens,
    ),
)