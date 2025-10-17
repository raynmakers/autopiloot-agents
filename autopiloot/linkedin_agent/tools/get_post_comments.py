"""
GetPostComments tool for fetching comments on LinkedIn posts via RapidAPI.
Supports batch fetching of comments for multiple posts with pagination.
Stores comments to Firestore linked to their parent posts.
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
from firestore_client import get_firestore_client
from loader import get_config_value

# Import SaveIngestionRecord for audit logging
try:
    from linkedin_agent.tools.save_ingestion_record import SaveIngestionRecord
except ImportError:
    SaveIngestionRecord = None


class GetPostComments(BaseTool):
    """
    Fetches comments for one or more LinkedIn posts using RapidAPI.

    Handles batch processing of multiple posts and pagination for comments.
    Uses the Fresh LinkedIn Scraper API via RapidAPI to retrieve comments.
    Recursively processes nested replies to any depth.

    Comment nesting structure:
        Top-level comment
        ├── Reply 1
        │   └── Reply to Reply 1
        │       └── Nested Reply 3+ levels deep
        └── Reply 2
    """

    post_ids: List[str] = Field(
        ...,
        description="List of LinkedIn post IDs/URNs to fetch comments for"
    )

    page: int = Field(
        1,
        description="Page number for pagination per post (default: 1)"
    )

    page_size: int = Field(
        50,
        description="Number of comments per page per post (default: 50, max: 100)"
    )

    include_replies: bool = Field(
        True,
        description="Whether to include replies to comments (default: True)"
    )

    def run(self) -> str:
        """
        Fetches comments for the specified LinkedIn posts.

        Returns:
            str: JSON string containing comments grouped by post
                 Format: {
                     "comments_by_post": {
                         "post_id_1": {
                             "comments": [...],
                             "total_count": 45,
                             "has_more": false
                         },
                         "post_id_2": {...}
                     },
                     "metadata": {
                         "total_posts": 2,
                         "total_comments": 89,
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
            endpoint_path = endpoints.get("post_comments", "/api/v1/post/comments")

            # Validate inputs
            if self.page_size > 100:
                self.page_size = 100

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

            # Fetch comments for each post
            comments_by_post = {}
            total_comments = 0

            for post_id in self.post_ids:
                # Fetch all pages for this post
                all_comments = []
                current_page = 1
                has_more = True

                while has_more:
                    # Build query parameters for this page
                    params = {
                        "post_id": post_id,
                        "page": current_page,
                        "page_size": self.page_size
                    }

                    if self.include_replies:
                        params["include_replies"] = "true"

                    # Make API request with retry logic
                    response_data = self._make_request_with_retry(base_url, headers, params)

                    if response_data:
                        comments = response_data.get("data", [])

                        # If no comments returned, we're done
                        if not comments:
                            has_more = False
                            break

                        # Add to our collection
                        all_comments.extend(comments)

                        # Always try next page until we get zero results
                        # The API might return exactly page_size on last full page
                        current_page += 1

                        # Small delay between pages to respect rate limits
                        time.sleep(0.3)
                    else:
                        # Failed to fetch this page
                        has_more = False

                # Process all comments for this post
                if all_comments:
                    # Fetch additional paginated replies if needed
                    all_comments = self._fetch_paginated_replies(
                        post_id, all_comments, rapidapi_host, rapidapi_key, endpoints
                    )

                    processed_comments = self._process_comments(all_comments)

                    # Store comments to Firestore
                    storage_result = self._store_comments_to_firestore(post_id, processed_comments)

                    comments_by_post[post_id] = {
                        "comments": processed_comments,
                        "total_count": len(processed_comments),
                        "pages_fetched": current_page - 1 if current_page > 1 else 1,
                        "storage": storage_result
                    }
                    total_comments += len(processed_comments)
                else:
                    # No comments found for this post
                    comments_by_post[post_id] = {
                        "comments": [],
                        "total_count": 0,
                        "pages_fetched": 0,
                        "storage": {"total_stored": 0, "created": 0, "updated": 0, "errors": 0}
                    }

                # Rate limiting between posts
                if len(self.post_ids) > 1:
                    time.sleep(0.5)  # 500ms delay between posts

            # Prepare response
            result = {
                "comments_by_post": comments_by_post,
                "metadata": {
                    "total_posts": len(self.post_ids),
                    "total_comments": total_comments,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "page_size": self.page_size,
                    "include_replies": self.include_replies,
                    "pagination": "automatic"  # Fetches all pages automatically
                }
            }

            # Calculate total storage stats across all posts
            total_stored = sum(p.get("storage", {}).get("total_stored", 0) for p in comments_by_post.values())
            total_created = sum(p.get("storage", {}).get("created", 0) for p in comments_by_post.values())
            total_updated = sum(p.get("storage", {}).get("updated", 0) for p in comments_by_post.values())
            total_errors = sum(p.get("storage", {}).get("errors", 0) for p in comments_by_post.values())

            # Save audit record
            processing_duration = time.time() - start_time
            self._save_audit_record(
                run_id=run_id,
                ingestion_stats={
                    "comments_processed": total_comments,
                    "comments_stored": total_stored,
                    "comments_created": total_created,
                    "comments_updated": total_updated,
                    "storage_errors": total_errors,
                    "posts_queried": len(self.post_ids)
                },
                processing_duration=processing_duration,
                errors=errors_list
            )

            return json.dumps(result)

        except Exception as e:
            # Track error
            error_info = {
                "type": "comments_fetch_failed",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            errors_list.append(error_info)

            # Save audit record with error
            processing_duration = time.time() - start_time
            self._save_audit_record(
                run_id=run_id,
                ingestion_stats={
                    "comments_processed": 0,
                    "comments_stored": 0,
                    "posts_queried": len(self.post_ids) if self.post_ids else 0
                },
                processing_duration=processing_duration,
                errors=errors_list
            )

            error_result = {
                "error": "comments_fetch_failed",
                "message": str(e),
                "post_ids": self.post_ids
            }
            return json.dumps(error_result)

    def _fetch_paginated_replies(
        self,
        post_id: str,
        comments: List[Dict],
        rapidapi_host: str,
        rapidapi_key: str,
        endpoints: Dict
    ) -> List[Dict]:
        """
        Fetch additional paginated replies for comments that have more replies than returned.

        Args:
            post_id: Post ID these comments belong to
            comments: List of comments with initial replies
            rapidapi_host: RapidAPI host
            rapidapi_key: RapidAPI key
            endpoints: Endpoint paths dictionary

        Returns:
            List[Dict]: Comments with all replies fetched
        """
        if not self.include_replies:
            return comments

        # Get replies endpoint
        replies_endpoint = endpoints.get("post_comment_replies", "/api/v1/post/comments/replies")
        replies_url = f"https://{rapidapi_host}{replies_endpoint}"

        headers = {
            "X-RapidAPI-Host": rapidapi_host,
            "X-RapidAPI-Key": rapidapi_key,
            "Accept": "application/json"
        }

        # Check each comment for paginated replies
        for comment in comments:
            num_replies = comment.get("num_replies", 0)
            current_replies = len(comment.get("replies", []))

            # If comment has more replies than returned, fetch them
            if num_replies > current_replies and "previous_replies_token" in comment:
                comment_id = comment.get("id", "")
                token = comment.get("previous_replies_token", "")

                # Fetch additional replies
                params = {
                    "post_id": post_id,
                    "comment_id": comment_id,
                    "previous_replies_token": token
                }

                response_data = self._make_request_with_retry(replies_url, headers, params)

                if response_data and "data" in response_data:
                    additional_replies = response_data.get("data", [])

                    # Merge with existing replies
                    if "replies" not in comment:
                        comment["replies"] = []
                    comment["replies"].extend(additional_replies)

                # Small delay to respect rate limits
                time.sleep(0.3)

        return comments

    def _process_comments(self, comments: List[Dict]) -> List[Dict]:
        """
        Process and normalize comment data.

        Args:
            comments: Raw comments from API

        Returns:
            List[Dict]: Processed comments with normalized structure
        """
        processed = []

        for comment in comments:
            processed_comment = self._process_single_comment(comment, is_reply=False)
            processed.append(processed_comment)

        return processed

    def _process_single_comment(self, comment: Dict, is_reply: bool = False) -> Dict:
        """
        Process a single comment with recursive reply handling.

        Args:
            comment: Raw comment data from API
            is_reply: Whether this is a reply to another comment

        Returns:
            Dict: Processed comment with nested replies
        """
        # Get commenter info
        commenter = comment.get("commenter", {})

        # Calculate total likes from reaction_counts
        reaction_counts = comment.get("reaction_counts", [])
        total_reactions = sum(r.get("count", 0) for r in reaction_counts)

        processed_comment = {
            "comment_id": comment.get("id", ""),
            "author": {
                "name": commenter.get("name", "Unknown"),
                "headline": commenter.get("description", ""),
                "profile_url": commenter.get("url", "")
            },
            "text": comment.get("comment", ""),
            "likes": total_reactions,
            "replies_count": comment.get("num_replies", 0),
            "created_at": comment.get("created_at", ""),
            "is_reply": is_reply
        }

        # Recursively process nested replies
        if self.include_replies and "replies" in comment:
            replies = comment.get("replies", [])
            processed_replies = []
            for reply in replies:
                # Recursive call to handle nested replies
                processed_reply = self._process_single_comment(reply, is_reply=True)
                processed_replies.append(processed_reply)
            processed_comment["replies"] = processed_replies

        return processed_comment

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
            author: Author/profile dictionary from comment

        Returns:
            str: Author profile ID extracted from URL
        """
        try:
            # Comments have profile_url instead of URN, use that as ID
            profile_url = self._decode_url_encoded_string(author.get('profile_url', ''))
            if not profile_url:
                return ''

            # Extract identifier from URL (e.g., "https://www.linkedin.com/in/ilke-oner" -> "ilke-oner")
            profile_id = profile_url.rstrip('/').split('/')[-1] if profile_url else ''
            if not profile_id:
                return profile_url

            # Create document reference using profile ID
            doc_ref = db.collection('linkedin_profiles').document(profile_id)
            existing_doc = doc_ref.get()

            # Split name into first and last name
            full_name = self._decode_url_encoded_string(author.get('name', ''))
            name_parts = full_name.split(' ', 1) if full_name else ['', '']
            first_name = name_parts[0] if len(name_parts) > 0 else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            # Prepare profile data with URL decoding
            profile_data = {
                'public_identifier': profile_id,
                'first_name': first_name,
                'last_name': last_name,
                'headline': self._decode_url_encoded_string(author.get('headline', '')),
                'profile_url': profile_url,
                'updated_at': firestore.SERVER_TIMESTAMP
            }

            # Idempotent upsert
            if not existing_doc.exists:
                profile_data['created_at'] = firestore.SERVER_TIMESTAMP
                doc_ref.set(profile_data)
            else:
                doc_ref.update(profile_data)

            return profile_id

        except Exception as e:
            print(f"Error storing profile {author.get('profile_url', 'unknown')}: {str(e)}")
            return ''

    def _store_comments_to_firestore(self, post_id: str, comments: List[Dict]) -> Dict[str, int]:
        """
        Store LinkedIn comments to Firestore with post_id linking.
        Extracts author profiles and stores them separately.

        Args:
            post_id: LinkedIn post ID these comments belong to
            comments: List of processed comment dictionaries

        Returns:
            dict: Storage statistics with counts for created, updated, errors
        """
        created = 0
        updated = 0
        errors = 0

        if not comments:
            return {"total_stored": 0, "created": 0, "updated": 0, "errors": 0}

        try:
            db = get_firestore_client()

            # Flatten nested comments for storage (recursively)
            all_comments = self._flatten_comments(comments)

            for comment in all_comments:
                try:
                    # Use comment_id as document ID, or generate one if missing
                    comment_id = comment.get("comment_id") or f"{post_id}_{len(all_comments)}_{datetime.now(timezone.utc).timestamp()}"

                    if not comment_id:
                        errors += 1
                        continue

                    # Store author profile separately and get profile ID
                    author = comment.get('author', {})
                    author_profile_id = self._store_profile_to_firestore(db, author) if author else ''

                    # Create document reference
                    doc_ref = db.collection('linkedin_comments').document(comment_id)
                    existing_doc = doc_ref.get()

                    # Prepare comment data with author reference only
                    comment_data = {
                        'comment_id': comment_id,
                        'post_id': post_id,  # Link to parent post
                        'author_profile_id': author_profile_id,  # Reference to linkedin_profiles
                        'text': comment.get('text', ''),
                        'likes': comment.get('likes', 0),
                        'replies_count': comment.get('replies_count', 0),
                        'created_at': comment.get('created_at', ''),
                        'is_reply': comment.get('is_reply', False),
                        'status': 'discovered',
                        'updated_at': firestore.SERVER_TIMESTAMP
                    }

                    # Idempotent upsert
                    if not existing_doc.exists:
                        comment_data['created_at_firestore'] = firestore.SERVER_TIMESTAMP
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

    def _flatten_comments(self, comments: List[Dict], flattened: Optional[List[Dict]] = None) -> List[Dict]:
        """
        Recursively flatten nested comment structure for storage.

        Args:
            comments: List of comments (may contain nested replies)
            flattened: Accumulator for flattened comments

        Returns:
            List[Dict]: Flat list of all comments including nested replies
        """
        if flattened is None:
            flattened = []

        for comment in comments:
            # Add this comment (without replies key to avoid circular storage)
            comment_copy = {k: v for k, v in comment.items() if k != 'replies'}
            flattened.append(comment_copy)

            # Recursively flatten nested replies
            if 'replies' in comment and comment['replies']:
                self._flatten_comments(comment['replies'], flattened)

        return flattened

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
            # Use first post_id as profile identifier
            profile_id = self.post_ids[0] if self.post_ids else "unknown"

            audit_tool = SaveIngestionRecord(
                run_id=run_id,
                profile_identifier=profile_id,
                content_type="comments",
                ingestion_stats=ingestion_stats,
                processing_duration_seconds=processing_duration,
                errors=errors if errors else None
            )
            audit_tool.run()
        except Exception as e:
            # Don't fail the main operation if audit logging fails
            print(f"Warning: Failed to save audit record: {str(e)}")


if __name__ == "__main__":
    # Test the tool with numeric post IDs (not URNs)
    tool = GetPostComments(
        post_ids=["7373607106899263488","7363442070256062464"],  # ilke-oner's post ID
        page=1,
        page_size=50,  # Default page size for full test
        include_replies=True
    )
    print("Testing GetPostComments tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))