"""
GetPostReactions tool for tracking LinkedIn post reactions via RapidAPI.
Focuses on identifying which profiles are engaging with an author's content.
Stores reactor-author interaction data to Firestore.
"""

import os
import sys
import json
import time
import requests
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from urllib.parse import unquote
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore

# Add core and config directories to path
from env_loader import get_required_env_var, load_environment
from loader import get_config_value

# Import SaveIngestionRecord for audit logging
try:
    from linkedin_agent.tools.save_ingestion_record import SaveIngestionRecord
except ImportError:
    SaveIngestionRecord = None


class GetPostReactions(BaseTool):
    """
    Fetches reactions for LinkedIn posts to track which profiles engage with an author.

    Use case: Identify top engagers who frequently react to a specific author's content.
    Stores aggregated reactor-author interaction data in Firestore for analysis.

    Output: Reactor profiles with total reactions and list of posts they engaged with.
    """

    post_ids: List[str] = Field(
        ...,
        description="List of LinkedIn post IDs to fetch reactions for (typically from one author)"
    )

    author_profile_id: str = Field(
        ...,
        description="LinkedIn profile ID/URN of the post author (for tracking engagement)"
    )

    max_reactions_per_post: int = Field(
        100,
        description="Maximum reactions to fetch per post (default: 100)"
    )

    def run(self) -> str:
        """
        Fetches reactions and identifies top engagers with the author.

        Returns:
            str: JSON string with reactor engagement summary
                 Format: {
                     "top_reactors": [
                         {
                             "profile_id": "john-doe",
                             "name": "John Doe",
                             "total_reactions": 5,
                             "posts_reacted_to": ["post1", "post2"],
                             "reaction_breakdown": {"like": 3, "celebrate": 2}
                         }
                     ],
                     "storage": {
                         "profiles_stored": 15,
                         "reactions_stored": 48
                     },
                     "metadata": {
                         "author_profile_id": "ilke-oner",
                         "posts_analyzed": 3,
                         "fetched_at": "2025-10-10T12:00:00Z"
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

            # Load plugin configuration
            plugin_config = get_config_value(f"rapidapi.plugins.{plugin_name}", None)
            if not plugin_config:
                raise ValueError(f"RapidAPI plugin '{plugin_name}' not found in settings.yaml")

            # Get host and API key env var name
            rapidapi_host = plugin_config.get("host")
            api_key_env = plugin_config.get("api_key_env")
            endpoints = plugin_config.get("endpoints", {})

            if not rapidapi_host or not api_key_env:
                raise ValueError(f"Plugin '{plugin_name}' missing 'host' or 'api_key_env'")

            # Get actual API key
            rapidapi_key = get_required_env_var(api_key_env, f"RapidAPI key for {plugin_name}")

            # Get endpoint path
            endpoint_path = endpoints.get("post_reactions", "/post-reactions")

            if not self.post_ids:
                return json.dumps({
                    "error": "invalid_input",
                    "message": "No post IDs provided"
                })

            # Prepare API endpoint and headers
            base_url = f"https://{rapidapi_host}{endpoint_path}"
            headers = {
                "X-RapidAPI-Host": rapidapi_host,
                "X-RapidAPI-Key": rapidapi_key,
                "Accept": "application/json"
            }

            # Track reactors across all posts
            reactor_data = {}  # {profile_id: {name, reactions_count, posts_list, reaction_types}}

            # Fetch reactions for each post
            for post_id in self.post_ids:
                params = {
                    "post_id": post_id,
                    "page": 1,
                    "type": "all"  # Fetch all reaction types
                }

                # Make API request with retry logic
                response_data = self._make_request_with_retry(base_url, headers, params)

                if response_data:
                    # Process reactors from this post
                    reactions = response_data.get("data", [])

                    for reaction in reactions:
                        # Extract user data from nested structure
                        user = reaction.get("user", {})
                        profile_url = user.get("url", "")
                        profile_id = self._extract_profile_id(profile_url)

                        if not profile_id:
                            continue

                        # Initialize reactor entry if new
                        if profile_id not in reactor_data:
                            reactor_data[profile_id] = {
                                "profile_id": profile_id,
                                "name": user.get("name", "Unknown"),
                                "headline": user.get("description", ""),
                                "profile_url": profile_url,
                                "total_reactions": 0,
                                "posts_reacted_to": [],
                                "reaction_breakdown": {}
                            }

                        # Update reactor stats
                        reactor_info = reactor_data[profile_id]
                        reactor_info["total_reactions"] += 1

                        # Track which post (avoid duplicates)
                        if post_id not in reactor_info["posts_reacted_to"]:
                            reactor_info["posts_reacted_to"].append(post_id)

                        # Track reaction type
                        reaction_type = reaction.get("reaction_type", "LIKE")
                        reactor_info["reaction_breakdown"][reaction_type] = \
                            reactor_info["reaction_breakdown"].get(reaction_type, 0) + 1

                # Rate limiting
                if len(self.post_ids) > 1:
                    time.sleep(0.5)

            # Sort reactors by total reactions (top engagers first)
            top_reactors = sorted(
                reactor_data.values(),
                key=lambda x: x["total_reactions"],
                reverse=True
            )

            # Store to Firestore
            storage_result = self._store_reactions_to_firestore(
                self.author_profile_id,
                top_reactors
            )

            # Prepare response
            result = {
                "top_reactors": top_reactors,
                "storage": storage_result,
                "metadata": {
                    "author_profile_id": self.author_profile_id,
                    "posts_analyzed": len(self.post_ids),
                    "unique_reactors": len(top_reactors),
                    "total_reactions": sum(r["total_reactions"] for r in top_reactors),
                    "fetched_at": datetime.now(timezone.utc).isoformat()
                }
            }

            # Save audit record
            processing_duration = time.time() - start_time
            self._save_audit_record(
                run_id=run_id,
                ingestion_stats={
                    "reactions_processed": sum(r["total_reactions"] for r in top_reactors),
                    "unique_reactors": len(top_reactors),
                    "profiles_stored": storage_result["profiles_stored"],
                    "reactions_stored": storage_result["reactions_stored"],
                    "storage_errors": storage_result["errors"],
                    "posts_analyzed": len(self.post_ids)
                },
                processing_duration=processing_duration,
                errors=errors_list
            )

            return json.dumps(result)

        except Exception as e:
            # Track error
            error_info = {
                "type": "reactions_fetch_failed",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            errors_list.append(error_info)

            # Save audit record with error
            processing_duration = time.time() - start_time
            self._save_audit_record(
                run_id=run_id,
                ingestion_stats={
                    "reactions_processed": 0,
                    "unique_reactors": 0,
                    "posts_analyzed": len(self.post_ids) if self.post_ids else 0
                },
                processing_duration=processing_duration,
                errors=errors_list
            )

            error_result = {
                "error": "reactions_fetch_failed",
                "message": str(e),
                "post_ids": self.post_ids
            }
            return json.dumps(error_result)

    def _decode_url_encoded_string(self, value: str) -> str:
        """
        Decode URL-encoded characters from strings.

        Args:
            value: String potentially containing URL-encoded characters

        Returns:
            str: Decoded string with proper UTF-8 characters
        """
        if not value or not isinstance(value, str):
            return value

        try:
            return unquote(value)
        except Exception:
            return value

    def _extract_profile_id(self, profile_url: str) -> str:
        """
        Extract profile ID from LinkedIn URL.

        Args:
            profile_url: Full LinkedIn profile URL

        Returns:
            str: Profile ID (e.g., 'ilke-oner')
        """
        if not profile_url:
            return ''

        # Extract identifier from URL
        decoded_url = self._decode_url_encoded_string(profile_url)
        profile_id = decoded_url.rstrip('/').split('/')[-1] if decoded_url else ''

        return profile_id

    def _initialize_firestore(self):
        """Initialize Firestore client with proper authentication."""
        try:
            project_id = get_required_env_var(
                "GCP_PROJECT_ID",
                "Google Cloud Project ID for Firestore"
            )

            credentials_path = get_required_env_var(
                "GOOGLE_APPLICATION_CREDENTIALS",
                "Google service account credentials file path"
            )

            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Service account file not found: {credentials_path}")

            return firestore.Client(project=project_id)

        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firestore client: {str(e)}")

    def _store_profile_to_firestore(self, db, reactor: Dict) -> str:
        """
        Store reactor profile to Firestore with idempotent upsert.

        Args:
            db: Firestore client
            reactor: Reactor profile data

        Returns:
            str: Profile ID
        """
        try:
            profile_id = reactor.get('profile_id', '')
            if not profile_id:
                return ''

            doc_ref = db.collection('linkedin_profiles').document(profile_id)
            existing_doc = doc_ref.get()

            # Split name into first and last
            full_name = self._decode_url_encoded_string(reactor.get('name', ''))
            name_parts = full_name.split(' ', 1) if full_name else ['', '']
            first_name = name_parts[0] if len(name_parts) > 0 else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            profile_data = {
                'public_identifier': profile_id,
                'first_name': first_name,
                'last_name': last_name,
                'headline': self._decode_url_encoded_string(reactor.get('headline', '')),
                'profile_url': self._decode_url_encoded_string(reactor.get('profile_url', '')),
                'updated_at': firestore.SERVER_TIMESTAMP
            }

            if not existing_doc.exists:
                profile_data['created_at'] = firestore.SERVER_TIMESTAMP
                doc_ref.set(profile_data)
            else:
                doc_ref.update(profile_data)

            return profile_id

        except Exception as e:
            print(f"Error storing profile {reactor.get('profile_id', 'unknown')}: {str(e)}")
            return ''

    def _store_reactions_to_firestore(self, author_profile_id: str, reactors: List[Dict]) -> Dict[str, int]:
        """
        Store reactor-author interaction data to Firestore.

        Creates documents tracking which profiles engage with an author's content.

        Args:
            author_profile_id: Profile ID of the content author
            reactors: List of reactor data with engagement metrics

        Returns:
            dict: Storage statistics
        """
        profiles_stored = 0
        reactions_stored = 0
        errors = 0

        if not reactors:
            return {
                "profiles_stored": 0,
                "reactions_stored": 0,
                "errors": 0
            }

        try:
            db = self._initialize_firestore()

            for reactor in reactors:
                try:
                    # Store reactor profile
                    reactor_profile_id = self._store_profile_to_firestore(db, reactor)

                    if not reactor_profile_id:
                        errors += 1
                        continue

                    # Store reactor-author interaction
                    # Document ID: {reactor_profile_id}_{author_profile_id}
                    interaction_id = f"{reactor_profile_id}_{author_profile_id}"
                    doc_ref = db.collection('linkedin_reactions').document(interaction_id)
                    existing_doc = doc_ref.get()

                    interaction_data = {
                        'reactor_profile_id': reactor_profile_id,
                        'author_profile_id': author_profile_id,
                        'total_reactions': reactor['total_reactions'],
                        'posts_reacted_to': reactor['posts_reacted_to'],
                        'reaction_breakdown': reactor['reaction_breakdown'],
                        'updated_at': firestore.SERVER_TIMESTAMP
                    }

                    if not existing_doc.exists:
                        interaction_data['created_at'] = firestore.SERVER_TIMESTAMP
                        doc_ref.set(interaction_data)
                    else:
                        doc_ref.update(interaction_data)

                    profiles_stored += 1
                    reactions_stored += reactor['total_reactions']

                except Exception as e:
                    print(f"Error storing reactor {reactor.get('profile_id', 'unknown')}: {str(e)}")
                    errors += 1
                    continue

            return {
                "profiles_stored": profiles_stored,
                "reactions_stored": reactions_stored,
                "errors": errors
            }

        except Exception as e:
            print(f"Firestore storage error: {str(e)}")
            return {
                "profiles_stored": 0,
                "reactions_stored": 0,
                "errors": len(reactors)
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
        delay = 1

        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", delay * 2)
                    time.sleep(min(int(retry_after), 60))
                    delay *= 2
                    continue

                if response.status_code >= 500:
                    time.sleep(delay)
                    delay *= 2
                    continue

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
                profile_identifier=self.author_profile_id,
                content_type="reactions",
                ingestion_stats=ingestion_stats,
                processing_duration_seconds=processing_duration,
                errors=errors if errors else None
            )
            audit_tool.run()
        except Exception as e:
            # Don't fail the main operation if audit logging fails
            print(f"Warning: Failed to save audit record: {str(e)}")


if __name__ == "__main__":
    # Test the tool - track who engages with ilke-oner's posts
    tool = GetPostReactions(
        post_ids=["7381924494396891136", "7381586262505201666"],
        author_profile_id="ilke-oner",
        max_reactions_per_post=100
    )
    print("Testing GetPostReactions tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))
