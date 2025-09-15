"""
Environment variable loader for Autopiloot agents.
Loads and validates all required environment variables.
"""

import os
from pathlib import Path
from typing import Dict, Optional, List
from dotenv import load_dotenv


class EnvironmentError(Exception):
    """Raised when required environment variables are missing or invalid."""
    pass


def load_environment(env_file: Optional[str] = None) -> None:
    """
    Load environment variables from .env file.
    
    Args:
        env_file: Optional path to .env file. If None, looks for .env in current directory.
        
    Raises:
        EnvironmentError: If .env file is not found (in development)
    """
    if env_file is None:
        # Look for .env file in the same directory as this script
        env_path = Path(__file__).parent.parent / ".env"
    else:
        env_path = Path(env_file)
    
    # Load .env file if it exists
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # In production, environment variables should be set by the system
        # In development, we need the .env file
        print(f"Warning: .env file not found at {env_path}")
        print("Assuming environment variables are set by the system.")


def get_required_env_var(name: str, description: str = "") -> str:
    """
    Get a required environment variable.
    
    Args:
        name: Environment variable name
        description: Optional description for error messages
        
    Returns:
        Environment variable value
        
    Raises:
        EnvironmentError: If the environment variable is not set or empty
    """
    value = os.getenv(name)
    if not value:
        desc_part = f" ({description})" if description else ""
        raise EnvironmentError(f"Required environment variable {name}{desc_part} is not set")
    return value


def get_optional_env_var(name: str, default: str = "", description: str = "") -> str:
    """
    Get an optional environment variable with a default value.
    
    Args:
        name: Environment variable name
        default: Default value if not set
        description: Optional description for logging
        
    Returns:
        Environment variable value or default
    """
    return os.getenv(name, default)


def validate_environment() -> Dict[str, str]:
    """
    Validate that all required environment variables are present.
    
    Returns:
        Dictionary of environment variable names and values
        
    Raises:
        EnvironmentError: If any required environment variables are missing
    """
    # Load environment variables
    load_environment()
    
    # Required environment variables
    required_vars = {
        "OPENAI_API_KEY": "OpenAI API key for LLM operations",
        "ASSEMBLYAI_API_KEY": "AssemblyAI API key for transcription",
        "YOUTUBE_API_KEY": "YouTube Data API key for video discovery",
        "SLACK_BOT_TOKEN": "Slack bot token for notifications",
        "GOOGLE_APPLICATION_CREDENTIALS": "Path to Google service account JSON file",
        "GCP_PROJECT_ID": "Google Cloud Project ID for Firestore and other GCP services",
        "GOOGLE_DRIVE_FOLDER_ID_TRANSCRIPTS": "Google Drive folder ID for transcript storage",
        "GOOGLE_DRIVE_FOLDER_ID_SUMMARIES": "Google Drive folder ID for summary storage",
        "ZEP_API_KEY": "Zep API key for GraphRAG storage",
    }
    
    # Optional environment variables with defaults
    optional_vars = {
        "ZEP_COLLECTION": "autopiloot_guidelines",
        "ZEP_BASE_URL": "https://api.getzep.com",
        "TIMEZONE": "Europe/Amsterdam",
        "LANGFUSE_HOST": "https://cloud.langfuse.com",
        "SLACK_SIGNING_SECRET": "",  # Optional for webhook verification
        "LANGFUSE_PUBLIC_KEY": "",   # Optional for observability
        "LANGFUSE_SECRET_KEY": "",   # Optional for observability
        "SLACK_ALERTS_CHANNEL": "",  # Optional, can be set in settings.yaml
    }
    
    env_values = {}
    missing_vars = []
    
    # Check required variables
    for var_name, description in required_vars.items():
        try:
            env_values[var_name] = get_required_env_var(var_name, description)
        except EnvironmentError:
            missing_vars.append(f"  - {var_name}: {description}")
    
    # If any required variables are missing, raise an error with all missing vars
    if missing_vars:
        error_msg = "Missing required environment variables:\n" + "\n".join(missing_vars)
        error_msg += f"\n\nPlease copy .env.template to .env and fill in your values."
        raise EnvironmentError(error_msg)
    
    # Set optional variables
    for var_name, default_value in optional_vars.items():
        env_values[var_name] = get_optional_env_var(var_name, default_value)
    
    return env_values


def get_google_credentials_path() -> str:
    """
    Get the path to Google service account credentials.
    
    Returns:
        Path to Google credentials JSON file
        
    Raises:
        EnvironmentError: If credentials path is not set or file doesn't exist
    """
    creds_path = get_required_env_var("GOOGLE_APPLICATION_CREDENTIALS", "Google service account credentials")
    
    if not Path(creds_path).exists():
        raise EnvironmentError(f"Google credentials file not found: {creds_path}")
    
    return creds_path


def get_api_key(service: str) -> str:
    """
    Get API key for a specific service.
    
    Args:
        service: Service name (openai, assemblyai, youtube, zep, slack)
        
    Returns:
        API key for the service
        
    Raises:
        EnvironmentError: If API key is not found
    """
    service_mapping = {
        "openai": "OPENAI_API_KEY",
        "assemblyai": "ASSEMBLYAI_API_KEY", 
        "youtube": "YOUTUBE_API_KEY",
        "zep": "ZEP_API_KEY",
        "slack": "SLACK_BOT_TOKEN",
    }
    
    if service not in service_mapping:
        raise EnvironmentError(f"Unknown service: {service}. Available: {list(service_mapping.keys())}")
    
    env_var = service_mapping[service]
    return get_required_env_var(env_var, f"{service} API key")


def get_langfuse_config() -> Dict[str, str]:
    """
    Get Langfuse configuration for LLM observability.
    
    Returns:
        Dictionary with Langfuse configuration (may contain empty values if not configured)
    """
    return {
        "public_key": get_optional_env_var("LANGFUSE_PUBLIC_KEY"),
        "secret_key": get_optional_env_var("LANGFUSE_SECRET_KEY"),
        "host": get_optional_env_var("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    }


if __name__ == "__main__":
    # Test environment loading
    try:
        print("Testing environment variable loading...")
        env_vars = validate_environment()
        print("✅ All required environment variables are present:")
        
        # Print non-sensitive info
        print(f"  - Timezone: {env_vars.get('TIMEZONE')}")
        print(f"  - Zep Collection: {env_vars.get('ZEP_COLLECTION')}")
        print(f"  - Langfuse Host: {env_vars.get('LANGFUSE_HOST')}")
        
        # Test API key access (without printing actual keys)
        services = ["openai", "assemblyai", "youtube", "zep", "slack"]
        for service in services:
            try:
                key = get_api_key(service)
                print(f"  - {service.upper()} API key: {'✅ Set' if key else '❌ Missing'}")
            except EnvironmentError as e:
                print(f"  - {service.upper()} API key: ❌ {e}")
        
        # Test Google credentials
        try:
            creds_path = get_google_credentials_path()
            print(f"  - Google credentials: ✅ {creds_path}")
        except EnvironmentError as e:
            print(f"  - Google credentials: ❌ {e}")
        
        print("\n🎉 Environment configuration is valid!")
        
    except EnvironmentError as e:
        print(f"❌ Environment validation failed:\n{e}")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        exit(1)
