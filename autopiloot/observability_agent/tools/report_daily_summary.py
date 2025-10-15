"""
Report Daily Summary tool for generating comprehensive daily pipeline summaries.
Implements TASK-OBS-0040 with Slack delivery and operational metrics compilation.
"""

import os
import sys
import json
from typing import Optional, Dict, Any, List
from agency_swarm.tools import BaseTool
from pydantic import Field
from google.cloud import firestore
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add core and config directories to path
from env_loader import get_required_env_var
from firestore_client import get_firestore_client
from loader import load_app_config
from audit_logger import audit_logger

load_dotenv()


class ReportDailySummary(BaseTool):
    """
    Generates comprehensive daily pipeline summary reports for Slack delivery.
    
    Compiles metrics from video processing, transcription, summarization,
    costs, errors, and system health for end-of-day operational reporting.
    """
    
    target_date: Optional[str] = Field(
        None,
        description="Target date for summary in YYYY-MM-DD format. Uses previous day if None."
    )
    
    include_details: bool = Field(
        True,
        description="Include detailed breakdowns and top items in summary"
    )
    
    slack_delivery: bool = Field(
        True,
        description="Format output for Slack delivery with rich blocks"
    )
    
    def run(self) -> str:
        """
        Generates daily summary report with comprehensive metrics.
        
        Returns:
            str: JSON string containing daily summary and optional Slack formatting
            
        Raises:
            RuntimeError: If summary generation fails
        """
        try:
            # Determine target date
            if self.target_date:
                try:
                    target_date = datetime.strptime(self.target_date, "%Y-%m-%d").date()
                except ValueError:
                    raise ValueError("target_date must be in YYYY-MM-DD format")
            else:
                # Use previous day (common for EOD reports)
                target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
            
            # Initialize Firestore client
            db = get_firestore_client()
            
            # Compile daily metrics
            video_metrics = self._compile_video_metrics(db, target_date)
            job_metrics = self._compile_job_metrics(db, target_date)
            cost_metrics = self._compile_cost_metrics(db, target_date)
            error_metrics = self._compile_error_metrics(db, target_date)
            quota_metrics = self._compile_quota_metrics(db, target_date)
            
            # Calculate performance indicators
            performance = self._calculate_performance_indicators(
                video_metrics, job_metrics, cost_metrics, error_metrics
            )
            
            # Generate insights and recommendations
            insights = self._generate_daily_insights(
                video_metrics, job_metrics, cost_metrics, error_metrics, performance
            )
            
            # Compile comprehensive summary
            summary = {
                "report_date": target_date.isoformat(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "video_metrics": video_metrics,
                "job_metrics": job_metrics,
                "cost_metrics": cost_metrics,
                "error_metrics": error_metrics,
                "quota_metrics": quota_metrics,
                "performance": performance,
                "insights": insights
            }
            
            # Add Slack formatting if requested
            if self.slack_delivery:
                summary["slack_blocks"] = self._format_slack_summary(summary)
            
            # Log summary generation to audit trail
            audit_logger.log_daily_summary_generated(
                report_date=target_date.isoformat(),
                videos_processed=video_metrics.get("total_processed", 0),
                total_cost_usd=cost_metrics.get("total_cost", 0),
                error_count=error_metrics.get("total_errors", 0),
                actor="ObservabilityAgent"
            )
            
            return json.dumps(summary, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to generate daily summary: {str(e)}",
                "report_date": None
            })
    
    def _compile_video_metrics(self, db, target_date) -> Dict[str, Any]:
        """Compile video processing metrics for the target date."""
        start_time = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_time = start_time + timedelta(days=1)
        
        try:
            # Query videos created on target date
            videos_query = (db.collection('videos')
                          .where('created_at', '>=', start_time)
                          .where('created_at', '<', end_time)
                          .limit(1000))
            
            videos = list(videos_query.stream())
            
            # Analyze video status distribution
            status_counts = {}
            source_counts = {}
            total_duration = 0
            channels = set()
            
            for video_doc in videos:
                video_data = video_doc.to_dict()
                
                status = video_data.get('status', 'unknown')
                source = video_data.get('source', 'unknown')
                duration = video_data.get('duration_sec', 0)
                channel_id = video_data.get('channel_id')
                
                status_counts[status] = status_counts.get(status, 0) + 1
                source_counts[source] = source_counts.get(source, 0) + 1
                total_duration += duration
                
                if channel_id:
                    channels.add(channel_id)
            
            return {
                "total_discovered": len(videos),
                "total_processed": status_counts.get('summarized', 0),
                "status_distribution": status_counts,
                "source_distribution": source_counts,
                "total_duration_hours": round(total_duration / 3600, 1),
                "unique_channels": len(channels),
                "average_duration_minutes": round(total_duration / len(videos) / 60, 1) if videos else 0,
                "processing_rate": round(status_counts.get('summarized', 0) / len(videos) * 100, 1) if videos else 0
            }
            
        except Exception:
            return {
                "total_discovered": 0,
                "total_processed": 0,
                "status_distribution": {},
                "source_distribution": {},
                "total_duration_hours": 0,
                "unique_channels": 0,
                "average_duration_minutes": 0,
                "processing_rate": 0
            }
    
    def _compile_job_metrics(self, db, target_date) -> Dict[str, Any]:
        """Compile job execution metrics across all agents."""
        start_time = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_time = start_time + timedelta(days=1)
        
        job_metrics = {
            "total_jobs": 0,
            "successful_jobs": 0,
            "failed_jobs": 0,
            "dlq_jobs": 0,
            "by_agent": {},
            "by_type": {},
            "average_processing_time_minutes": 0
        }
        
        try:
            # Query DLQ entries for failed jobs
            dlq_query = (db.collection('jobs_deadletter')
                        .where('dlq_created_at', '>=', start_time)
                        .where('dlq_created_at', '<', end_time)
                        .limit(500))
            
            dlq_entries = list(dlq_query.stream())
            job_metrics["dlq_jobs"] = len(dlq_entries)
            
            # Analyze DLQ by type and agent
            for dlq_doc in dlq_entries:
                dlq_data = dlq_doc.to_dict()
                job_type = dlq_data.get('job_type', 'unknown')
                
                # Infer agent from job type
                if job_type in ['channel_scrape', 'sheet_backfill']:
                    agent = 'scraper'
                elif job_type in ['single_video', 'batch_transcribe']:
                    agent = 'transcriber'
                elif job_type in ['single_summary', 'batch_summarize']:
                    agent = 'summarizer'
                else:
                    agent = 'unknown'
                
                job_metrics["by_agent"][agent] = job_metrics["by_agent"].get(agent, 0) + 1
                job_metrics["by_type"][job_type] = job_metrics["by_type"].get(job_type, 0) + 1
            
            job_metrics["failed_jobs"] = len(dlq_entries)
            
            # Estimate successful jobs based on video progression
            # This is a simplification - in production, would track actual job completions
            job_metrics["successful_jobs"] = max(0, job_metrics["total_jobs"] - job_metrics["failed_jobs"])
            
        except Exception:
            pass
        
        return job_metrics
    
    def _compile_cost_metrics(self, db, target_date) -> Dict[str, Any]:
        """Compile cost metrics for the target date."""
        try:
            # Query costs_daily collection for the target date
            cost_doc_id = target_date.strftime("%Y-%m-%d")
            cost_doc = db.collection('costs_daily').document(cost_doc_id).get()
            
            if cost_doc.exists:
                cost_data = cost_doc.to_dict()
                return {
                    "total_cost": cost_data.get('total_usd', 0),
                    "transcription_cost": cost_data.get('transcription_usd', 0),
                    "llm_cost": cost_data.get('llm_usd', 0),
                    "other_costs": cost_data.get('other_usd', 0),
                    "budget_utilization": self._calculate_budget_utilization(cost_data.get('transcription_usd', 0)),
                    "cost_per_video": self._calculate_cost_per_video(cost_data, target_date, db)
                }
            else:
                return {
                    "total_cost": 0,
                    "transcription_cost": 0,
                    "llm_cost": 0,
                    "other_costs": 0,
                    "budget_utilization": 0,
                    "cost_per_video": 0
                }
                
        except Exception:
            return {
                "total_cost": 0,
                "transcription_cost": 0,
                "llm_cost": 0,
                "other_costs": 0,
                "budget_utilization": 0,
                "cost_per_video": 0
            }
    
    def _compile_error_metrics(self, db, target_date) -> Dict[str, Any]:
        """Compile error and reliability metrics."""
        start_time = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_time = start_time + timedelta(days=1)
        
        try:
            # Query audit logs for errors
            audit_query = (db.collection('audit_logs')
                         .where('timestamp', '>=', start_time)
                         .where('timestamp', '<', end_time)
                         .where('action', 'in', ['error_occurred', 'job_failed', 'alert_sent'])
                         .limit(500))
            
            error_logs = list(audit_query.stream())
            
            error_types = {}
            severity_counts = {}
            
            for log_doc in error_logs:
                log_data = log_doc.to_dict()
                details = log_data.get('details', {})
                
                error_type = details.get('error_type', 'unknown')
                severity = details.get('severity', 'unknown')
                
                error_types[error_type] = error_types.get(error_type, 0) + 1
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            return {
                "total_errors": len(error_logs),
                "error_types": error_types,
                "severity_distribution": severity_counts,
                "error_rate": self._calculate_error_rate(len(error_logs), target_date, db),
                "mttr_minutes": self._estimate_mttr(error_logs)
            }
            
        except Exception:
            return {
                "total_errors": 0,
                "error_types": {},
                "severity_distribution": {},
                "error_rate": 0,
                "mttr_minutes": 0
            }
    
    def _compile_quota_metrics(self, db, target_date) -> Dict[str, Any]:
        """Compile quota utilization metrics."""
        config = load_app_config()
        
        # Get quota limits from config
        youtube_limit = config.get("reliability", {}).get("quotas", {}).get("youtube_daily_limit", 10000)
        assemblyai_limit = config.get("reliability", {}).get("quotas", {}).get("assemblyai_daily_limit", 100)
        
        # Estimate usage based on activity (simplified)
        start_time = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_time = start_time + timedelta(days=1)
        
        try:
            # Estimate YouTube usage from video discoveries
            videos_query = (db.collection('videos')
                          .where('created_at', '>=', start_time)
                          .where('created_at', '<', end_time)
                          .limit(1000))
            
            video_count = len(list(videos_query.stream()))
            estimated_youtube_usage = video_count * 100  # Rough estimate
            
            # Estimate AssemblyAI usage from transcripts
            transcripts_query = (db.collection('transcripts')
                               .where('created_at', '>=', start_time)
                               .where('created_at', '<', end_time)
                               .limit(500))
            
            transcript_count = len(list(transcripts_query.stream()))
            
            return {
                "youtube": {
                    "estimated_usage": estimated_youtube_usage,
                    "daily_limit": youtube_limit,
                    "utilization_percent": round(estimated_youtube_usage / youtube_limit * 100, 1) if youtube_limit > 0 else 0
                },
                "assemblyai": {
                    "estimated_usage": transcript_count,
                    "daily_limit": assemblyai_limit,
                    "utilization_percent": round(transcript_count / assemblyai_limit * 100, 1) if assemblyai_limit > 0 else 0
                }
            }
            
        except Exception:
            return {
                "youtube": {"estimated_usage": 0, "daily_limit": youtube_limit, "utilization_percent": 0},
                "assemblyai": {"estimated_usage": 0, "daily_limit": assemblyai_limit, "utilization_percent": 0}
            }
    
    def _calculate_performance_indicators(self, video_metrics: Dict, job_metrics: Dict, cost_metrics: Dict, error_metrics: Dict) -> Dict[str, Any]:
        """Calculate key performance indicators."""
        # Processing efficiency
        processing_rate = video_metrics.get("processing_rate", 0)
        
        # Cost efficiency
        cost_per_video = cost_metrics.get("cost_per_video", 0)
        
        # Reliability
        error_rate = error_metrics.get("error_rate", 0)
        
        # Overall health score (0-100)
        health_score = 100
        
        # Penalize low processing rate
        if processing_rate < 80:
            health_score -= (80 - processing_rate) * 0.5
        
        # Penalize high error rate
        if error_rate > 5:
            health_score -= min(30, (error_rate - 5) * 3)
        
        # Penalize high costs
        budget_util = cost_metrics.get("budget_utilization", 0)
        if budget_util > 90:
            health_score -= (budget_util - 90) * 2
        
        health_score = max(0, min(100, health_score))
        
        return {
            "processing_efficiency": processing_rate,
            "cost_efficiency": cost_per_video,
            "reliability_score": 100 - error_rate,
            "overall_health_score": round(health_score, 1),
            "health_status": self._get_health_status(health_score),
            "key_metrics": {
                "videos_processed": video_metrics.get("total_processed", 0),
                "total_cost_usd": cost_metrics.get("total_cost", 0),
                "error_count": error_metrics.get("total_errors", 0),
                "processing_rate_percent": processing_rate
            }
        }
    
    def _generate_daily_insights(self, video_metrics: Dict, job_metrics: Dict, cost_metrics: Dict, error_metrics: Dict, performance: Dict) -> List[Dict[str, Any]]:
        """Generate actionable insights from daily metrics."""
        insights = []
        
        # Performance insights
        processing_rate = video_metrics.get("processing_rate", 0)
        if processing_rate < 70:
            insights.append({
                "type": "performance_concern",
                "severity": "warning",
                "message": f"Processing rate at {processing_rate}% - below target of 80%",
                "recommendation": "Investigate transcription and summarization bottlenecks"
            })
        elif processing_rate > 95:
            insights.append({
                "type": "performance_excellent",
                "severity": "info",
                "message": f"Excellent processing rate of {processing_rate}%",
                "recommendation": "Maintain current operational parameters"
            })
        
        # Cost insights
        budget_util = cost_metrics.get("budget_utilization", 0)
        if budget_util > 80:
            insights.append({
                "type": "budget_concern",
                "severity": "warning" if budget_util < 95 else "critical",
                "message": f"Budget utilization at {budget_util}%",
                "recommendation": "Review transcription volume and consider optimization"
            })
        
        # Error insights
        error_count = error_metrics.get("total_errors", 0)
        if error_count > 10:
            top_error = max(error_metrics.get("error_types", {}).items(), key=lambda x: x[1], default=("unknown", 0))
            insights.append({
                "type": "reliability_concern",
                "severity": "warning",
                "message": f"{error_count} errors detected, primarily '{top_error[0]}'",
                "recommendation": "Focus on resolving the most common error type"
            })
        
        # Quota insights
        # Would add quota utilization insights here
        
        return insights
    
    def _format_slack_summary(self, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format summary for Slack delivery with rich blocks."""
        performance = summary.get("performance", {})
        video_metrics = summary.get("video_metrics", {})
        cost_metrics = summary.get("cost_metrics", {})
        error_metrics = summary.get("error_metrics", {})
        
        health_score = performance.get("overall_health_score", 0)
        status_emoji = "✅" if health_score >= 80 else "⚠️" if health_score >= 60 else "🚨"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{status_emoji} Daily Pipeline Summary - {summary.get('report_date')}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Videos Processed:* {video_metrics.get('total_processed', 0)}/{video_metrics.get('total_discovered', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Processing Rate:* {video_metrics.get('processing_rate', 0)}%"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Cost:* ${cost_metrics.get('total_cost', 0):.2f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Errors:* {error_metrics.get('total_errors', 0)}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Health Score:* {health_score}/100 ({performance.get('health_status', 'unknown')})"
                }
            }
        ]
        
        # Add insights section if available
        insights = summary.get("insights", [])
        if insights:
            insight_text = "\n".join([f"• {insight['message']}" for insight in insights[:3]])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Key Insights:*\n{insight_text}"
                }
            })
        
        return blocks
    
    def _calculate_budget_utilization(self, transcription_cost: float) -> float:
        """Calculate budget utilization percentage."""
        config = load_app_config()
        daily_budget = config.get("budgets", {}).get("transcription_daily_usd", 5.0)
        return round(transcription_cost / daily_budget * 100, 1) if daily_budget > 0 else 0
    
    def _calculate_cost_per_video(self, cost_data: Dict, target_date, db) -> float:
        """Calculate average cost per processed video."""
        total_cost = cost_data.get('total_usd', 0)
        
        # Get video count for the date
        start_time = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_time = start_time + timedelta(days=1)
        
        try:
            videos_query = (db.collection('videos')
                          .where('created_at', '>=', start_time)
                          .where('created_at', '<', end_time)
                          .where('status', '==', 'summarized')
                          .limit(1000))
            
            processed_count = len(list(videos_query.stream()))
            return round(total_cost / processed_count, 3) if processed_count > 0 else 0
            
        except Exception:
            return 0
    
    def _calculate_error_rate(self, error_count: int, target_date, db) -> float:
        """Calculate error rate as percentage of total operations."""
        # Simplified calculation - in production would track actual operation count
        estimated_operations = max(100, error_count * 10)  # Rough estimate
        return round(error_count / estimated_operations * 100, 2)
    
    def _estimate_mttr(self, error_logs: List) -> float:
        """Estimate mean time to recovery from error logs."""
        # Simplified estimation - would need actual resolution tracking
        return 30.0  # Default 30 minutes
    
    def _get_health_status(self, health_score: float) -> str:
        """Get human-readable health status."""
        if health_score >= 90:
            return "excellent"
        elif health_score >= 80:
            return "good"
        elif health_score >= 60:
            return "fair"
        elif health_score >= 40:
            return "poor"
        else:
            return "critical"
    

if __name__ == "__main__":
    # Test daily summary generation
    print("Testing report_daily_summary...")
    test_tool = ReportDailySummary(
        target_date=None,  # Use yesterday
        include_details=True,
        slack_delivery=True
    )
    
    try:
        result = test_tool.run()
        print("Daily summary result:")
        print(result)
        
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            performance = data.get('performance', {})
            video_metrics = data.get('video_metrics', {})
            print(f"Report date: {data['report_date']}")
            print(f"Videos processed: {video_metrics.get('total_processed', 0)}")
            print(f"Health score: {performance.get('overall_health_score', 0)}")
            print(f"Insights: {len(data.get('insights', []))}")
            if 'slack_blocks' in data:
                print(f"Slack blocks: {len(data['slack_blocks'])}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting with specific date...")
    test_tool_date = ReportDailySummary(
        target_date="2025-01-26",
        include_details=False,
        slack_delivery=False
    )
    
    try:
        result = test_tool_date.run()
        data = json.loads(result)
        if "error" not in data:
            print(f"Specific date report: {data['report_date']}")
        
    except Exception as e:
        print(f"Date test error: {str(e)}")