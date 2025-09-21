"""
NormalizeLinkedInContent tool for standardizing LinkedIn data into a consistent schema.
Prepares content for Zep storage and strategy analysis with uniform structure.
"""

import json
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field


class NormalizeLinkedInContent(BaseTool):
    """
    Normalizes LinkedIn posts, comments, and reactions into a standard schema.

    Creates consistent data structure for storage in Zep GraphRAG and enables
    cross-content analysis with standardized fields and metrics.
    """

    posts: Optional[List[Dict]] = Field(
        None,
        description="Raw LinkedIn posts data to normalize"
    )

    comments: Optional[List[Dict]] = Field(
        None,
        description="Raw LinkedIn comments data to normalize"
    )

    reactions: Optional[Dict] = Field(
        None,
        description="Raw LinkedIn reactions data to normalize"
    )

    include_metadata: bool = Field(
        True,
        description="Whether to include processing metadata (default: True)"
    )

    def run(self) -> str:
        """
        Normalizes LinkedIn content into standard schema.

        Returns:
            str: JSON string containing normalized content
                 Format: {
                     "normalized_posts": [...],
                     "normalized_comments": [...],
                     "normalized_reactions": {...},
                     "processing_summary": {
                         "posts_processed": 10,
                         "comments_processed": 25,
                         "reactions_processed": 5,
                         "normalization_timestamp": "2024-01-15T10:30:00Z"
                     },
                     "schema_version": "1.0"
                 }
        """
        try:
            result = {
                "schema_version": "1.0",
                "processing_summary": {
                    "posts_processed": 0,
                    "comments_processed": 0,
                    "reactions_processed": 0,
                    "normalization_timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

            # Normalize posts if provided
            if self.posts:
                normalized_posts = self._normalize_posts(self.posts)
                result["normalized_posts"] = normalized_posts
                result["processing_summary"]["posts_processed"] = len(normalized_posts)

            # Normalize comments if provided
            if self.comments:
                normalized_comments = self._normalize_comments(self.comments)
                result["normalized_comments"] = normalized_comments
                result["processing_summary"]["comments_processed"] = len(normalized_comments)

            # Normalize reactions if provided
            if self.reactions:
                normalized_reactions = self._normalize_reactions(self.reactions)
                result["normalized_reactions"] = normalized_reactions
                result["processing_summary"]["reactions_processed"] = len(
                    normalized_reactions.get("posts_with_reactions", [])
                )

            # Add metadata if requested
            if self.include_metadata:
                result["metadata"] = self._generate_metadata(result)

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "normalization_failed",
                "message": str(e),
                "input_summary": {
                    "posts_count": len(self.posts) if self.posts else 0,
                    "comments_count": len(self.comments) if self.comments else 0,
                    "has_reactions": bool(self.reactions)
                }
            }
            return json.dumps(error_result)

    def _normalize_posts(self, posts: List[Dict]) -> List[Dict]:
        """
        Normalize posts to standard schema.

        Args:
            posts: Raw post data

        Returns:
            List[Dict]: Normalized posts
        """
        normalized = []

        for post in posts:
            # Generate unique content ID
            post_id = post.get("id") or post.get("urn", "")
            content_hash = self._generate_content_hash(post_id, "post")

            normalized_post = {
                # Identifiers
                "id": post_id,
                "content_hash": content_hash,
                "type": "post",

                # Content
                "text": post.get("text", ""),
                "title": post.get("title", ""),
                "url": post.get("url", ""),

                # Author
                "author": {
                    "name": post.get("authorName", ""),
                    "headline": post.get("authorHeadline", ""),
                    "profile_url": post.get("authorProfileUrl", ""),
                    "urn": post.get("authorUrn", "")
                },

                # Timestamps
                "created_at": post.get("createdAt") or post.get("publishedAt", ""),
                "updated_at": post.get("updatedAt", ""),

                # Engagement metrics
                "metrics": {
                    "likes": post.get("likes", 0),
                    "comments": post.get("commentsCount", 0),
                    "shares": post.get("shares", 0),
                    "views": post.get("views", 0),
                    "engagement_rate": self._calculate_engagement_rate(post)
                },

                # Media
                "media": self._extract_media(post),

                # Tags and mentions
                "tags": post.get("tags", []),
                "mentions": post.get("mentions", []),

                # Processing metadata
                "normalized_at": datetime.now(timezone.utc).isoformat()
            }

            normalized.append(normalized_post)

        return normalized

    def _normalize_comments(self, comments: List[Dict]) -> List[Dict]:
        """
        Normalize comments to standard schema.

        Args:
            comments: Raw comment data

        Returns:
            List[Dict]: Normalized comments
        """
        normalized = []

        for comment in comments:
            comment_id = comment.get("id") or comment.get("comment_id", "")
            content_hash = self._generate_content_hash(comment_id, "comment")

            normalized_comment = {
                # Identifiers
                "id": comment_id,
                "content_hash": content_hash,
                "type": "comment",
                "parent_post_id": comment.get("postId") or comment.get("post_id", ""),
                "parent_comment_id": comment.get("parentCommentId", ""),

                # Content
                "text": comment.get("text", ""),

                # Author
                "author": {
                    "name": comment.get("authorName") or comment.get("author", {}).get("name", ""),
                    "headline": comment.get("authorHeadline") or comment.get("author", {}).get("headline", ""),
                    "profile_url": comment.get("authorProfileUrl") or comment.get("author", {}).get("profile_url", ""),
                },

                # Timestamps
                "created_at": comment.get("createdAt") or comment.get("created_at", ""),

                # Engagement
                "metrics": {
                    "likes": comment.get("likes", 0),
                    "replies": comment.get("repliesCount") or comment.get("replies_count", 0),
                    "is_reply": comment.get("isReply") or comment.get("is_reply", False)
                },

                # Processing metadata
                "normalized_at": datetime.now(timezone.utc).isoformat()
            }

            # Handle nested replies if present
            if "replies" in comment and comment["replies"]:
                normalized_comment["replies"] = self._normalize_comments(comment["replies"])

            normalized.append(normalized_comment)

        return normalized

    def _normalize_reactions(self, reactions: Dict) -> Dict:
        """
        Normalize reactions data to standard schema.

        Args:
            reactions: Raw reactions data

        Returns:
            Dict: Normalized reactions
        """
        normalized = {
            "summary": {
                "total_reactions": 0,
                "unique_posts": 0,
                "reaction_types": {}
            },
            "posts_with_reactions": []
        }

        # Handle reactions by post structure
        if "reactions_by_post" in reactions:
            for post_id, post_reactions in reactions["reactions_by_post"].items():
                if isinstance(post_reactions, dict) and "error" not in post_reactions:
                    normalized_post_reactions = {
                        "post_id": post_id,
                        "total": post_reactions.get("total_reactions", 0),
                        "breakdown": post_reactions.get("breakdown", {}),
                        "engagement_rate": post_reactions.get("engagement_rate", 0),
                        "top_reaction": post_reactions.get("top_reaction", ""),
                        "normalized_at": datetime.now(timezone.utc).isoformat()
                    }

                    normalized["posts_with_reactions"].append(normalized_post_reactions)

                    # Update summary
                    normalized["summary"]["total_reactions"] += normalized_post_reactions["total"]
                    for reaction_type, count in normalized_post_reactions["breakdown"].items():
                        normalized["summary"]["reaction_types"][reaction_type] = \
                            normalized["summary"]["reaction_types"].get(reaction_type, 0) + count

        normalized["summary"]["unique_posts"] = len(normalized["posts_with_reactions"])

        # Add aggregate metrics if present
        if "aggregate_metrics" in reactions:
            normalized["aggregate_metrics"] = reactions["aggregate_metrics"]

        return normalized

    def _generate_content_hash(self, content_id: str, content_type: str) -> str:
        """
        Generate a unique hash for content deduplication.

        Args:
            content_id: Original content identifier
            content_type: Type of content (post, comment, etc.)

        Returns:
            str: SHA-256 hash of the content identifier
        """
        hash_input = f"{content_type}:{content_id}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def _calculate_engagement_rate(self, post: Dict) -> float:
        """
        Calculate engagement rate for a post.

        Args:
            post: Post data with metrics

        Returns:
            float: Engagement rate (0-1)
        """
        views = post.get("views", 0)
        if views == 0:
            return 0.0

        engagements = (
            post.get("likes", 0) +
            post.get("commentsCount", 0) +
            post.get("shares", 0)
        )

        return round(engagements / views, 4) if views > 0 else 0.0

    def _extract_media(self, post: Dict) -> List[Dict]:
        """
        Extract and normalize media information from a post.

        Args:
            post: Post data

        Returns:
            List[Dict]: Normalized media items
        """
        media = []

        # Extract images
        if "images" in post and post["images"]:
            for image in post["images"]:
                media.append({
                    "type": "image",
                    "url": image.get("url", ""),
                    "alt_text": image.get("altText", "")
                })

        # Extract videos
        if "videos" in post and post["videos"]:
            for video in post["videos"]:
                media.append({
                    "type": "video",
                    "url": video.get("url", ""),
                    "duration": video.get("duration", 0),
                    "thumbnail": video.get("thumbnail", "")
                })

        # Extract article/link
        if "articleUrl" in post:
            media.append({
                "type": "article",
                "url": post["articleUrl"],
                "title": post.get("articleTitle", ""),
                "description": post.get("articleDescription", "")
            })

        return media

    def _generate_metadata(self, result: Dict) -> Dict:
        """
        Generate processing metadata.

        Args:
            result: Processing result

        Returns:
            Dict: Metadata about the normalization
        """
        metadata = {
            "total_items_processed": (
                result["processing_summary"]["posts_processed"] +
                result["processing_summary"]["comments_processed"] +
                result["processing_summary"]["reactions_processed"]
            ),
            "has_posts": "normalized_posts" in result,
            "has_comments": "normalized_comments" in result,
            "has_reactions": "normalized_reactions" in result,
            "schema_version": result["schema_version"],
            "processing_time": datetime.now(timezone.utc).isoformat()
        }

        # Add content statistics
        if "normalized_posts" in result:
            metadata["posts_stats"] = {
                "total": len(result["normalized_posts"]),
                "with_media": sum(1 for p in result["normalized_posts"] if p.get("media")),
                "with_high_engagement": sum(
                    1 for p in result["normalized_posts"]
                    if p.get("metrics", {}).get("engagement_rate", 0) > 0.05
                )
            }

        if "normalized_comments" in result:
            metadata["comments_stats"] = {
                "total": len(result["normalized_comments"]),
                "replies": sum(
                    1 for c in result["normalized_comments"]
                    if c.get("metrics", {}).get("is_reply", False)
                ),
                "with_likes": sum(
                    1 for c in result["normalized_comments"]
                    if c.get("metrics", {}).get("likes", 0) > 0
                )
            }

        return metadata


if __name__ == "__main__":
    # Test the tool
    test_posts = [{
        "id": "urn:li:activity:12345",
        "text": "Test post content",
        "authorName": "John Doe",
        "likes": 100,
        "commentsCount": 25,
        "views": 1000
    }]

    test_comments = [{
        "id": "comment_123",
        "text": "Great post!",
        "authorName": "Jane Smith",
        "likes": 5
    }]

    tool = NormalizeLinkedInContent(
        posts=test_posts,
        comments=test_comments,
        include_metadata=True
    )
    print("Testing NormalizeLinkedInContent tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))