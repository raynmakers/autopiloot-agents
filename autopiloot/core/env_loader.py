"""
Standardized environment variable loader for all Autopiloot tools.
Provides consistent validation, error handling, and configuration access.
"""

import os
from typing import Optional, Dict, Any, List
from pathlib import Path
from dotenv import load_dotenv
import yaml

# Load environment variables from .env file
load_dotenv()


class EnvironmentError(Exception):
    """Raised when required environment variables are missing or invalid."""
    pass


class EnvironmentLoader:
    """
    Centralized environment variable loader with validation and defaults.
    """
    
    def __init__(self):
        """Initialize the environment loader."""
        self._config_cache: Optional[Dict[str, Any]] = None
    
    def get_required_var(self, var_name: str, description: str = "") -> str:
        """
        Get a required environment variable.
        
        Args:
            var_name: Environment variable name
            description: Human-readable description for error messages
            
        Returns:
            str: Environment variable value
            
        Raises:
            EnvironmentError: If variable is not set or empty
        """
        value = os.getenv(var_name)
        if not value:
            desc_text = f" ({description})" if description else ""
            raise EnvironmentError(
                f"Required environment variable {var_name} is not set{desc_text}. "
                f"Please check your .env file."
            )
        return value.strip()
    
    def get_optional_var(self, var_name: str, default: str = "", description: str = "") -> str:
        """
        Get an optional environment variable with default.
        
        Args:
            var_name: Environment variable name
            default: Default value if not set
            description: Human-readable description
            
        Returns:
            str: Environment variable value or default
        """
        value = os.getenv(var_name, default)
        return value.strip() if value else default
    
    def get_bool_var(self, var_name: str, default: bool = False) -> bool:
        """
        Get a boolean environment variable.
        
        Args:
            var_name: Environment variable name
            default: Default value if not set
            
        Returns:
            bool: Parsed boolean value
        """
        value = os.getenv(var_name, "").lower()
        if value in ("true", "1", "yes", "on"):
            return True
        elif value in ("false", "0", "no", "off"):
            return False
        else:
            return default
    
    def get_float_var(self, var_name: str, default: float = 0.0) -> float:
        """
        Get a float environment variable.
        
        Args:
            var_name: Environment variable name
            default: Default value if not set
            
        Returns:
            float: Parsed float value
        """
        value = os.getenv(var_name)
        if not value:
            return default
        
        try:
            return float(value)
        except ValueError:
            return default
    
    def get_int_var(self, var_name: str, default: int = 0) -> int:
        """
        Get an integer environment variable.
        
        Args:
            var_name: Environment variable name
            default: Default value if not set
            
        Returns:
            int: Parsed integer value
        """
        value = os.getenv(var_name)
        if not value:
            return default
        
        try:
            return int(value)
        except ValueError:
            return default
    
    def validate_file_path(self, var_name: str, description: str = "") -> str:
        """
        Validate that an environment variable points to an existing file.
        
        Args:
            var_name: Environment variable name
            description: Human-readable description
            
        Returns:
            str: Validated file path
            
        Raises:
            EnvironmentError: If file doesn't exist
        """
        file_path = self.get_required_var(var_name, description)
        
        if not Path(file_path).exists():
            desc_text = f" ({description})" if description else ""
            raise EnvironmentError(
                f"File specified in {var_name} does not exist: {file_path}{desc_text}"
            )
        
        return file_path
    
    def load_settings_config(self) -> Dict[str, Any]:
        """
        Load configuration from settings.yaml file.
        
        Returns:
            Dict[str, Any]: Parsed configuration
            
        Raises:
            EnvironmentError: If settings file cannot be loaded
        """
        if self._config_cache is not None:
            return self._config_cache
        
        # Look for settings.yaml in various locations
        possible_paths = [
            Path(__file__).parent / "settings.yaml",
            Path(__file__).parent.parent / "config" / "settings.yaml",
            Path("autopiloot/config/settings.yaml"),
            Path("config/settings.yaml"),
            Path("settings.yaml")
        ]
        
        settings_path = None
        for path in possible_paths:
            if path.exists():
                settings_path = path
                break
        
        if not settings_path:
            raise EnvironmentError(
                f"settings.yaml not found in any of these locations: {[str(p) for p in possible_paths]}"
            )
        
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                self._config_cache = yaml.safe_load(f) or {}
                return self._config_cache
        except Exception as e:
            raise EnvironmentError(f"Failed to load settings from {settings_path}: {str(e)}")
    
    def get_config_value(self, key_path: str, default: Any = None) -> Any:
        """
        Get a value from settings.yaml using dot notation.
        
        Args:
            key_path: Dot-separated path (e.g., "scraper.daily_limit_per_channel")
            default: Default value if key not found
            
        Returns:
            Any: Configuration value or default
            
        Example:
            get_config_value("llm.default.temperature", 0.2)
        """
        config = self.load_settings_config()
        
        keys = key_path.split('.')
        value = config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def validate_required_environment(self) -> Dict[str, str]:
        """
        Validate all required environment variables for basic operation.
        
        Returns:
            Dict[str, str]: All validated environment variables
            
        Raises:
            EnvironmentError: If any required variables are missing
        """
        required_vars = {}
        errors = []
        
        # Core API keys
        try:
            required_vars['OPENAI_API_KEY'] = self.get_required_var(
                'OPENAI_API_KEY', 'OpenAI API key for GPT-4 summaries'
            )
        except EnvironmentError as e:
            errors.append(str(e))
        
        try:
            required_vars['YOUTUBE_API_KEY'] = self.get_required_var(
                'YOUTUBE_API_KEY', 'YouTube Data API key for video discovery'
            )
        except EnvironmentError as e:
            errors.append(str(e))
        
        # Google Cloud setup
        try:
            # Check for either service account path or application credentials
            service_account_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_PATH')
            app_credentials = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            
            if service_account_path:
                required_vars['GOOGLE_SERVICE_ACCOUNT_PATH'] = self.validate_file_path(
                    'GOOGLE_SERVICE_ACCOUNT_PATH', 'Google Cloud service account JSON file'
                )
            elif app_credentials:
                required_vars['GOOGLE_APPLICATION_CREDENTIALS'] = self.validate_file_path(
                    'GOOGLE_APPLICATION_CREDENTIALS', 'Google Cloud application credentials'
                )
            else:
                errors.append(
                    "Either GOOGLE_SERVICE_ACCOUNT_PATH or GOOGLE_APPLICATION_CREDENTIALS must be set"
                )
        except EnvironmentError as e:
            errors.append(str(e))
        
        try:
            required_vars['GCP_PROJECT_ID'] = self.get_required_var(
                'GCP_PROJECT_ID', 'Google Cloud Project ID'
            )
        except EnvironmentError as e:
            errors.append(str(e))
        
        if errors:
            error_msg = "Required environment variables are missing:\n" + "\n".join(f"  - {err}" for err in errors)
            error_msg += f"\n\nPlease copy .env.template to .env and fill in your values."
            raise EnvironmentError(error_msg)
        
        return required_vars
    
    def get_service_credentials(self) -> str:
        """
        Get Google Cloud service account credentials path.
        
        Returns:
            str: Path to service account JSON file
            
        Raises:
            EnvironmentError: If no valid credentials found
        """
        # Check GOOGLE_SERVICE_ACCOUNT_PATH first (our preference)
        service_account_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_PATH')
        if service_account_path and Path(service_account_path).exists():
            return service_account_path
        
        # Fallback to GOOGLE_APPLICATION_CREDENTIALS
        app_credentials = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if app_credentials and Path(app_credentials).exists():
            return app_credentials
        
        raise EnvironmentError(
            "No valid Google Cloud credentials found. Set either:\n"
            "  - GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/service-account.json\n"
            "  - GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json"
        )


