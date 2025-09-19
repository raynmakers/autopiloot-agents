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
sys.path.append(str(config_dir))

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