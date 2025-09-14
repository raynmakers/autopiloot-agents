"""
Configuration loader for Autopiloot agents.
Loads and validates settings from settings.yaml.
"""

import os
import yaml
from typing import TypedDict, List, Dict, Optional, Union, Literal
from pathlib import Path

# Define VideoStatus locally to avoid circular imports
VideoStatus = Literal["discovered", "transcribed", "summarized"]


class ScraperConfig(TypedDict, total=False):
    handles: List[str]
    daily_limit_per_channel: int


class LLMPrompts(TypedDict, total=False):
    summarizer_short_id: str


class LLMTaskConfig(TypedDict, total=False):
    model: str
    temperature: float
    prompt_id: Optional[str]


class LLMConfig(TypedDict, total=False):
    default: LLMTaskConfig
    prompts: LLMPrompts
    tasks: Dict[str, LLMTaskConfig]


class NotificationsSlackConfig(TypedDict, total=False):
    channel: str


class BudgetsConfig(TypedDict, total=False):
    transcription_daily_usd: float


class SheetsConfig(TypedDict, total=False):
    daily_limit_per_channel: int
    range_a1: str


class ReliabilityRetryConfig(TypedDict, total=False):
    max_attempts: int
    base_delay_sec: int


class ReliabilityQuotasConfig(TypedDict, total=False):
    youtube_daily_limit: int
    assemblyai_daily_limit: int


class ReliabilityConfig(TypedDict, total=False):
    retry: ReliabilityRetryConfig
    quotas: ReliabilityQuotasConfig


class AppConfig(TypedDict, total=False):
    sheet: str
    scraper: ScraperConfig
    sheets: SheetsConfig
    llm: LLMConfig
    notifications: Dict[str, NotificationsSlackConfig]
    budgets: BudgetsConfig
    idempotency: Dict[str, Union[int, List[str], str]]
    reliability: ReliabilityConfig


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