# Global instance for easy access
env_loader = EnvironmentLoader()

# Convenience functions for common usage patterns
def get_required_var(var_name: str, description: str = "") -> str:
    """Get a required environment variable."""
    return env_loader.get_required_var(var_name, description)

def get_optional_var(var_name: str, default: str = "", description: str = "") -> str:
    """Get an optional environment variable."""
    return env_loader.get_optional_var(var_name, default, description)

def get_config_value(key_path: str, default: Any = None) -> Any:
    """Get a configuration value from settings.yaml."""
    return env_loader.get_config_value(key_path, default)

def validate_environment() -> Dict[str, str]:
    """Validate all required environment variables."""
    return env_loader.validate_required_environment()


if __name__ == "__main__":
    # Test the environment loader
    try:
        print("🧪 Testing environment loader...")
        
        # Test required variables
        env_vars = validate_environment()
        print("✅ All required environment variables found:")
        for key, value in env_vars.items():
            masked_value = value[:8] + "..." if len(value) > 8 else value
            print(f"   {key}: {masked_value}")
        
        # Test settings loading
        config = env_loader.load_settings_config()
        print(f"✅ Settings loaded: {len(config)} top-level keys")
        
        # Test config access
        daily_limit = get_config_value("scraper.daily_limit_per_channel", 10)
        print(f"✅ Config access: scraper.daily_limit_per_channel = {daily_limit}")
        
        print("🎉 Environment validation passed!")
        
    except EnvironmentError as e:
        print(f"❌ Environment validation failed:")
        print(f"   {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()