"""
ComputeLinkedInStats tool for calculating comprehensive analytics from LinkedIn data.
Analyzes posts, comments, reactions, and engagement patterns for strategy insights.
Works with data from get_user_posts, get_post_comments, and get_post_reactions tools.
"""

import json
import statistics
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.time_utils import parse_iso8601_z, to_iso8601_z, now, timezone
from collections import Counter, defaultdict
from agency_swarm.tools import BaseTool
from pydantic import Field


class ComputeLinkedInStats(BaseTool):
    """
    Computes comprehensive statistics and analytics from LinkedIn content.

    Analyzes posts, comments, reactions, and reposts to provide insights for
    content strategy and performance optimization.

    Input data format matches output from:
    - get_user_posts.py (posts with activity object)
    - get_post_comments.py (comments with direct fields)
    - get_post_reactions.py (top_reactors format)
    """

    posts: Optional[List[Dict]] = Field(
        None,
        description="LinkedIn posts data from get_user_posts tool"
    )

    comments: Optional[List[Dict]] = Field(
        None,
        description="LinkedIn comments data from get_post_comments tool"
    )

    reactions: Optional[List[Dict]] = Field(
        None,
        description="Top reactors data from get_post_reactions tool"
    )

    include_trends: bool = Field(
        True,
        description="Whether to calculate time-based trends (default: True)"
    )

    def run(self) -> str:
        """
        Computes comprehensive LinkedIn statistics and analytics.

        Returns:
            str: JSON string with statistical analysis
                 Format: {
                     "overview": {...},
                     "engagement_stats": {...},
                     "content_analysis": {...},
                     "reaction_insights": {...},
                     "trends": {...}
                 }
        """
        try:
            result = {
                "analysis_metadata": {
                    "computed_at": datetime.now(timezone.utc).isoformat(),
                    "data_sources": self._get_data_sources()
                }
            }

            # Calculate overview statistics
            result["overview"] = self._calculate_overview()

            # Calculate engagement statistics
            if self.posts or self.comments:
                result["engagement_stats"] = self._calculate_engagement_stats()

            # Analyze content patterns
            if self.posts:
                result["content_analysis"] = self._analyze_content_patterns()

            # Analyze reactions and top engagers
            if self.reactions:
                result["reaction_insights"] = self._analyze_reactions()

            # Calculate trends
            if self.include_trends and self.posts:
                result["trends"] = self._calculate_trends()

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "stats_computation_failed",
                "message": str(e),
                "data_available": {
                    "posts": len(self.posts) if self.posts else 0,
                    "comments": len(self.comments) if self.comments else 0,
                    "reactions": len(self.reactions) if self.reactions else 0
                }
            }
            return json.dumps(error_result)

    def _get_data_sources(self) -> List[str]:
        """Identify available data sources."""
        sources = []
        if self.posts:
            sources.append(f"posts ({len(self.posts)})")
        if self.comments:
            sources.append(f"comments ({len(self.comments)})")
        if self.reactions:
            sources.append(f"top_reactors ({len(self.reactions)})")
        return sources

    def _calculate_overview(self) -> Dict:
        """Calculate high-level overview statistics."""
        overview = {}

        if self.posts:
            overview["total_posts"] = len(self.posts)

            # Count unique authors
            authors = set()
            for post in self.posts:
                if post.get("author_urn"):
                    authors.add(post.get("author_urn"))
            overview["unique_authors"] = len(authors)

            # Sum total engagement
            total_likes = sum(
                post.get("activity", {}).get("num_likes", 0)
                for post in self.posts
            )
            total_comments = sum(
                post.get("activity", {}).get("num_comments", 0)
                for post in self.posts
            )
            total_shares = sum(
                post.get("activity", {}).get("num_shares", 0)
                for post in self.posts
            )

            overview["total_likes"] = total_likes
            overview["total_comments"] = total_comments
            overview["total_shares"] = total_shares
            overview["total_engagement"] = total_likes + total_comments + total_shares

        if self.comments:
            overview["total_comment_records"] = len(self.comments)
            overview["total_comment_likes"] = sum(
                c.get("likes", 0) for c in self.comments
            )

        if self.reactions:
            overview["unique_reactors"] = len(self.reactions)
            overview["total_reactions_tracked"] = sum(
                r.get("total_reactions", 0) for r in self.reactions
            )

        # Calculate analysis period
        dates = []
        if self.posts:
            dates.extend([p.get("posted_at") for p in self.posts if p.get("posted_at")])

        if dates:
            dates = [d for d in dates if d]
            if dates:
                try:
                    start_dt = min(dates)
                    end_dt = max(dates)
                    overview["analysis_period"] = {
                        "start": start_dt,
                        "end": end_dt,
                        "days_covered": (
                            parse_iso8601_z(end_dt) -
                            parse_iso8601_z(start_dt)
                        ).days
                    }
                except:
                    pass

        return overview

    def _calculate_engagement_stats(self) -> Dict:
        """Calculate detailed engagement statistics."""
        stats = {}

        if self.posts:
            # Extract engagement metrics from activity object
            likes = [p.get("activity", {}).get("num_likes", 0) for p in self.posts]
            comments = [p.get("activity", {}).get("num_comments", 0) for p in self.posts]
            shares = [p.get("activity", {}).get("num_shares", 0) for p in self.posts]

            stats["post_metrics"] = {
                "average_likes": round(statistics.mean(likes), 2) if likes else 0,
                "median_likes": statistics.median(likes) if likes else 0,
                "max_likes": max(likes) if likes else 0,
                "min_likes": min(likes) if likes else 0,
                "average_comments": round(statistics.mean(comments), 2) if comments else 0,
                "median_comments": statistics.median(comments) if comments else 0,
                "average_shares": round(statistics.mean(shares), 2) if shares else 0,
                "median_shares": statistics.median(shares) if shares else 0
            }

            # Top performing posts
            sorted_posts = sorted(
                self.posts,
                key=lambda p: p.get("activity", {}).get("num_likes", 0),
                reverse=True
            )

            stats["top_performing_posts"] = [
                {
                    "post_id": p.get("post_id"),
                    "text_preview": (p.get("text", "")[:100] + "...") if len(p.get("text", "")) > 100 else p.get("text", ""),
                    "likes": p.get("activity", {}).get("num_likes", 0),
                    "comments": p.get("activity", {}).get("num_comments", 0),
                    "shares": p.get("activity", {}).get("num_shares", 0),
                    "total_engagement": (
                        p.get("activity", {}).get("num_likes", 0) +
                        p.get("activity", {}).get("num_comments", 0) +
                        p.get("activity", {}).get("num_shares", 0)
                    ),
                    "posted_at": p.get("posted_at"),
                    "post_url": p.get("post_url")
                } for p in sorted_posts[:10]
            ]

            # Reaction type analysis
            reaction_types_count = defaultdict(int)
            for post in self.posts:
                reaction_counts = post.get("activity", {}).get("reaction_counts", [])
                for reaction in reaction_counts:
                    reaction_type = reaction.get("type", "LIKE")
                    count = reaction.get("count", 0)
                    reaction_types_count[reaction_type] += count

            if reaction_types_count:
                total_reactions = sum(reaction_types_count.values())
                stats["reaction_breakdown"] = {
                    reaction_type: {
                        "count": count,
                        "percentage": round((count / total_reactions) * 100, 1) if total_reactions > 0 else 0
                    } for reaction_type, count in reaction_types_count.items()
                }

        if self.comments:
            # Comment engagement
            comment_likes = [c.get("likes", 0) for c in self.comments]

            stats["comment_metrics"] = {
                "total_comments": len(self.comments),
                "average_likes_per_comment": round(statistics.mean(comment_likes), 2) if comment_likes else 0,
                "median_likes_per_comment": statistics.median(comment_likes) if comment_likes else 0,
                "comments_with_likes": sum(1 for likes in comment_likes if likes > 0),
                "like_rate": round(
                    sum(1 for likes in comment_likes if likes > 0) / len(comment_likes),
                    3
                ) if comment_likes else 0
            }

            # Top comments by likes
            sorted_comments = sorted(
                self.comments,
                key=lambda c: c.get("likes", 0),
                reverse=True
            )

            stats["top_comments"] = [
                {
                    "comment_id": c.get("comment_id"),
                    "text_preview": (c.get("text", "")[:80] + "...") if len(c.get("text", "")) > 80 else c.get("text", ""),
                    "likes": c.get("likes", 0),
                    "author_profile_id": c.get("author_profile_id"),
                    "created_at": c.get("created_at")
                } for c in sorted_comments[:5]
            ]

        return stats

    def _analyze_content_patterns(self) -> Dict:
        """Analyze content patterns and posting behavior."""
        analysis = {}

        if not self.posts:
            return analysis

        # Analyze posting times
        posting_hours = []
        posting_days = []

        for post in self.posts:
            posted_at = post.get("posted_at")
            if posted_at:
                try:
                    dt = parse_iso8601_z(posted_at)
                    posting_hours.append(dt.hour)
                    posting_days.append(dt.strftime("%A"))
                except:
                    continue

        if posting_hours:
            hour_counts = Counter(posting_hours)
            analysis["optimal_posting_times"] = {
                "best_hours": [
                    {"hour": f"{h}:00", "post_count": c}
                    for h, c in hour_counts.most_common(5)
                ],
                "hour_distribution": dict(hour_counts)
            }

        if posting_days:
            day_counts = Counter(posting_days)
            analysis["optimal_posting_days"] = {
                "best_days": [
                    {"day": d, "post_count": c}
                    for d, c in day_counts.most_common(3)
                ],
                "day_distribution": dict(day_counts)
            }

        # Analyze content length
        text_lengths = [len(post.get("text", "")) for post in self.posts]
        if text_lengths:
            analysis["content_length"] = {
                "average_length": round(statistics.mean(text_lengths), 0),
                "median_length": statistics.median(text_lengths),
                "min_length": min(text_lengths),
                "max_length": max(text_lengths)
            }

        # Simple keyword analysis
        text_words = []
        for post in self.posts:
            text = post.get("text", "").lower()
            words = [
                word.strip(".,!?;:\"'()[]{}")
                for word in text.split()
                if len(word) > 5  # Only words longer than 5 chars
            ]
            text_words.extend(words)

        if text_words:
            word_counts = Counter(text_words)
            analysis["common_keywords"] = [
                {"keyword": word, "frequency": count}
                for word, count in word_counts.most_common(15)
            ]

        return analysis

    def _analyze_reactions(self) -> Dict:
        """Analyze reactor patterns and top engagers."""
        if not self.reactions:
            return {}

        analysis = {}

        # Top engagers (sorted by total reactions)
        sorted_reactors = sorted(
            self.reactions,
            key=lambda r: r.get("total_reactions", 0),
            reverse=True
        )

        analysis["top_engagers"] = [
            {
                "profile_id": r.get("profile_id"),
                "name": r.get("name"),
                "total_reactions": r.get("total_reactions", 0),
                "posts_engaged": len(r.get("posts_reacted_to", [])),
                "reaction_breakdown": r.get("reaction_breakdown", {})
            } for r in sorted_reactors[:20]
        ]

        # Engagement distribution
        reaction_counts = [r.get("total_reactions", 0) for r in self.reactions]
        if reaction_counts:
            analysis["engagement_distribution"] = {
                "average_reactions_per_engager": round(statistics.mean(reaction_counts), 2),
                "median_reactions": statistics.median(reaction_counts),
                "max_reactions": max(reaction_counts),
                "highly_engaged_users": sum(1 for count in reaction_counts if count >= 3),
                "total_unique_engagers": len(reaction_counts)
            }

        # Reaction type preferences across all engagers
        all_reaction_types = defaultdict(int)
        for reactor in self.reactions:
            for reaction_type, count in reactor.get("reaction_breakdown", {}).items():
                all_reaction_types[reaction_type] += count

        if all_reaction_types:
            total = sum(all_reaction_types.values())
            analysis["reaction_type_preferences"] = {
                reaction_type: {
                    "count": count,
                    "percentage": round((count / total) * 100, 1)
                } for reaction_type, count in sorted(
                    all_reaction_types.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            }

        # Multi-post engagers (engaged with 2+ posts)
        multi_post_engagers = [
            r for r in self.reactions
            if len(r.get("posts_reacted_to", [])) >= 2
        ]

        analysis["engagement_depth"] = {
            "multi_post_engagers": len(multi_post_engagers),
            "single_post_engagers": len(self.reactions) - len(multi_post_engagers),
            "retention_rate": round(
                len(multi_post_engagers) / len(self.reactions) * 100, 1
            ) if self.reactions else 0
        }

        return analysis

    def _calculate_trends(self) -> Dict:
        """Calculate time-based trends and patterns."""
        trends = {}

        if not self.posts:
            return trends

        # Time series engagement data
        time_series = []

        for post in self.posts:
            if post.get("posted_at"):
                try:
                    dt = datetime.fromisoformat(post.get("posted_at").replace("Z", "+00:00"))
                    engagement = (
                        post.get("activity", {}).get("num_likes", 0) +
                        post.get("activity", {}).get("num_comments", 0) +
                        post.get("activity", {}).get("num_shares", 0)
                    )

                    time_series.append({
                        "date": dt.date().isoformat(),
                        "datetime": dt,
                        "engagement": engagement,
                        "likes": post.get("activity", {}).get("num_likes", 0),
                        "comments": post.get("activity", {}).get("num_comments", 0),
                        "shares": post.get("activity", {}).get("num_shares", 0)
                    })
                except:
                    continue

        if time_series:
            # Sort by date
            time_series.sort(key=lambda x: x["datetime"])

            # Daily aggregation
            daily_stats = defaultdict(lambda: {
                "posts": 0,
                "total_engagement": 0,
                "total_likes": 0,
                "total_comments": 0,
                "total_shares": 0
            })

            for item in time_series:
                date_key = item["date"]
                daily_stats[date_key]["posts"] += 1
                daily_stats[date_key]["total_engagement"] += item["engagement"]
                daily_stats[date_key]["total_likes"] += item["likes"]
                daily_stats[date_key]["total_comments"] += item["comments"]
                daily_stats[date_key]["total_shares"] += item["shares"]

            trends["daily_activity"] = [
                {"date": date, **stats}
                for date, stats in sorted(daily_stats.items())
            ]

            # Calculate growth metrics (last 7 days vs previous 7 days)
            if len(daily_stats) >= 7:
                dates = sorted(daily_stats.keys())
                recent_7_days = dates[-7:]
                previous_7_days = dates[-14:-7] if len(dates) >= 14 else []

                recent_engagement = sum(
                    daily_stats[d]["total_engagement"] for d in recent_7_days
                )

                if previous_7_days:
                    previous_engagement = sum(
                        daily_stats[d]["total_engagement"] for d in previous_7_days
                    )

                    trends["growth_metrics"] = {
                        "recent_7_days_engagement": recent_engagement,
                        "previous_7_days_engagement": previous_engagement,
                        "engagement_change": recent_engagement - previous_engagement,
                        "percentage_change": round(
                            ((recent_engagement - previous_engagement) / previous_engagement * 100)
                            if previous_engagement > 0 else 0,
                            1
                        )
                    }

        return trends


if __name__ == "__main__":
    # Test with new data structure
    test_posts = [
        {
            "post_id": "7381924494396891136",
            "author_urn": "ilke-oner",
            "text": "Great content about business strategy",
            "posted_at": "2025-10-09T12:04:58.424Z",
            "post_url": "https://linkedin.com/...",
            "activity": {
                "num_likes": 21,
                "num_comments": 5,
                "num_shares": 2,
                "reaction_counts": [
                    {"type": "LIKE", "count": 13},
                    {"type": "INTEREST", "count": 5},
                    {"type": "EMPATHY", "count": 3}
                ]
            }
        }
    ]

    test_comments = [
        {
            "comment_id": "123",
            "post_id": "7381924494396891136",
            "author_profile_id": "john-doe",
            "text": "Great post!",
            "likes": 3,
            "created_at": "2025-10-09T13:00:00Z"
        }
    ]

    test_reactions = [
        {
            "profile_id": "laurence-blairon",
            "name": "Laurence Blairon",
            "total_reactions": 2,
            "posts_reacted_to": ["post1", "post2"],
            "reaction_breakdown": {"LIKE": 1, "EMPATHY": 1}
        }
    ]

    tool = ComputeLinkedInStats(
        posts=test_posts,
        comments=test_comments,
        reactions=test_reactions,
        include_trends=True
    )

    print("Testing ComputeLinkedInStats tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))
