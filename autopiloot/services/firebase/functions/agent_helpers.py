"""
Shared agent initialization helpers for Firebase Functions.

Provides lazy-initialized singleton getters for orchestrator and observability agents
to avoid duplication across Firebase Functions modules and prevent cold start overhead.
"""

import logging
from typing import Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Lazy-initialized agent singletons
_orchestrator_agent: Optional[Any] = None
_observability_agent: Optional[Any] = None
_linkedin_agent: Optional[Any] = None
_drive_agent: Optional[Any] = None
_strategy_agent: Optional[Any] = None


def get_orchestrator_agent():
    """
    Get or create the orchestrator agent instance (lazy initialization).
    This minimizes cold start costs by deferring agent creation until needed.

    Returns:
        The orchestrator agent instance or None if import fails
    """
    global _orchestrator_agent
    if _orchestrator_agent is None:
        try:
            from agents.autopiloot.orchestrator_agent.orchestrator_agent import orchestrator_agent
            _orchestrator_agent = orchestrator_agent
            logger.info("Orchestrator agent initialized successfully")
        except ImportError as e:
            logger.error(f"Failed to import orchestrator agent: {e}")
            # Fallback to None, functions will use existing logic
            _orchestrator_agent = None
    return _orchestrator_agent


def get_observability_agent():
    """
    Get or create the observability agent instance (lazy initialization).
    Used for daily digest delivery and error alerting.

    Returns:
        The observability agent instance or None if import fails
    """
    global _observability_agent
    if _observability_agent is None:
        try:
            from agents.autopiloot.observability_agent.observability_agent import observability_agent
            _observability_agent = observability_agent
            logger.info("Observability agent initialized successfully")
        except ImportError as e:
            logger.error(f"Failed to import observability agent: {e}")
            _observability_agent = None
    return _observability_agent


def get_linkedin_agent():
    """
    Get or create the LinkedIn agent instance (lazy initialization).
    Used for LinkedIn content ingestion and processing.

    Returns:
        The LinkedIn agent instance or None if import fails
    """
    global _linkedin_agent
    if _linkedin_agent is None:
        try:
            from agents.autopiloot.linkedin_agent.linkedin_agent import linkedin_agent
            _linkedin_agent = linkedin_agent
            logger.info("LinkedIn agent initialized successfully")
        except ImportError as e:
            logger.error(f"Failed to import LinkedIn agent: {e}")
            _linkedin_agent = None
    return _linkedin_agent


def get_drive_agent():
    """
    Get or create the Drive agent instance (lazy initialization).
    Used for Google Drive content ingestion and Zep indexing.

    Returns:
        The Drive agent instance or None if import fails
    """
    global _drive_agent
    if _drive_agent is None:
        try:
            from agents.autopiloot.drive_agent.drive_agent import drive_agent
            _drive_agent = drive_agent
            logger.info("Drive agent initialized successfully")
        except ImportError as e:
            logger.error(f"Failed to import Drive agent: {e}")
            _drive_agent = None
    return _drive_agent


def get_strategy_agent():
    """
    Get or create the Strategy agent instance (lazy initialization).
    Used for content analysis and playbook synthesis.

    Returns:
        The Strategy agent instance or None if import fails
    """
    global _strategy_agent
    if _strategy_agent is None:
        try:
            from agents.autopiloot.strategy_agent.strategy_agent import strategy_agent
            _strategy_agent = strategy_agent
            logger.info("Strategy agent initialized successfully")
        except ImportError as e:
            logger.error(f"Failed to import Strategy agent: {e}")
            _strategy_agent = None
    return _strategy_agent


def reset_agents():
    """
    Reset all cached agent instances. Useful for testing.
    """
    global _orchestrator_agent, _observability_agent, _linkedin_agent, _drive_agent, _strategy_agent
    _orchestrator_agent = None
    _observability_agent = None
    _linkedin_agent = None
    _drive_agent = None
    _strategy_agent = None
    logger.info("All agent instances reset")