def _validate_config(config: dict) -> None:
    """
    Validate configuration values according to task requirements.
    
    Raises:
        ConfigValidationError: If validation fails
    """
    
    # Validate sheet ID
    if not config.get("sheet") or not isinstance(config["sheet"], str) or not config["sheet"].strip():
        raise ConfigValidationError("sheet must be a non-empty string (Google Sheet ID)")
    
    # Validate scraper config
    scraper = config.get("scraper", {})
    if "daily_limit_per_channel" in scraper:
        daily_limit = scraper["daily_limit_per_channel"]
        if not isinstance(daily_limit, int) or daily_limit < 0:
            raise ConfigValidationError("scraper.daily_limit_per_channel must be int >= 0")
    
    # Validate LLM config
    llm = config.get("llm", {})
    if "default" in llm:
        default_config = llm["default"]
        
        # Validate default model
        if not default_config.get("model") or not isinstance(default_config["model"], str) or not default_config["model"].strip():
            raise ConfigValidationError("llm.default.model must be a non-empty string")
        
        # Validate default temperature
        if "temperature" in default_config:
            temp = default_config["temperature"]
            if not isinstance(temp, (int, float)) or temp < 0.0 or temp > 1.0:
                raise ConfigValidationError("llm.default.temperature must be between 0.0 and 1.0")
    
    # Validate LLM task configs
    if "tasks" in llm:
        for task_name, task_config in llm["tasks"].items():
            if not isinstance(task_config, dict):
                raise ConfigValidationError(f"llm.tasks.{task_name} must be a dict")
            
            # Validate task model
            if "model" in task_config:
                if not isinstance(task_config["model"], str) or not task_config["model"].strip():
                    raise ConfigValidationError(f"llm.tasks.{task_name}.model must be a non-empty string")
            
            # Validate task temperature
            if "temperature" in task_config:
                temp = task_config["temperature"]
                if not isinstance(temp, (int, float)) or temp < 0.0 or temp > 1.0:
                    raise ConfigValidationError(f"llm.tasks.{task_name}.temperature must be between 0.0 and 1.0")
    
    # Validate notifications
    notifications = config.get("notifications", {})
    if "slack" in notifications:
        slack_config = notifications["slack"]
        if not slack_config.get("channel") or not isinstance(slack_config["channel"], str) or not slack_config["channel"].strip():
            raise ConfigValidationError("notifications.slack.channel must be a non-empty string")
    
    # Validate budgets
    budgets = config.get("budgets", {})
    if "transcription_daily_usd" in budgets:
        budget = budgets["transcription_daily_usd"]
        if not isinstance(budget, (int, float)) or budget <= 0:
            raise ConfigValidationError("budgets.transcription_daily_usd must be a positive number")
    
    # Validate sheets config
    sheets = config.get("sheets", {})
    if "daily_limit_per_channel" in sheets:
        daily_limit = sheets["daily_limit_per_channel"]
        if not isinstance(daily_limit, int) or daily_limit <= 0:
            raise ConfigValidationError("sheets.daily_limit_per_channel must be a positive integer")
    
    if "range_a1" in sheets:
        range_a1 = sheets["range_a1"]
        if not isinstance(range_a1, str) or not range_a1.strip():
            raise ConfigValidationError("sheets.range_a1 must be a non-empty string")
    
    # Validate idempotency config
    idempotency = config.get("idempotency", {})
    if "max_video_duration_sec" in idempotency:
        max_duration = idempotency["max_video_duration_sec"]
        if not isinstance(max_duration, int) or max_duration <= 0:
            raise ConfigValidationError("idempotency.max_video_duration_sec must be a positive integer")
    
    if "status_progression" in idempotency:
        status_progression = idempotency["status_progression"]
        if not isinstance(status_progression, list):
            raise ConfigValidationError("idempotency.status_progression must be a list")
        
        valid_statuses = ["discovered", "transcribed", "summarized"]
        for status in status_progression:
            if status not in valid_statuses:
                raise ConfigValidationError(f"idempotency.status_progression contains invalid status: {status}")
    
    if "drive_naming_format" in idempotency:
        naming_format = idempotency["drive_naming_format"]
        if not isinstance(naming_format, str) or not naming_format.strip():
            raise ConfigValidationError("idempotency.drive_naming_format must be a non-empty string")
    
    # Validate reliability config
    reliability = config.get("reliability", {})
    if "retry" in reliability:
        retry_config = reliability["retry"]
        if "max_attempts" in retry_config:
            max_attempts = retry_config["max_attempts"]
            if not isinstance(max_attempts, int) or max_attempts < 0:
                raise ConfigValidationError("reliability.retry.max_attempts must be a non-negative integer")
        
        if "base_delay_sec" in retry_config:
            base_delay = retry_config["base_delay_sec"]
            if not isinstance(base_delay, int) or base_delay <= 0:
                raise ConfigValidationError("reliability.retry.base_delay_sec must be a positive integer")
    
    if "quotas" in reliability:
        quotas_config = reliability["quotas"]
        for quota_key in ["youtube_daily_limit", "assemblyai_daily_limit"]:
            if quota_key in quotas_config:
                quota_value = quotas_config[quota_key]
                if not isinstance(quota_value, int) or quota_value <= 0:
                    raise ConfigValidationError(f"reliability.quotas.{quota_key} must be a positive integer")


def load_app_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Load and validate application configuration from settings.yaml.
    
    Args:
        config_path: Optional path to config file. If None, uses default location.
        
    Returns:
        Validated configuration dictionary
        
    Raises:
        ConfigValidationError: If configuration is invalid
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    
    if config_path is None:
        # Default to settings.yaml in the same directory as this file
        config_dir = Path(__file__).parent
        config_path = config_dir / "settings.yaml"
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Failed to parse YAML configuration: {e}")
    
    if not isinstance(config, dict):
        raise ConfigValidationError("Configuration must be a YAML dictionary")
    
    # Validate the configuration
    _validate_config(config)
    
    return config


