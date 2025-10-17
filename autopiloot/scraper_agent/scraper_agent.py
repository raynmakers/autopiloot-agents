"""
Scraper Agent for Autopiloot Agency
Handles YouTube content discovery and Google Sheets processing
"""

from agency_swarm import Agent, ModelSettings
from config.loader import get_config_value
from core.guardrails import validate_scraper_output

# Get agent-specific LLM configuration with fallback to default
model = get_config_value('llm.agents.scraper_agent.model',
                         default=get_config_value('llm.default.model', default='gpt-3.5-turbo'))
temperature = get_config_value('llm.agents.scraper_agent.temperature',
                               default=get_config_value('llm.default.temperature', default=0.3))
max_tokens = get_config_value('llm.agents.scraper_agent.max_output_tokens',
                              default=get_config_value('llm.default.max_output_tokens', default=4000))

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
    output_guardrails=[validate_scraper_output],  # Agency Swarm v1.2.0 - validates videos_discovered count
)