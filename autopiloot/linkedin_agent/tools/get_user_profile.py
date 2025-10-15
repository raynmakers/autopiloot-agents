"""
GetUserProfile tool for fetching LinkedIn user profile data via RapidAPI.
Retrieves profile information including URN, name, headline, and website.
"""

import os
import sys
import json
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
from env_loader import get_required_env_var, load_environment
from loader import get_config_value


class GetUserProfile(BaseTool):
    """
    Fetches LinkedIn user profile data using RapidAPI.

    Retrieves essential profile information including URN identifier,
    full name, headline, and associated website.
    """

    username: str = Field(
        ...,
        description="LinkedIn username or public identifier (e.g., 'ilke-oner')"
    )

    def run(self) -> str:
        """
        Fetches LinkedIn profile data for the specified username.

        Returns:
            str: JSON string containing profile data
                 Format: {
                     "id": "...",
                     "urn": "...",
                     "public_identifier": "...",
                     "first_name": "...",
                     "last_name": "...",
                     "full_name": "...",
                     "headline": "...",
                     "associated_hashtag": "...",
                     "website": "...",
                     "fetched_at": "2024-01-15T10:30:00Z"
                 }
        """
        try:
            # Load environment
            load_environment()

            # Get plugin name from linkedin.api.rapidapi_plugin
            plugin_name = get_config_value("linkedin.api.rapidapi_plugin", "linkedin_scraper")

            # Load plugin configuration from rapidapi.plugins[plugin_name]
            plugin_config = get_config_value(f"rapidapi.plugins.{plugin_name}", None)
            if not plugin_config:
                raise ValueError(f"RapidAPI plugin '{plugin_name}' not found in settings.yaml")

            # Get host and API key env var name from plugin config
            rapidapi_host = plugin_config.get("host")
            api_key_env = plugin_config.get("api_key_env")
            endpoints = plugin_config.get("endpoints", {})

            if not rapidapi_host or not api_key_env:
                raise ValueError(f"Plugin '{plugin_name}' missing 'host' or 'api_key_env' in settings.yaml")

            # Get actual API key from environment variable
            rapidapi_key = get_required_env_var(api_key_env, f"RapidAPI key for {plugin_name}")

            # Get endpoint path from plugin config
            endpoint_path = endpoints.get("user_profile", "/api/v1/user/profile")

            # Prepare API endpoint and headers
            base_url = f"https://{rapidapi_host}{endpoint_path}"
            headers = {
                "X-RapidAPI-Host": rapidapi_host,
                "X-RapidAPI-Key": rapidapi_key,
                "Accept": "application/json"
            }

            # Build query parameters
            params = {
                "username": self.username
            }

            # Make API request with retry logic
            response_data = self._make_request_with_retry(base_url, headers, params)

            if not response_data:
                return json.dumps({
                    "error": "profile_fetch_failed",
                    "message": "Failed to retrieve profile data after retries",
                    "username": self.username
                })

            # Extract relevant fields from response
            profile_data = response_data.get("data", {})

            result = {
                "id": profile_data.get("id"),
                "urn": profile_data.get("urn"),
                "public_identifier": profile_data.get("public_identifier"),
                "first_name": profile_data.get("first_name"),
                "last_name": profile_data.get("last_name"),
                "full_name": profile_data.get("full_name"),
                "headline": profile_data.get("headline"),
                "associated_hashtag": profile_data.get("associated_hashtag"),
                "website": profile_data.get("website"),
                "fetched_at": datetime.now(timezone.utc).isoformat()
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            error_result = {
                "error": "profile_fetch_failed",
                "message": str(e),
                "username": self.username
            }
            return json.dumps(error_result)

    def _make_request_with_retry(self, url: str, headers: Dict, params: Dict, max_retries: int = 3) -> Optional[Dict]:
        """
        Makes HTTP request with exponential backoff retry logic.

        Args:
            url: API endpoint URL
            headers: Request headers including RapidAPI credentials
            params: Query parameters
            max_retries: Maximum number of retry attempts

        Returns:
            Optional[Dict]: Response data or None if all retries failed
        """
        import time
        delay = 1  # Start with 1 second delay

        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)

                # Success
                if response.status_code == 200:
                    return response.json()

                # Rate limiting - back off
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", delay * 2)
                    time.sleep(min(int(retry_after), 60))  # Max 60 seconds wait
                    delay *= 2
                    continue

                # Server errors - retry with backoff
                if response.status_code >= 500:
                    time.sleep(delay)
                    delay *= 2
                    continue

                # Client error - don't retry
                if response.status_code >= 400:
                    print(f"Client error {response.status_code}: {response.text}")
                    return None

            except requests.exceptions.Timeout:
                print(f"Request timeout on attempt {attempt + 1}")
                time.sleep(delay)
                delay *= 2
            except requests.exceptions.RequestException as e:
                print(f"Request failed on attempt {attempt + 1}: {e}")
                time.sleep(delay)
                delay *= 2

        return None


if __name__ == "__main__":
    # Test the tool
    tool = GetUserProfile(
        username="ilke-oner"
    )
    print("Testing GetUserProfile tool...")
    result = tool.run()
    print(result)
