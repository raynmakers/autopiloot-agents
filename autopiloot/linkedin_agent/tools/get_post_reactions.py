"""
GetPostReactions tool for fetching reactions on LinkedIn posts via RapidAPI.
Provides aggregated reaction metrics and breakdown by reaction type.
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


class GetPostReactions(BaseTool):
    """
    Fetches reaction metrics for one or more LinkedIn posts using RapidAPI.

    Provides aggregated totals and breakdown by reaction type (like, celebrate,
    support, love, insightful, funny, etc.) for engagement analysis.
    """

    post_ids: List[str] = Field(
        ...,
        description="List of LinkedIn post IDs/URNs to fetch reactions for"
    )

    include_details: bool = Field(
        False,
        description="Whether to include individual reactor details (default: False, just aggregates)"
    )

    page: int = Field(
        1,
        description="Page number for detailed reactions if include_details=True (default: 1)"
    )

    page_size: int = Field(
        100,
        description="Number of detailed reactions per page if include_details=True (default: 100)"
    )

    def run(self) -> str:
        """
        Fetches reactions for the specified LinkedIn posts.

        Returns:
            str: JSON string containing reaction metrics grouped by post
                 Format: {
                     "reactions_by_post": {
                         "post_id_1": {
                             "total_reactions": 245,
                             "breakdown": {
                                 "like": 180,
                                 "celebrate": 32,
                                 "support": 15,
                                 "love": 10,
                                 "insightful": 5,
                                 "funny": 3
                             },
                             "engagement_rate": 0.045,
                             "top_reaction": "like",
                             "reactors": [...] // if include_details=True
                         },
                         "post_id_2": {...}
                     },
                     "aggregate_metrics": {
                         "total_reactions": 489,
                         "average_reactions_per_post": 244.5,
                         "most_engaging_post": "post_id_1",
                         "reaction_distribution": {...}
                     },
                     "metadata": {
                         "posts_analyzed": 2,
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

            if not self.post_ids:
                return json.dumps({
                    "error": "invalid_input",
                    "message": "No post IDs provided"
                })

            # Prepare API endpoint and headers
            base_url = f"https://{rapidapi_host}/post-reactions"
            headers = {
                "X-RapidAPI-Host": rapidapi_host,
                "X-RapidAPI-Key": rapidapi_key,
                "Accept": "application/json"
            }

            # Fetch reactions for each post
            reactions_by_post = {}
            total_reactions_all = 0
            reaction_distribution_all = {}

            for post_id in self.post_ids:
                # Build query parameters for this post
                params = {
                    "postId": post_id,
                    "aggregateOnly": "false" if self.include_details else "true"
                }

                if self.include_details:
                    params["page"] = self.page
                    params["pageSize"] = self.page_size

                # Make API request with retry logic
                response_data = self._make_request_with_retry(base_url, headers, params)

                if response_data:
                    # Process reaction data
                    post_reactions = self._process_reactions(response_data, post_id)
                    reactions_by_post[post_id] = post_reactions

                    # Update aggregates
                    total_reactions_all += post_reactions.get("total_reactions", 0)

                    # Merge reaction distributions
                    for reaction_type, count in post_reactions.get("breakdown", {}).items():
                        reaction_distribution_all[reaction_type] = \
                            reaction_distribution_all.get(reaction_type, 0) + count
                else:
                    # Failed to fetch reactions for this post
                    reactions_by_post[post_id] = {
                        "total_reactions": 0,
                        "breakdown": {},
                        "error": "fetch_failed"
                    }

                # Rate limiting between posts
                if len(self.post_ids) > 1:
                    time.sleep(0.5)  # 500ms delay between posts

            # Calculate aggregate metrics
            posts_with_data = [p for p in reactions_by_post.values() if "error" not in p]
            avg_reactions = total_reactions_all / len(posts_with_data) if posts_with_data else 0

            # Find most engaging post
            most_engaging = max(
                reactions_by_post.items(),
                key=lambda x: x[1].get("total_reactions", 0),
                default=(None, {})
            )[0]

            # Prepare response
            result = {
                "reactions_by_post": reactions_by_post,
                "aggregate_metrics": {
                    "total_reactions": total_reactions_all,
                    "average_reactions_per_post": round(avg_reactions, 2),
                    "most_engaging_post": most_engaging,
                    "reaction_distribution": reaction_distribution_all,
                    "posts_with_data": len(posts_with_data),
                    "posts_with_errors": len(self.post_ids) - len(posts_with_data)
                },
                "metadata": {
                    "posts_analyzed": len(self.post_ids),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "include_details": self.include_details
                }
            }

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "reactions_fetch_failed",
                "message": str(e),
                "post_ids": self.post_ids
            }
            return json.dumps(error_result)

    def _process_reactions(self, response_data: Dict, post_id: str) -> Dict:
        """
        Process and normalize reaction data from API response.

        Args:
            response_data: Raw API response
            post_id: Post identifier

        Returns:
            Dict: Processed reaction metrics
        """
        # Extract reaction totals and breakdown
        reactions_summary = response_data.get("summary", {})
        total_reactions = reactions_summary.get("totalReactions", 0)

        # Get reaction type breakdown
        breakdown = {}
        reaction_types = reactions_summary.get("reactionTypes", {})

        # Common LinkedIn reaction types
        for reaction_type in ["like", "celebrate", "support", "love", "insightful", "funny", "curious"]:
            count = reaction_types.get(reaction_type, 0)
            if count > 0:
                breakdown[reaction_type] = count

        # Calculate engagement rate if views data available
        views = response_data.get("views", 0)
        engagement_rate = (total_reactions / views) if views > 0 else 0

        # Find top reaction type
        top_reaction = max(breakdown.items(), key=lambda x: x[1], default=(None, 0))[0] if breakdown else None

        result = {
            "total_reactions": total_reactions,
            "breakdown": breakdown,
            "engagement_rate": round(engagement_rate, 4),
            "top_reaction": top_reaction
        }

        # Include detailed reactor information if requested
        if self.include_details and "reactors" in response_data:
            reactors = []
            for reactor in response_data.get("reactors", []):
                reactors.append({
                    "name": reactor.get("name", "Unknown"),
                    "headline": reactor.get("headline", ""),
                    "reaction_type": reactor.get("reactionType", "like"),
                    "profile_url": reactor.get("profileUrl", "")
                })
            result["reactors"] = reactors
            result["has_more_reactors"] = response_data.get("pagination", {}).get("hasMore", False)

        return result

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
    tool = GetPostReactions(
        post_ids=["urn:li:activity:7240371806548066304", "urn:li:activity:7240371806548066305"],
        include_details=False
    )
    print("Testing GetPostReactions tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))