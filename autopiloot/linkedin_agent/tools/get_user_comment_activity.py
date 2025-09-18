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
from datetime import datetime
from agency_swarm.tools import BaseTool
from pydantic import Field

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

            # Get RapidAPI credentials
            rapidapi_host = get_required_env_var("RAPIDAPI_LINKEDIN_HOST", "RapidAPI LinkedIn host")
            rapidapi_key = get_required_env_var("RAPIDAPI_LINKEDIN_KEY", "RapidAPI key for LinkedIn")

            # Validate inputs
            if self.page_size > 100:
                self.page_size = 100

            # Prepare API endpoint and headers
            base_url = f"https://{rapidapi_host}/user-comment-activity"
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

            # Extract pagination info
            pagination_info = response_data.get("pagination", {})
            has_more = pagination_info.get("hasMore", False)

            # Prepare response
            result = {
                "comments": comments,
                "activity_metrics": activity_metrics,
                "pagination": {
                    "page": self.page,
                    "page_size": self.page_size,
                    "has_more": has_more,
                    "total_available": pagination_info.get("totalCount", len(comments))
                },
                "metadata": {
                    "user_urn": self.user_urn,
                    "fetched_at": datetime.utcnow().isoformat() + "Z",
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
            processed_comment = {
                "comment_id": comment.get("id", ""),
                "text": comment.get("text", ""),
                "created_at": comment.get("createdAt", ""),
                "likes": comment.get("likes", 0),
                "replies_count": comment.get("repliesCount", 0),
                "is_edited": comment.get("isEdited", False)
            }

            # Include post context if available
            if self.include_post_context and "postContext" in comment:
                context = comment["postContext"]
                processed_comment["post_context"] = {
                    "post_id": context.get("postId", ""),
                    "post_author": context.get("authorName", ""),
                    "post_author_headline": context.get("authorHeadline", ""),
                    "post_title": context.get("title", ""),
                    "post_url": context.get("url", ""),
                    "post_date": context.get("publishedAt", "")
                }

            # Add engagement metrics for the comment
            processed_comment["engagement"] = {
                "likes": comment.get("likes", 0),
                "replies": comment.get("repliesCount", 0),
                "total_engagement": comment.get("likes", 0) + comment.get("repliesCount", 0)
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


if __name__ == "__main__":
    # Test the tool
    tool = GetUserCommentActivity(
        user_urn="alexhormozi",
        page=1,
        page_size=25,
        include_post_context=True
    )
    print("Testing GetUserCommentActivity tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))