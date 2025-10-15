"""
GetUserPosts tool for fetching LinkedIn user posts via RapidAPI.
Supports pagination, date filtering, and backfill of historical posts.
Stores posts to Firestore for persistence and tracking.
"""

import os
import sys
import json
import time
import requests
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore

# Add core and config directories to path
from env_loader import get_required_env_var, load_environment
from firestore_client import get_firestore_client
from loader import get_config_value

# Import SaveIngestionRecord for audit logging
try:
    from linkedin_agent.tools.save_ingestion_record import SaveIngestionRecord
except ImportError:
    SaveIngestionRecord = None


class GetUserPosts(BaseTool):
    """
    Fetches LinkedIn posts from a user profile using RapidAPI and stores to Firestore.

    Handles pagination, rate limiting, historical backfill, and persistent storage.
    Uses the Fresh LinkedIn Scraper API via RapidAPI to retrieve posts.
    Stores posts to linkedin_posts/{post_id} collection with idempotent upsert.
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
        Fetches LinkedIn posts for the specified user and stores to Firestore.

        Returns:
            str: JSON string containing posts data with pagination and storage info
                 Format: {
                     "posts": [...],
                     "pagination": {
                         "page": 1,
                         "page_size": 25,
                         "has_more": true,
                         "total_fetched": 25
                     },
                     "storage": {
                         "total_stored": 25,
                         "created": 20,
                         "updated": 5,
                         "errors": 0
                     },
                     "metadata": {
                         "user_urn": "...",
                         "fetched_at": "2024-01-15T10:30:00Z"
                     }
                 }
        """
        # Track processing start time and generate run ID
        start_time = time.time()
        run_id = str(uuid.uuid4())
        errors_list = []

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

            # Store posts to Firestore
            storage_results = self._store_posts_to_firestore(posts)

            # Prepare response
            result = {
                "posts": posts,
                "pagination": {
                    "page": self.page,
                    "page_size": self.page_size,
                    "has_more": has_more,
                    "total_fetched": total_fetched
                },
                "storage": {
                    "total_stored": storage_results["total_stored"],
                    "created": storage_results["created"],
                    "updated": storage_results["updated"],
                    "errors": storage_results["errors"]
                },
                "metadata": {
                    "user_urn": self.user_urn,
                    "fetched_at": datetime.now(timezone.utc).isoformat()
                }
            }

            if self.since_iso:
                result["metadata"]["since_filter"] = self.since_iso

            # Save audit record
            processing_duration = time.time() - start_time
            self._save_audit_record(
                run_id=run_id,
                ingestion_stats={
                    "posts_processed": total_fetched,
                    "posts_stored": storage_results["total_stored"],
                    "posts_created": storage_results["created"],
                    "posts_updated": storage_results["updated"],
                    "storage_errors": storage_results["errors"]
                },
                processing_duration=processing_duration,
                errors=errors_list
            )

            return json.dumps(result)

        except Exception as e:
            # Track error
            error_info = {
                "type": "posts_fetch_failed",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            errors_list.append(error_info)

            # Save audit record with error
            processing_duration = time.time() - start_time
            self._save_audit_record(
                run_id=run_id,
                ingestion_stats={
                    "posts_processed": 0,
                    "posts_stored": 0
                },
                processing_duration=processing_duration,
                errors=errors_list
            )

            error_result = {
                "error": "posts_fetch_failed",
                "message": str(e),
                "user_urn": self.user_urn
            }
            return json.dumps(error_result)

    def _decode_url_encoded_string(self, value: str) -> str:
        """
        Decode URL-encoded characters from strings.
        Removes encoded characters like %C3, %B6, etc.

        Args:
            value: String potentially containing URL-encoded characters

        Returns:
            str: Decoded string with proper UTF-8 characters
        """
        if not value or not isinstance(value, str):
            return value

        try:
            # URL decode the string to convert %XX to actual characters
            return unquote(value)
        except Exception:
            # If decoding fails, return original value
            return value

    def _store_profile_to_firestore(self, db, author: Dict) -> str:
        """
        Store LinkedIn profile to Firestore with idempotent upsert.
        Decodes URL-encoded characters from all string fields.

        Args:
            db: Firestore client
            author: Author/profile dictionary from API

        Returns:
            str: Author URN (profile ID)
        """
        try:
            author_urn = author.get('urn', '')
            if not author_urn:
                return ''

            # Create document reference using URN as ID
            doc_ref = db.collection('linkedin_profiles').document(author_urn)
            existing_doc = doc_ref.get()

            # Prepare profile data with URL decoding
            profile_data = {
                'id': self._decode_url_encoded_string(author.get('id', '')),
                'urn': author_urn,
                'public_identifier': self._decode_url_encoded_string(author.get('public_identifier', '')),
                'first_name': self._decode_url_encoded_string(author.get('first_name', '')),
                'last_name': self._decode_url_encoded_string(author.get('last_name', '')),
                'headline': self._decode_url_encoded_string(author.get('description', '')),
                'profile_url': self._decode_url_encoded_string(author.get('url', '')),
                'updated_at': firestore.SERVER_TIMESTAMP
            }

            # Idempotent upsert
            if not existing_doc.exists:
                profile_data['created_at'] = firestore.SERVER_TIMESTAMP
                doc_ref.set(profile_data)
            else:
                doc_ref.update(profile_data)

            return author_urn

        except Exception as e:
            print(f"Error storing profile {author.get('urn', 'unknown')}: {str(e)}")
            return ''

    def _store_posts_to_firestore(self, posts: List[Dict]) -> Dict[str, int]:
        """
        Store LinkedIn posts to Firestore with idempotent upsert.
        Extracts author profiles and stores them separately.

        Args:
            posts: List of post dictionaries from API

        Returns:
            dict: Storage statistics with counts for created, updated, errors
        """
        created = 0
        updated = 0
        errors = 0

        if not posts:
            return {"total_stored": 0, "created": 0, "updated": 0, "errors": 0}

        try:
            db = get_firestore_client()

            for post in posts:
                try:
                    # Extract post ID from URN or use 'id' field
                    post_id = post.get("id", post.get("urn", "")).replace("urn:li:share:", "")

                    if not post_id:
                        errors += 1
                        continue

                    # Store author profile separately and get URN
                    author = post.get('author', {})
                    author_urn = self._store_profile_to_firestore(db, author) if author else ''

                    # Create document reference
                    doc_ref = db.collection('linkedin_posts').document(post_id)
                    existing_doc = doc_ref.get()

                    # Prepare post data with author reference only
                    post_data = {
                        'post_id': post_id,
                        'author_urn': author_urn,  # Reference to linkedin_profiles
                        'urn': post.get('share_urn', ''),  # LinkedIn share URN
                        'text': post.get('text', ''),
                        'posted_at': post.get('created_at', ''),  # Post timestamp
                        'post_url': post.get('url', ''),  # LinkedIn post URL
                        'activity': post.get('activity', {}),  # Engagement metrics
                        'status': 'discovered',
                        'updated_at': firestore.SERVER_TIMESTAMP
                    }

                    # Idempotent upsert
                    if not existing_doc.exists:
                        post_data['created_at'] = firestore.SERVER_TIMESTAMP
                        doc_ref.set(post_data)
                        created += 1
                    else:
                        doc_ref.update(post_data)
                        updated += 1

                except Exception as e:
                    print(f"Error storing post {post.get('id', 'unknown')}: {str(e)}")
                    errors += 1
                    continue

            return {
                "total_stored": created + updated,
                "created": created,
                "updated": updated,
                "errors": errors
            }

        except Exception as e:
            print(f"Firestore storage error: {str(e)}")
            return {
                "total_stored": 0,
                "created": 0,
                "updated": 0,
                "errors": len(posts)
            }

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

    def _save_audit_record(self, run_id: str, ingestion_stats: Dict, processing_duration: float, errors: List[Dict]):
        """
        Save audit record for this ingestion run.

        Args:
            run_id: Unique run identifier
            ingestion_stats: Statistics from ingestion
            processing_duration: Duration in seconds
            errors: List of errors encountered
        """
        if not SaveIngestionRecord:
            return  # Skip if audit tool not available

        try:
            audit_tool = SaveIngestionRecord(
                run_id=run_id,
                profile_identifier=self.user_urn,
                content_type="posts",
                ingestion_stats=ingestion_stats,
                processing_duration_seconds=processing_duration,
                errors=errors if errors else None
            )
            audit_tool.run()
        except Exception as e:
            # Don't fail the main operation if audit logging fails
            print(f"Warning: Failed to save audit record: {str(e)}")


if __name__ == "__main__":
    # Test the tool with ilke-oner's URN
    tool = GetUserPosts(
        user_urn="ACoAAAHgd4AByBB_-yxtC25kj4Kmlw9ubw8Vmtk",  # ilke-oner
        page=1,
        page_size=10,
        max_items=20
    )
    print("Testing GetUserPosts tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))