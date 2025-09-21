"""
GetPostComments tool for fetching comments on LinkedIn posts via RapidAPI.
Supports batch fetching of comments for multiple posts with pagination.
"""

import os
import sys
import json
import time
import requests
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, load_environment
from loader import load_app_config, get_config_value


class GetPostComments(BaseTool):
    """
    Fetches comments for one or more LinkedIn posts using RapidAPI.

    Handles batch processing of multiple posts and pagination for comments.
    Uses the Fresh LinkedIn Scraper API via RapidAPI to retrieve comments.
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
        try:
            # Load environment variables
            load_environment()

            # Get RapidAPI credentials
            rapidapi_host = get_required_env_var("RAPIDAPI_LINKEDIN_HOST", "RapidAPI LinkedIn host")
            rapidapi_key = get_required_env_var("RAPIDAPI_LINKEDIN_KEY", "RapidAPI key for LinkedIn")

            # Validate inputs
            if self.page_size > 100:
                self.page_size = 100

            if not self.post_ids:
                return json.dumps({
                    "error": "invalid_input",
                    "message": "No post IDs provided"
                })

            # Prepare API endpoint and headers
            base_url = f"https://{rapidapi_host}/post-comments"
            headers = {
                "X-RapidAPI-Host": rapidapi_host,
                "X-RapidAPI-Key": rapidapi_key,
                "Accept": "application/json"
            }

            # Fetch comments for each post
            comments_by_post = {}
            total_comments = 0

            for post_id in self.post_ids:
                # Build query parameters for this post
                params = {
                    "postId": post_id,
                    "page": self.page,
                    "pageSize": self.page_size
                }

                if self.include_replies:
                    params["includeReplies"] = "true"

                # Make API request with retry logic
                response_data = self._make_request_with_retry(base_url, headers, params)

                if response_data:
                    comments = response_data.get("data", [])
                    pagination = response_data.get("pagination", {})

                    # Process comments to extract key information
                    processed_comments = self._process_comments(comments)

                    comments_by_post[post_id] = {
                        "comments": processed_comments,
                        "total_count": len(processed_comments),
                        "has_more": pagination.get("hasMore", False),
                        "page": self.page
                    }
                    total_comments += len(processed_comments)
                else:
                    # Failed to fetch comments for this post
                    comments_by_post[post_id] = {
                        "comments": [],
                        "total_count": 0,
                        "has_more": False,
                        "error": "fetch_failed"
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
                    "page": self.page,
                    "page_size": self.page_size,
                    "include_replies": self.include_replies
                }
            }

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "comments_fetch_failed",
                "message": str(e),
                "post_ids": self.post_ids
            }
            return json.dumps(error_result)

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
            processed_comment = {
                "comment_id": comment.get("id", ""),
                "author": {
                    "name": comment.get("authorName", "Unknown"),
                    "headline": comment.get("authorHeadline", ""),
                    "profile_url": comment.get("authorProfileUrl", "")
                },
                "text": comment.get("text", ""),
                "likes": comment.get("likes", 0),
                "replies_count": comment.get("repliesCount", 0),
                "created_at": comment.get("createdAt", ""),
                "is_reply": comment.get("isReply", False)
            }

            # Include replies if present
            if self.include_replies and "replies" in comment:
                processed_comment["replies"] = self._process_comments(comment["replies"])

            processed.append(processed_comment)

        return processed

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
    tool = GetPostComments(
        post_ids=["urn:li:activity:7240371806548066304", "urn:li:activity:7240371806548066305"],
        page=1,
        page_size=10,
        include_replies=True
    )
    print("Testing GetPostComments tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))