"""
Configuration loading and environment variable management.

This module provides centralized configuration and environment variable access
for all agents in the Autopiloot system.

Key modules:
    - env_loader: Environment variable validation and access
    - loader: YAML configuration loading (settings.yaml)

Usage:
    from config.env_loader import get_required_env_var, get_optional_env_var
    from config.loader import load_app_config, get_config_value
"""
