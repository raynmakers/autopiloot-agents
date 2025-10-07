"""
Scraper Agent for Autopiloot Agency
Handles YouTube content discovery and Google Sheets processing
"""

from agency_swarm import Agent, ModelSettings
from config.loader import load_app_config

# Load configuration
config = load_app_config()

# Get agent-specific LLM configuration
agent_config = config.get('llm', {}).get('agents', {}).get('scraper_agent', {})
default_config = config.get('llm', {}).get('default', {})

# Use agent-specific config with fallback to default
model = agent_config.get('model', default_config.get('model', 'gpt-3.5-turbo'))
temperature = agent_config.get('temperature', default_config.get('temperature', 0.3))
max_tokens = agent_config.get('max_output_tokens', default_config.get('max_output_tokens', 4000))

scraper_agent = Agent(
    name="ScraperAgent",
    description="Discovers new videos from YouTube channels and processes Google Sheets backfill links. Handles deduplication, maintains backfill history, and enqueues transcription jobs for new content.",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model=model,
        temperature=temperature,
        max_completion_tokens=max_tokens,
    ),
)