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
        
        # Provide specific guidance based on variable type
        guidance = ""
        if "API_KEY" in name:
            guidance = f"\n  Hint: Obtain your API key from the service provider and add it to your .env file"
        elif "PROJECT_ID" in name:
            guidance = f"\n  Hint: Set this to your Google Cloud Project ID (e.g., my-project-123)"
        elif "CREDENTIALS" in name:
            guidance = f"\n  Hint: Set this to the path of your Google service account JSON file"
        elif "FOLDER_ID" in name:
            guidance = f"\n  Hint: Create a folder in Google Drive and use its ID from the URL"
        
        raise EnvironmentError(f"Required environment variable {name}{desc_part} is not set{guidance}")
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
        "ZEP_API_KEY": "Zep API key for GraphRAG storage",
    }

    # Optional environment variables with defaults
    optional_vars = {
        "ZEP_COLLECTION": "autopiloot_guidelines",
        "GOOGLE_DRIVE_FOLDER_ID_TRANSCRIPTS": "DEPRECATED - No longer used. Transcripts stored in Firestore only",
        "GOOGLE_DRIVE_FOLDER_ID_SUMMARIES": "DEPRECATED - No longer used. Summaries stored in Zep and Firestore only",
        "ZEP_BASE_URL": "https://api.getzep.com",
        "TIMEZONE": "Europe/Amsterdam",
        "LANGFUSE_HOST": "https://cloud.langfuse.com",
        "SLACK_SIGNING_SECRET": "",  # Optional for webhook verification
        "LANGFUSE_PUBLIC_KEY": "",   # Optional for observability
        "LANGFUSE_SECRET_KEY": "",   # Optional for observability
        "SLACK_ALERTS_CHANNEL": "",  # Optional, can be set in settings.yaml
        "OPENSEARCH_HOST": "",       # Optional for Hybrid RAG keyword retrieval
        "OPENSEARCH_API_KEY": "",    # Optional API key authentication
        "OPENSEARCH_USERNAME": "",   # Optional basic auth username
        "OPENSEARCH_PASSWORD": "",   # Optional basic auth password
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
        error_msg += f"\n\nTo fix this:"
        error_msg += f"\n  1. Copy .env.template to .env: cp .env.template .env"
        error_msg += f"\n  2. Edit .env and fill in your actual values"
        error_msg += f"\n  3. Restart your application"
        error_msg += f"\n\nFor detailed setup instructions, see docs/environment.md"
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
        raise EnvironmentError(
            f"Google credentials file not found: {creds_path}\n"
            f"  Hint: Download your service account key from Google Cloud Console and update the path"
        )
    
    return creds_path


def validate_gcp_project_access() -> str:
    """
    Validate GCP project ID and Firestore access.
    
    Returns:
        GCP project ID
        
    Raises:
        EnvironmentError: If project ID is invalid or Firestore access fails
    """
    project_id = get_required_env_var("GCP_PROJECT_ID", "Google Cloud Project ID for Firestore access")
    
    # Validate project ID format (basic check)
    if not project_id.replace("-", "").replace("_", "").replace("0", "").replace("1", "").replace("2", "").replace("3", "").replace("4", "").replace("5", "").replace("6", "").replace("7", "").replace("8", "").replace("9", "").isalnum():
        raise EnvironmentError(
            f"Invalid GCP project ID format: {project_id}\n"
            f"  Hint: Project IDs must contain only lowercase letters, numbers, and hyphens"
        )
    
    # Try to validate Firestore access (optional, only if google-cloud-firestore is available)
    try:
        from google.cloud import firestore
        import google.auth.exceptions
        
        # Attempt to initialize Firestore client
        try:
            db = firestore.Client(project=project_id)
            # Try a simple operation to validate access
            # This doesn't actually read data, just validates auth
            collections = db.collections()
            # Force evaluation of the generator to check access
            list(collections)
        except google.auth.exceptions.DefaultCredentialsError:
            raise EnvironmentError(
                f"Google Cloud authentication failed for project {project_id}\n"
                f"  Hint: Ensure GOOGLE_APPLICATION_CREDENTIALS points to a valid service account key"
            )
        except Exception as e:
            # If we can't access Firestore but credentials are valid, it might be permissions
            if "permission" in str(e).lower() or "access" in str(e).lower():
                raise EnvironmentError(
                    f"Firestore access denied for project {project_id}\n"
                    f"  Hint: Ensure your service account has Firestore permissions (roles/datastore.user)"
                )
            # For other errors, just warn but don't fail
            print(f"Warning: Could not fully validate Firestore access: {e}")
    
    except ImportError:
        # google-cloud-firestore not installed, skip validation
        print("Warning: google-cloud-firestore not installed, skipping Firestore access validation")
    
    return project_id


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


def validate_opensearch_config() -> Dict[str, str]:
    """
    Validate OpenSearch configuration for Hybrid RAG.

    Checks that if OpenSearch is enabled and host is provided, at least one
    authentication method is configured (API key OR username+password).

    Returns:
        Dictionary with OpenSearch configuration

    Raises:
        EnvironmentError: If OpenSearch is enabled but authentication is incomplete
    """
    opensearch_config = {
        "host": get_optional_env_var("OPENSEARCH_HOST"),
        "api_key": get_optional_env_var("OPENSEARCH_API_KEY"),
        "username": get_optional_env_var("OPENSEARCH_USERNAME"),
        "password": get_optional_env_var("OPENSEARCH_PASSWORD"),
    }

    # If host is not set, OpenSearch is not configured (optional feature)
    if not opensearch_config["host"]:
        return opensearch_config

    # If host is set, validate authentication
    has_api_key = bool(opensearch_config["api_key"])
    has_basic_auth = bool(opensearch_config["username"]) and bool(opensearch_config["password"])

    if not has_api_key and not has_basic_auth:
        raise EnvironmentError(
            "OpenSearch host is configured but no authentication method is provided.\n"
            "  Either set:\n"
            "    - OPENSEARCH_API_KEY for API key authentication, OR\n"
            "    - OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD for basic authentication\n"
            "  To disable OpenSearch, leave OPENSEARCH_HOST empty or set rag.opensearch.enabled to false in settings.yaml"
        )

    # Validate that basic auth has both username AND password
    if opensearch_config["username"] and not opensearch_config["password"]:
        raise EnvironmentError(
            "OPENSEARCH_USERNAME is set but OPENSEARCH_PASSWORD is missing.\n"
            "  Basic authentication requires both username and password."
        )

    if opensearch_config["password"] and not opensearch_config["username"]:
        raise EnvironmentError(
            "OPENSEARCH_PASSWORD is set but OPENSEARCH_USERNAME is missing.\n"
            "  Basic authentication requires both username and password."
        )

    return opensearch_config


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
        
        # Test GCP project access
        try:
            project_id = validate_gcp_project_access()
            print(f"  - GCP project access: ✅ {project_id}")
        except EnvironmentError as e:
            print(f"  - GCP project access: ❌ {e}")

        # Test OpenSearch configuration
        try:
            opensearch_config = validate_opensearch_config()
            if opensearch_config.get("host"):
                auth_method = "API Key" if opensearch_config.get("api_key") else "Basic Auth"
                print(f"  - OpenSearch configuration: ✅ {opensearch_config['host']} ({auth_method})")
            else:
                print(f"  - OpenSearch configuration: ⚪ Not configured (optional)")
        except EnvironmentError as e:
            print(f"  - OpenSearch configuration: ❌ {e}")

        print("\n🎉 Environment configuration is valid!")
        
    except EnvironmentError as e:
        print(f"❌ Environment validation failed:\n{e}")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        exit(1)
