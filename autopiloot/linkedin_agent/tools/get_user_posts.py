"""
GetUserPosts tool for fetching LinkedIn user posts via RapidAPI.
Supports pagination, date filtering, and backfill of historical posts.
"""

import os
import sys
import json
import time
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, load_environment
from loader import get_config_value


class GetUserPosts(BaseTool):
    """
    Fetches LinkedIn posts from a user profile using RapidAPI.

    Handles pagination, rate limiting, and historical backfill.
    Uses the Fresh LinkedIn Scraper API via RapidAPI to retrieve posts.
    """

    user_urn: str = Field(
        ...,
        description="LinkedIn user URN or profile identifier (e.g., 'alexhormozi' or full URN)"
    )

    page: int = Field(
        1,
        description="Page number for pagination (default: 1)"
    )

    page_size: int = Field(
        25,
        description="Number of posts per page (default: 25, max: 100)"
    )

    max_items: int = Field(
        100,
        description="Maximum total posts to fetch across all pages (default: 100, max: 1000)"
    )

    since_iso: Optional[str] = Field(
        None,
        description="Optional ISO 8601 datetime to fetch posts after this date (e.g., '2024-01-01T00:00:00Z')"
    )

    def run(self) -> str:
        """
        Fetches LinkedIn posts for the specified user.

        Returns:
            str: JSON string containing posts data with pagination info
                 Format: {
                     "posts": [...],
                     "pagination": {
                         "page": 1,
                         "page_size": 25,
                         "has_more": true,
                         "total_fetched": 25
                     },
                     "metadata": {
                         "user_urn": "...",
                         "fetched_at": "2024-01-15T10:30:00Z"
                     }
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
            endpoint_path = endpoints.get("user_posts", "/user-posts")

            # Validate inputs
            if self.page_size > 100:
                self.page_size = 100
            if self.max_items > 1000:
                self.max_items = 1000

            # Prepare API endpoint and headers
            base_url = f"https://{rapidapi_host}{endpoint_path}"
            headers = {
                "X-RapidAPI-Host": rapidapi_host,
                "X-RapidAPI-Key": rapidapi_key,
                "Accept": "application/json"
            }

            # Build query parameters
            params = {
                "urn": self.user_urn,
                "page": self.page,
                "pageSize": self.page_size
            }

            if self.since_iso:
                params["since"] = self.since_iso

            # Fetch posts with retry logic
            posts = []
            total_fetched = 0
            current_page = self.page
            has_more = True

            while has_more and total_fetched < self.max_items:
                # Update page parameter
                params["page"] = current_page

                # Make API request with exponential backoff
                response_data = self._make_request_with_retry(base_url, headers, params)

                if not response_data:
                    break

                # Extract posts from response
                page_posts = response_data.get("data", [])
                if not page_posts:
                    has_more = False
                    break

                # Add posts up to max_items limit
                remaining = self.max_items - total_fetched
                posts.extend(page_posts[:remaining])
                total_fetched += len(page_posts[:remaining])

                # Check for more pages
                pagination_info = response_data.get("pagination", {})
                has_more = pagination_info.get("hasMore", False) and total_fetched < self.max_items
                current_page += 1

                # Rate limiting - be respectful
                if has_more:
                    time.sleep(1)  # 1 second delay between pages

            # Prepare response
            result = {
                "posts": posts,
                "pagination": {
                    "page": self.page,
                    "page_size": self.page_size,
                    "has_more": has_more,
                    "total_fetched": total_fetched
                },
                "metadata": {
                    "user_urn": self.user_urn,
                    "fetched_at": datetime.now(timezone.utc).isoformat()
                }
            }

            if self.since_iso:
                result["metadata"]["since_filter"] = self.since_iso

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "posts_fetch_failed",
                "message": str(e),
                "user_urn": self.user_urn
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
    tool = GetUserPosts(
        user_urn="ilke-oner",
        page=1,
        page_size=10,
        max_items=20
    )
    print("Testing GetUserPosts tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))