def get_max_video_duration(config: AppConfig) -> int:
    """
    Get maximum video duration for processing from config.
    
    Args:
        config: Application configuration
        
    Returns:
        Maximum duration in seconds (default: 4200 = 70 minutes)
    """
    return config.get("idempotency", {}).get("max_video_duration_sec", 4200)


def get_drive_naming_format(config: AppConfig) -> str:
    """
    Get Drive filename format string from config.
    
    Args:
        config: Application configuration
        
    Returns:
        Format string (default: "{video_id}_{date}_{type}.{ext}")
    """
    return config.get("idempotency", {}).get("drive_naming_format", "{video_id}_{date}_{type}.{ext}")


def get_status_progression(config: AppConfig) -> List[str]:
    """
    Get expected status progression from config.
    
    Args:
        config: Application configuration
        
    Returns:
        List of status values in progression order
    """
    return config.get("idempotency", {}).get("status_progression", ["discovered", "transcribed", "summarized"])


def get_sheets_daily_limit(config: AppConfig) -> int:
    """
    Get daily limit for sheet processing from config.
    
    Args:
        config: Application configuration
        
    Returns:
        Daily limit for sheet processing (default: 10)
    """
    return config.get("sheets", {}).get("daily_limit_per_channel", 10)


def get_sheets_range(config: AppConfig) -> str:
    """
    Get sheet range for reading data from config.
    
    Args:
        config: Application configuration
        
    Returns:
        A1 notation range for sheet data (default: "Sheet1!A:D")
    """
    return config.get("sheets", {}).get("range_a1", "Sheet1!A:D")


def get_retry_max_attempts(config: AppConfig) -> int:
    """
    Get maximum retry attempts from config.
    
    Args:
        config: Application configuration
        
    Returns:
        Maximum retry attempts (default: 3)
    """
    return config.get("reliability", {}).get("retry", {}).get("max_attempts", 3)


def get_retry_base_delay(config: AppConfig) -> int:
    """
    Get base delay for exponential backoff from config.
    
    Args:
        config: Application configuration
        
    Returns:
        Base delay in seconds (default: 60)
    """
    return config.get("reliability", {}).get("retry", {}).get("base_delay_sec", 60)


def get_youtube_daily_limit(config: AppConfig) -> int:
    """
    Get YouTube API daily quota limit from config.
    
    Args:
        config: Application configuration
        
    Returns:
        YouTube API daily quota limit (default: 10000)
    """
    return config.get("reliability", {}).get("quotas", {}).get("youtube_daily_limit", 10000)


def get_assemblyai_daily_limit(config: AppConfig) -> int:
    """
    Get AssemblyAI daily limit from config.
    
    Args:
        config: Application configuration
        
    Returns:
        AssemblyAI daily limit (default: 100)
    """
    return config.get("reliability", {}).get("quotas", {}).get("assemblyai_daily_limit", 100)


if __name__ == "__main__":
    config = load_app_config()
    print(f"Configuration loaded successfully. Sheet ID: {config['sheet']}")
    print(f"Default LLM model: {config['llm']['default']['model']}")
    print(f"Slack channel: {config['notifications']['slack']['channel']}")
    print(f"Transcription budget: ${config['budgets']['transcription_daily_usd']}")
    print(f"Max video duration: {get_max_video_duration(config)} seconds")
    print(f"Drive naming format: {get_drive_naming_format(config)}")
    print(f"Retry max attempts: {get_retry_max_attempts(config)}")
    print(f"Retry base delay: {get_retry_base_delay(config)} seconds")
    print(f"YouTube daily limit: {get_youtube_daily_limit(config)}")
    print(f"AssemblyAI daily limit: {get_assemblyai_daily_limit(config)}")
