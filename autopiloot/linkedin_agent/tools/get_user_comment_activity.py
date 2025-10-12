"""
GetUserCommentActivity tool for fetching comments authored by a user on others' LinkedIn posts.
Tracks user engagement and conversation participation across the platform.
"""

import os
import sys
import json
import time
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from urllib.parse import unquote
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, load_environment
from loader import load_app_config, get_config_value


class GetUserCommentActivity(BaseTool):
    """
    Fetches comments authored by a specific user on other users' LinkedIn posts.

    Helps track engagement activity, conversation participation, and networking
    patterns by analyzing where and how a user comments on the platform.
    """

    user_urn: str = Field(
        ...,
        description="LinkedIn user URN or profile identifier whose comment activity to fetch"
    )

    page: int = Field(
        1,
        description="Page number for pagination (default: 1)"
    )

    page_size: int = Field(
        50,
        description="Number of comments per page (default: 50, max: 100)"
    )

    since_iso: Optional[str] = Field(
        None,
        description="Optional ISO 8601 datetime to fetch comments after this date"
    )

    include_post_context: bool = Field(
        True,
        description="Whether to include context about the posts being commented on (default: True)"
    )

    def run(self) -> str:
        """
        Fetches comment activity for the specified user.

        Returns:
            str: JSON string containing user's comment activity
                 Format: {
                     "comments": [
                         {
                             "comment_id": "...",
                             "text": "...",
                             "created_at": "2024-01-15T10:30:00Z",
                             "likes": 5,
                             "post_context": {
                                 "post_id": "...",
                                 "post_author": "...",
                                 "post_title": "...",
                                 "post_url": "..."
                             }
                         },
                         ...
                     ],
                     "activity_metrics": {
                         "total_comments": 125,
                         "comments_this_page": 50,
                         "average_likes_per_comment": 3.4,
                         "most_liked_comment": {...},
                         "top_engaged_authors": [...]
                     },
                     "pagination": {
                         "page": 1,
                         "page_size": 50,
                         "has_more": true
                     },
                     "metadata": {
                         "user_urn": "...",
                         "fetched_at": "2024-01-15T10:30:00Z"
                     }
                 }
        """
        try:
            # Load environment variables
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
            endpoint_path = endpoints.get("user_comments", "/api/v1/user/comments")

            # Validate inputs
            if self.page_size > 100:
                self.page_size = 100

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
                "pageSize": self.page_size,
                "includeContext": "true" if self.include_post_context else "false"
            }

            if self.since_iso:
                params["since"] = self.since_iso

            # Make API request with retry logic
            response_data = self._make_request_with_retry(base_url, headers, params)

            if not response_data:
                return json.dumps({
                    "error": "activity_fetch_failed",
                    "message": "Failed to fetch user comment activity",
                    "user_urn": self.user_urn
                })

            # Process comment activity data
            comments = self._process_comments(response_data.get("data", []))

            # Calculate activity metrics
            activity_metrics = self._calculate_metrics(comments, response_data)

            # Store comments to Firestore
            storage_results = self._store_comments_to_firestore(comments)

            # Extract pagination info
            pagination_info = response_data.get("pagination", {})
            has_more = pagination_info.get("hasMore", False)

            # Prepare response
            result = {
                "comments": comments,
                "activity_metrics": activity_metrics,
                "storage": {
                    "total_stored": storage_results["total_stored"],
                    "created": storage_results["created"],
                    "updated": storage_results["updated"],
                    "errors": storage_results["errors"]
                },
                "pagination": {
                    "page": self.page,
                    "page_size": self.page_size,
                    "has_more": has_more,
                    "total_available": pagination_info.get("totalCount", len(comments))
                },
                "metadata": {
                    "user_urn": self.user_urn,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "include_post_context": self.include_post_context
                }
            }

            if self.since_iso:
                result["metadata"]["since_filter"] = self.since_iso

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "comment_activity_failed",
                "message": str(e),
                "user_urn": self.user_urn
            }
            return json.dumps(error_result)

    def _process_comments(self, raw_comments: List[Dict]) -> List[Dict]:
        """
        Process and normalize comment data.

        Args:
            raw_comments: Raw comment data from API

        Returns:
            List[Dict]: Processed comments with normalized structure
        """
        processed = []

        for comment in raw_comments:
            # Extract activity metrics
            activity = comment.get("activity", {})
            likes = activity.get("num_likes", 0)
            replies_count = activity.get("num_comments", 0)

            # Extract comment URN and ID
            # URN format: urn:li:fsd_comment:(7382328312960012288,urn:li:activity:7381586262505201666)
            comment_urn = comment.get("urn", "")
            comment_id = ""
            if comment_urn and "(" in comment_urn:
                # Extract the first number inside parentheses
                parts = comment_urn.split("(")
                if len(parts) > 1:
                    comment_id = parts[1].split(",")[0]

            if not comment_id:
                comment_id = comment_urn

            processed_comment = {
                "comment_id": comment_id,
                "comment_urn": comment_urn,
                "text": comment.get("comment", ""),
                "created_at": comment.get("created_at", ""),
                "likes": likes,
                "replies_count": replies_count,
                "is_edited": comment.get("is_edited", False)
            }

            # Include post context if available
            if self.include_post_context and "post" in comment:
                post = comment["post"]
                post_author = post.get("author", {})

                processed_comment["post_context"] = {
                    "post_id": post.get("id", ""),
                    "post_author": post_author.get("full_name", ""),
                    "post_author_urn": post_author.get("urn", ""),
                    "post_author_headline": post_author.get("description", ""),
                    "post_text": post.get("text", "")[:200] + "..." if len(post.get("text", "")) > 200 else post.get("text", ""),
                    "post_url": f"https://www.linkedin.com/feed/update/{post.get('id', '')}",
                    "post_engagement": post.get("activity", {})
                }

            # Add engagement metrics for the comment
            processed_comment["engagement"] = {
                "likes": likes,
                "replies": replies_count,
                "total_engagement": likes + replies_count
            }

            processed.append(processed_comment)

        return processed

    def _calculate_metrics(self, comments: List[Dict], response_data: Dict) -> Dict:
        """
        Calculate activity metrics from processed comments.

        Args:
            comments: Processed comment list
            response_data: Raw API response for additional metrics

        Returns:
            Dict: Calculated activity metrics
        """
        if not comments:
            return {
                "total_comments": 0,
                "comments_this_page": 0,
                "average_likes_per_comment": 0
            }

        # Calculate average likes
        total_likes = sum(c.get("likes", 0) for c in comments)
        avg_likes = total_likes / len(comments) if comments else 0

        # Find most liked comment
        most_liked = max(comments, key=lambda c: c.get("likes", 0), default=None)

        # Track engagement by post author if context available
        author_engagement = {}
        if self.include_post_context:
            for comment in comments:
                if "post_context" in comment:
                    author = comment["post_context"].get("post_author", "Unknown")
                    if author:
                        author_engagement[author] = author_engagement.get(author, 0) + 1

        # Get top engaged authors
        top_authors = sorted(
            author_engagement.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]  # Top 5 authors

        metrics = {
            "total_comments": response_data.get("totalCount", len(comments)),
            "comments_this_page": len(comments),
            "average_likes_per_comment": round(avg_likes, 2),
            "total_likes_received": total_likes,
            "comments_with_replies": sum(1 for c in comments if c.get("replies_count", 0) > 0)
        }

        if most_liked and most_liked.get("likes", 0) > 0:
            metrics["most_liked_comment"] = {
                "comment_id": most_liked.get("comment_id"),
                "likes": most_liked.get("likes"),
                "text_preview": most_liked.get("text", "")[:100] + "..."
                    if len(most_liked.get("text", "")) > 100 else most_liked.get("text", "")
            }

        if top_authors:
            metrics["top_engaged_authors"] = [
                {"author": author, "comment_count": count}
                for author, count in top_authors
            ]

        # Add time-based metrics if we have timestamps
        if comments and comments[0].get("created_at"):
            try:
                # Get date range of comments
                dates = [c.get("created_at") for c in comments if c.get("created_at")]
                if dates:
                    metrics["earliest_comment"] = min(dates)
                    metrics["latest_comment"] = max(dates)
            except:
                pass  # Ignore date parsing errors

        return metrics

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

    def _store_profile_to_firestore(self, db, user_data: Dict) -> str:
        """
        Store user profile to Firestore with idempotent upsert.

        Args:
            db: Firestore client
            user_data: User profile data

        Returns:
            str: User URN (profile ID)
        """
        try:
            user_urn = user_data.get('urn', user_data.get('user_urn', ''))
            if not user_urn:
                return ''

            doc_ref = db.collection('linkedin_profiles').document(user_urn)
            existing_doc = doc_ref.get()

            # Split name into first and last
            full_name = self._decode_url_encoded_string(user_data.get('name', ''))
            name_parts = full_name.split(' ', 1) if full_name else ['', '']
            first_name = name_parts[0] if len(name_parts) > 0 else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            profile_data = {
                'urn': user_urn,
                'public_identifier': self._decode_url_encoded_string(user_data.get('public_identifier', '')),
                'first_name': first_name,
                'last_name': last_name,
                'headline': self._decode_url_encoded_string(user_data.get('headline', '')),
                'profile_url': self._decode_url_encoded_string(user_data.get('profile_url', '')),
                'updated_at': firestore.SERVER_TIMESTAMP
            }

            if not existing_doc.exists:
                profile_data['created_at'] = firestore.SERVER_TIMESTAMP
                doc_ref.set(profile_data)
            else:
                doc_ref.update(profile_data)

            return user_urn

        except Exception as e:
            print(f"Error storing profile {user_data.get('urn', 'unknown')}: {str(e)}")
            return ''

    def _store_comments_to_firestore(self, comments: List[Dict]) -> Dict[str, int]:
        """
        Store user comment activity to Firestore with idempotent upsert.

        Args:
            comments: List of comment dictionaries

        Returns:
            dict: Storage statistics with counts for created, updated, errors
        """
        created = 0
        updated = 0
        errors = 0

        if not comments:
            return {"total_stored": 0, "created": 0, "updated": 0, "errors": 0}

        try:
            db = self._initialize_firestore()

            # Store commenter profile once (the user whose activity we're fetching)
            commenter_profile = {
                'urn': self.user_urn,
                'user_urn': self.user_urn
            }
            commenter_urn = self._store_profile_to_firestore(db, commenter_profile)

            for comment in comments:
                try:
                    comment_id = comment.get("comment_id", "")
                    if not comment_id:
                        errors += 1
                        continue

                    # Create document reference
                    doc_ref = db.collection('linkedin_comments').document(comment_id)
                    existing_doc = doc_ref.get()

                    # Prepare comment data
                    comment_data = {
                        'comment_id': comment_id,
                        'author_urn': commenter_urn,  # The user whose activity we're tracking
                        'text': self._decode_url_encoded_string(comment.get('text', '')),
                        'created_at': comment.get('created_at', ''),
                        'likes': comment.get('likes', 0),
                        'replies_count': comment.get('replies_count', 0),
                        'is_edited': comment.get('is_edited', False),
                        'engagement': comment.get('engagement', {}),
                        'status': 'discovered',
                        'updated_at': firestore.SERVER_TIMESTAMP
                    }

                    # Add post context if available
                    if 'post_context' in comment:
                        comment_data['post_context'] = comment['post_context']

                    # Idempotent upsert
                    if not existing_doc.exists:
                        comment_data['created_at'] = firestore.SERVER_TIMESTAMP
                        doc_ref.set(comment_data)
                        created += 1
                    else:
                        doc_ref.update(comment_data)
                        updated += 1

                except Exception as e:
                    print(f"Error storing comment {comment.get('comment_id', 'unknown')}: {str(e)}")
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
                "errors": len(comments)
            }


if __name__ == "__main__":
    # Test the tool with ilke-oner's URN
    tool = GetUserCommentActivity(
        user_urn="ACoAAAHgd4AByBB_-yxtC25kj4Kmlw9ubw8Vmtk",  # ilke-oner
        page=1,
        page_size=25,
        include_post_context=True
    )
    print("Testing GetUserCommentActivity tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))