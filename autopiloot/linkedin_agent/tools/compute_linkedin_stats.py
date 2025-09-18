"""
ComputeLinkedInStats tool for calculating comprehensive analytics and insights from LinkedIn data.
Generates statistical analysis for strategy optimization and performance tracking.
"""

import json
import statistics
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from agency_swarm.tools import BaseTool
from pydantic import Field


class ComputeLinkedInStats(BaseTool):
    """
    Computes comprehensive statistics and analytics from LinkedIn content.

    Analyzes posts, comments, reactions, and engagement patterns to provide
    insights for content strategy and performance optimization.
    """

    posts: Optional[List[Dict]] = Field(
        None,
        description="Normalized LinkedIn posts data for analysis"
    )

    comments: Optional[List[Dict]] = Field(
        None,
        description="Normalized LinkedIn comments data for analysis"
    )

    reactions: Optional[Dict] = Field(
        None,
        description="Normalized LinkedIn reactions data for analysis"
    )

    user_activity: Optional[List[Dict]] = Field(
        None,
        description="User comment activity data for analysis"
    )

    include_histograms: bool = Field(
        True,
        description="Whether to include engagement distribution histograms (default: True)"
    )

    include_trends: bool = Field(
        True,
        description="Whether to calculate time-based trends (default: True)"
    )

    def run(self) -> str:
        """
        Computes comprehensive LinkedIn statistics and analytics.

        Returns:
            str: JSON string containing statistical analysis
                 Format: {
                     "overview": {
                         "total_posts": 150,
                         "total_comments": 500,
                         "total_reactions": 2500,
                         "analysis_period": "2024-01-01 to 2024-01-31"
                     },
                     "engagement_stats": {
                         "average_likes_per_post": 45.2,
                         "engagement_rate": 0.045,
                         "top_performing_posts": [...],
                         "engagement_distribution": {...}
                     },
                     "content_analysis": {
                         "most_common_topics": [...],
                         "optimal_posting_times": [...],
                         "content_type_performance": {...}
                     },
                     "user_insights": {
                         "most_active_commenters": [...],
                         "engagement_patterns": {...}
                     },
                     "trends": {
                         "engagement_over_time": [...],
                         "growth_metrics": {...}
                     }
                 }
        """
        try:
            # Initialize result structure
            result = {
                "analysis_metadata": {
                    "computed_at": datetime.utcnow().isoformat() + "Z",
                    "data_sources": [],
                    "analysis_period": None
                }
            }

            # Determine what data sources are available
            data_sources = []
            if self.posts:
                data_sources.append(f"posts ({len(self.posts)})")
            if self.comments:
                data_sources.append(f"comments ({len(self.comments)})")
            if self.reactions:
                data_sources.append("reactions")
            if self.user_activity:
                data_sources.append(f"user_activity ({len(self.user_activity)})")

            result["analysis_metadata"]["data_sources"] = data_sources

            # Calculate overview statistics
            result["overview"] = self._calculate_overview()

            # Calculate engagement statistics
            if self.posts or self.comments:
                result["engagement_stats"] = self._calculate_engagement_stats()

            # Analyze content patterns
            if self.posts:
                result["content_analysis"] = self._analyze_content_patterns()

            # Calculate user insights
            if self.comments or self.user_activity:
                result["user_insights"] = self._calculate_user_insights()

            # Calculate trends if requested
            if self.include_trends:
                result["trends"] = self._calculate_trends()

            # Add reaction analysis if available
            if self.reactions:
                result["reaction_analysis"] = self._analyze_reactions()

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "stats_computation_failed",
                "message": str(e),
                "data_available": {
                    "posts": len(self.posts) if self.posts else 0,
                    "comments": len(self.comments) if self.comments else 0,
                    "has_reactions": bool(self.reactions),
                    "user_activity": len(self.user_activity) if self.user_activity else 0
                }
            }
            return json.dumps(error_result)

    def _calculate_overview(self) -> Dict:
        """Calculate high-level overview statistics."""
        overview = {}

        if self.posts:
            overview["total_posts"] = len(self.posts)
            overview["unique_authors"] = len(set(
                p.get("author", {}).get("name", "Unknown") for p in self.posts
            ))

        if self.comments:
            overview["total_comments"] = len(self.comments)

        if self.reactions:
            overview["total_reactions"] = self.reactions.get("summary", {}).get("total_reactions", 0)

        if self.user_activity:
            overview["user_activities_tracked"] = len(self.user_activity)

        # Calculate analysis period
        dates = []
        if self.posts:
            dates.extend([p.get("created_at") for p in self.posts if p.get("created_at")])
        if self.comments:
            dates.extend([c.get("created_at") for c in self.comments if c.get("created_at")])

        if dates:
            dates = [d for d in dates if d]  # Filter out None values
            if dates:
                overview["analysis_period"] = {
                    "start": min(dates),
                    "end": max(dates),
                    "days_covered": (datetime.fromisoformat(max(dates).replace("Z", "")) -
                                   datetime.fromisoformat(min(dates).replace("Z", ""))).days
                }

        return overview

    def _calculate_engagement_stats(self) -> Dict:
        """Calculate detailed engagement statistics."""
        stats = {}

        if self.posts:
            # Calculate post engagement metrics
            likes = [p.get("metrics", {}).get("likes", 0) for p in self.posts]
            comments = [p.get("metrics", {}).get("comments", 0) for p in self.posts]
            shares = [p.get("metrics", {}).get("shares", 0) for p in self.posts]
            views = [p.get("metrics", {}).get("views", 0) for p in self.posts if p.get("metrics", {}).get("views", 0) > 0]

            stats["post_metrics"] = {
                "average_likes": round(statistics.mean(likes), 2) if likes else 0,
                "median_likes": statistics.median(likes) if likes else 0,
                "max_likes": max(likes) if likes else 0,
                "average_comments": round(statistics.mean(comments), 2) if comments else 0,
                "average_shares": round(statistics.mean(shares), 2) if shares else 0,
                "average_engagement_rate": round(statistics.mean([
                    p.get("metrics", {}).get("engagement_rate", 0) for p in self.posts
                ]), 4) if self.posts else 0
            }

            # Top performing posts
            sorted_posts = sorted(self.posts, key=lambda p: p.get("metrics", {}).get("likes", 0), reverse=True)
            stats["top_performing_posts"] = [
                {
                    "id": p.get("id"),
                    "text_preview": p.get("text", "")[:100] + "..." if len(p.get("text", "")) > 100 else p.get("text", ""),
                    "likes": p.get("metrics", {}).get("likes", 0),
                    "comments": p.get("metrics", {}).get("comments", 0),
                    "engagement_rate": p.get("metrics", {}).get("engagement_rate", 0),
                    "author": p.get("author", {}).get("name", "Unknown")
                } for p in sorted_posts[:5]
            ]

            # Engagement distribution histograms
            if self.include_histograms:
                stats["engagement_distribution"] = {
                    "likes_histogram": self._create_histogram(likes, "likes"),
                    "comments_histogram": self._create_histogram(comments, "comments")
                }

        if self.comments:
            # Calculate comment engagement
            comment_likes = [c.get("metrics", {}).get("likes", 0) for c in self.comments]
            stats["comment_metrics"] = {
                "average_likes_per_comment": round(statistics.mean(comment_likes), 2) if comment_likes else 0,
                "comments_with_likes": sum(1 for likes in comment_likes if likes > 0),
                "like_rate": round(sum(1 for likes in comment_likes if likes > 0) / len(comment_likes), 3) if comment_likes else 0
            }

        return stats

    def _analyze_content_patterns(self) -> Dict:
        """Analyze content patterns and topics."""
        analysis = {}

        if not self.posts:
            return analysis

        # Analyze posting times
        posting_hours = []
        posting_days = []

        for post in self.posts:
            created_at = post.get("created_at")
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace("Z", ""))
                    posting_hours.append(dt.hour)
                    posting_days.append(dt.strftime("%A"))
                except:
                    continue

        if posting_hours:
            hour_counts = Counter(posting_hours)
            analysis["optimal_posting_times"] = {
                "best_hours": [{"hour": h, "count": c} for h, c in hour_counts.most_common(3)],
                "hour_distribution": dict(hour_counts)
            }

        if posting_days:
            day_counts = Counter(posting_days)
            analysis["optimal_posting_days"] = {
                "best_days": [{"day": d, "count": c} for d, c in day_counts.most_common(3)],
                "day_distribution": dict(day_counts)
            }

        # Analyze content types by media presence
        media_analysis = {
            "text_only": 0,
            "with_images": 0,
            "with_videos": 0,
            "with_articles": 0
        }

        engagement_by_type = defaultdict(list)

        for post in self.posts:
            media = post.get("media", [])
            likes = post.get("metrics", {}).get("likes", 0)

            if not media:
                media_analysis["text_only"] += 1
                engagement_by_type["text_only"].append(likes)
            else:
                has_image = any(m.get("type") == "image" for m in media)
                has_video = any(m.get("type") == "video" for m in media)
                has_article = any(m.get("type") == "article" for m in media)

                if has_image:
                    media_analysis["with_images"] += 1
                    engagement_by_type["with_images"].append(likes)
                if has_video:
                    media_analysis["with_videos"] += 1
                    engagement_by_type["with_videos"].append(likes)
                if has_article:
                    media_analysis["with_articles"] += 1
                    engagement_by_type["with_articles"].append(likes)

        analysis["content_type_analysis"] = {
            "distribution": media_analysis,
            "performance_by_type": {
                content_type: {
                    "average_likes": round(statistics.mean(likes), 2) if likes else 0,
                    "post_count": len(likes)
                } for content_type, likes in engagement_by_type.items()
            }
        }

        # Simple text analysis for common themes
        text_words = []
        for post in self.posts:
            text = post.get("text", "").lower()
            # Simple word extraction (could be enhanced with NLP)
            words = [word.strip(".,!?;:") for word in text.split() if len(word) > 4]
            text_words.extend(words)

        if text_words:
            word_counts = Counter(text_words)
            analysis["common_terms"] = [
                {"term": word, "frequency": count}
                for word, count in word_counts.most_common(10)
            ]

        return analysis

    def _calculate_user_insights(self) -> Dict:
        """Calculate insights about user engagement patterns."""
        insights = {}

        if self.comments:
            # Most active commenters
            commenter_counts = Counter(
                c.get("author", {}).get("name", "Unknown") for c in self.comments
            )
            insights["most_active_commenters"] = [
                {"name": name, "comment_count": count}
                for name, count in commenter_counts.most_common(5)
            ]

            # Comment engagement patterns
            comment_likes = [c.get("metrics", {}).get("likes", 0) for c in self.comments]
            insights["comment_engagement"] = {
                "total_comment_likes": sum(comment_likes),
                "comments_with_high_engagement": sum(1 for likes in comment_likes if likes >= 5),
                "average_likes_per_commenter": {}
            }

            # Likes by commenter
            commenter_likes = defaultdict(list)
            for comment in self.comments:
                name = comment.get("author", {}).get("name", "Unknown")
                likes = comment.get("metrics", {}).get("likes", 0)
                commenter_likes[name].append(likes)

            insights["comment_engagement"]["average_likes_per_commenter"] = {
                name: round(statistics.mean(likes), 2)
                for name, likes in commenter_likes.items()
            }

        if self.user_activity:
            # User activity patterns
            activity_metrics = []
            for activity in self.user_activity:
                if isinstance(activity, dict) and "activity_metrics" in activity:
                    activity_metrics.append(activity["activity_metrics"])

            if activity_metrics:
                insights["user_activity_patterns"] = {
                    "users_analyzed": len(activity_metrics),
                    "average_comments_per_user": round(statistics.mean([
                        m.get("total_comments", 0) for m in activity_metrics
                    ]), 2) if activity_metrics else 0
                }

        return insights

    def _calculate_trends(self) -> Dict:
        """Calculate time-based trends and patterns."""
        trends = {}

        if not (self.posts or self.comments):
            return trends

        # Combine posts and comments with timestamps
        time_series_data = []

        if self.posts:
            for post in self.posts:
                if post.get("created_at"):
                    time_series_data.append({
                        "timestamp": post["created_at"],
                        "type": "post",
                        "likes": post.get("metrics", {}).get("likes", 0),
                        "engagement": post.get("metrics", {}).get("likes", 0) + post.get("metrics", {}).get("comments", 0)
                    })

        if self.comments:
            for comment in self.comments:
                if comment.get("created_at"):
                    time_series_data.append({
                        "timestamp": comment["created_at"],
                        "type": "comment",
                        "likes": comment.get("metrics", {}).get("likes", 0),
                        "engagement": comment.get("metrics", {}).get("likes", 0)
                    })

        if time_series_data:
            # Sort by timestamp
            time_series_data.sort(key=lambda x: x["timestamp"])

            # Weekly aggregation
            weekly_stats = defaultdict(lambda: {"posts": 0, "comments": 0, "total_engagement": 0})

            for item in time_series_data:
                try:
                    dt = datetime.fromisoformat(item["timestamp"].replace("Z", ""))
                    week_key = dt.strftime("%Y-W%U")  # Year-Week format
                    weekly_stats[week_key][item["type"] + "s"] += 1
                    weekly_stats[week_key]["total_engagement"] += item["engagement"]
                except:
                    continue

            trends["weekly_activity"] = [
                {"week": week, **stats} for week, stats in sorted(weekly_stats.items())
            ]

            # Calculate growth metrics
            if len(weekly_stats) >= 2:
                weeks = sorted(weekly_stats.keys())
                recent_weeks = weeks[-2:]
                if len(recent_weeks) == 2:
                    prev_week = weekly_stats[recent_weeks[0]]
                    curr_week = weekly_stats[recent_weeks[1]]

                    trends["growth_metrics"] = {
                        "posts_growth": curr_week["posts"] - prev_week["posts"],
                        "engagement_growth": curr_week["total_engagement"] - prev_week["total_engagement"],
                        "week_over_week_change": round(
                            ((curr_week["total_engagement"] - prev_week["total_engagement"]) /
                             prev_week["total_engagement"] * 100) if prev_week["total_engagement"] > 0 else 0, 2
                        )
                    }

        return trends

    def _analyze_reactions(self) -> Dict:
        """Analyze reaction patterns and preferences."""
        if not self.reactions:
            return {}

        analysis = {}

        # Overall reaction distribution
        summary = self.reactions.get("summary", {})
        analysis["reaction_summary"] = {
            "total_reactions": summary.get("total_reactions", 0),
            "posts_with_reactions": summary.get("unique_posts", 0),
            "reaction_types": summary.get("reaction_types", {})
        }

        # Reaction type preferences
        if "reaction_types" in summary:
            total_reactions = sum(summary["reaction_types"].values())
            analysis["reaction_preferences"] = {
                reaction_type: {
                    "count": count,
                    "percentage": round((count / total_reactions) * 100, 1) if total_reactions > 0 else 0
                } for reaction_type, count in summary["reaction_types"].items()
            }

        # Post-level reaction analysis
        if "posts_with_reactions" in self.reactions:
            post_reactions = self.reactions["posts_with_reactions"]
            reaction_totals = [pr.get("total", 0) for pr in post_reactions]

            if reaction_totals:
                analysis["reaction_distribution"] = {
                    "average_reactions_per_post": round(statistics.mean(reaction_totals), 2),
                    "median_reactions": statistics.median(reaction_totals),
                    "max_reactions": max(reaction_totals),
                    "posts_with_high_reactions": sum(1 for r in reaction_totals if r >= 50)
                }

        return analysis

    def _create_histogram(self, values: List[int], metric_name: str) -> Dict:
        """Create a histogram distribution for a metric."""
        if not values:
            return {}

        # Define bins based on data range
        max_val = max(values)
        if max_val <= 10:
            bins = list(range(0, max_val + 2))
        elif max_val <= 100:
            bins = list(range(0, max_val + 10, 10))
        else:
            bins = list(range(0, max_val + 50, 50))

        histogram = {}
        for i in range(len(bins) - 1):
            count = sum(1 for v in values if bins[i] <= v < bins[i + 1])
            histogram[f"{bins[i]}-{bins[i + 1] - 1}"] = count

        return {
            "bins": histogram,
            "total_items": len(values),
            "metric": metric_name
        }


if __name__ == "__main__":
    # Test the tool
    test_posts = [
        {
            "id": "post_1",
            "text": "Great content about business strategy",
            "created_at": "2024-01-15T10:00:00Z",
            "author": {"name": "John Doe"},
            "metrics": {"likes": 150, "comments": 25, "shares": 5, "engagement_rate": 0.05}
        },
        {
            "id": "post_2",
            "text": "Another post about entrepreneurship",
            "created_at": "2024-01-16T14:00:00Z",
            "author": {"name": "Jane Smith"},
            "metrics": {"likes": 200, "comments": 30, "shares": 10, "engagement_rate": 0.07}
        }
    ]

    tool = ComputeLinkedInStats(
        posts=test_posts,
        include_histograms=True,
        include_trends=True
    )
    print("Testing ComputeLinkedInStats tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))