"""
Stuck Job Scanner tool for detecting stale jobs by status age and escalating issues.
Implements TASK-OBS-0040 with configurable staleness thresholds and escalation logic.
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
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var
from loader import load_app_config
from audit_logger import audit_logger

load_dotenv()


class StuckJobScanner(BaseTool):
    """
    Scans for stuck jobs by analyzing status age and escalates based on staleness.
    
    Monitors active jobs across all agent collections to identify jobs that have
    been in the same status for too long, indicating potential processing issues.
    """
    
    staleness_threshold_hours: int = Field(
        4,
        description="Hours after which a job is considered potentially stuck. Default 4 hours.",
        ge=1,
        le=72
    )
    
    critical_threshold_hours: int = Field(
        12,
        description="Hours after which a stuck job becomes critical. Default 12 hours.",
        ge=1,
        le=168
    )
    
    include_status_breakdown: bool = Field(
        True,
        description="Include detailed breakdown by job status and type"
    )
    
    def run(self) -> str:
        """
        Scans for stuck jobs and returns analysis with escalation recommendations.
        
        Returns:
            str: JSON string containing stuck job analysis and escalation actions
            
        Raises:
            RuntimeError: If job scanning fails
        """
        try:
            # Initialize Firestore client
            db = self._initialize_firestore()
            
            # Define staleness thresholds
            now = datetime.now(timezone.utc)
            stale_threshold = now - timedelta(hours=self.staleness_threshold_hours)
            critical_threshold = now - timedelta(hours=self.critical_threshold_hours)
            
            # Scan jobs across all agent collections
            stuck_jobs = self._scan_all_job_collections(db, stale_threshold, critical_threshold)
            
            # Analyze stuck job patterns
            analysis = self._analyze_stuck_patterns(stuck_jobs, stale_threshold, critical_threshold)
            
            # Generate escalation actions
            escalations = self._generate_escalations(stuck_jobs, analysis)
            
            # Calculate system health impact
            health_impact = self._calculate_health_impact(stuck_jobs, analysis)
            
            # Log stuck job monitoring to audit trail
            audit_logger.log_stuck_jobs_scanned(
                stuck_count=len(stuck_jobs),
                critical_count=len([j for j in stuck_jobs if j['severity'] == 'critical']),
                escalation_count=len(escalations),
                actor="ObservabilityAgent"
            )
            
            return json.dumps({
                "scan_timestamp": now.isoformat(),
                "thresholds": {
                    "staleness_hours": self.staleness_threshold_hours,
                    "critical_hours": self.critical_threshold_hours,
                    "stale_cutoff": stale_threshold.isoformat(),
                    "critical_cutoff": critical_threshold.isoformat()
                },
                "stuck_jobs": stuck_jobs,
                "analysis": analysis,
                "escalations": escalations,
                "health_impact": health_impact,
                "recommendations": self._generate_recommendations(analysis, health_impact)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to scan for stuck jobs: {str(e)}",
                "stuck_jobs": []
            })
    
    def _scan_all_job_collections(self, db, stale_threshold: datetime, critical_threshold: datetime) -> List[Dict[str, Any]]:
        """Scan all agent job collections for stuck jobs."""
        agent_collections = ['scraper', 'transcriber', 'summarizer']
        stuck_jobs = []
        
        for agent in agent_collections:
            try:
                # Query active jobs for this agent
                active_jobs_ref = db.collection('jobs').document(agent).collection('active')
                
                # Get all active jobs (in production, might want to add filters)
                jobs_query = active_jobs_ref.limit(500)  # Reasonable limit
                
                for job_doc in jobs_query.stream():
                    job_data = job_doc.to_dict()
                    job_data['job_ref'] = f"jobs/{agent}/active/{job_doc.id}"
                    job_data['agent'] = agent
                    
                    # Check if job is stuck
                    stuck_info = self._check_job_staleness(job_data, stale_threshold, critical_threshold)
                    if stuck_info:
                        stuck_jobs.append({
                            **job_data,
                            **stuck_info
                        })
                        
            except Exception as e:
                # Continue scanning other agents if one fails
                continue
        
        # Also scan for stuck videos in processing status
        video_stuck_jobs = self._scan_video_statuses(db, stale_threshold, critical_threshold)
        stuck_jobs.extend(video_stuck_jobs)
        
        return stuck_jobs
    
    def _check_job_staleness(self, job_data: Dict[str, Any], stale_threshold: datetime, critical_threshold: datetime) -> Optional[Dict[str, Any]]:
        """Check if a job is stuck based on its timestamps and status."""
        created_at = job_data.get('created_at')
        status = job_data.get('status', 'unknown')
        
        if not created_at:
            return None
        
        # Convert Firestore timestamp to datetime if needed
        if hasattr(created_at, 'replace'):
            job_created = created_at.replace(tzinfo=timezone.utc)
        elif isinstance(created_at, str):
            try:
                job_created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except ValueError:
                return None
        else:
            return None
        
        # Check staleness
        if job_created < critical_threshold:
            severity = 'critical'
            stuck_hours = (datetime.now(timezone.utc) - job_created).total_seconds() / 3600
        elif job_created < stale_threshold:
            severity = 'warning'
            stuck_hours = (datetime.now(timezone.utc) - job_created).total_seconds() / 3600
        else:
            return None  # Not stuck
        
        # Determine likely cause based on status and age
        likely_cause = self._diagnose_stuck_cause(job_data, stuck_hours)
        
        return {
            'severity': severity,
            'stuck_hours': round(stuck_hours, 1),
            'job_created_at': job_created.isoformat(),
            'current_status': status,
            'likely_cause': likely_cause,
            'job_id': job_data.get('job_id', 'unknown')
        }
    
    def _scan_video_statuses(self, db, stale_threshold: datetime, critical_threshold: datetime) -> List[Dict[str, Any]]:
        """Scan for videos stuck in intermediate processing states."""
        stuck_videos = []
        
        try:
            # Query videos in non-final states
            stuck_statuses = ['transcription_queued', 'transcribing', 'summarizing']
            
            for status in stuck_statuses:
                videos_query = (db.collection('videos')
                              .where('status', '==', status)
                              .where('updated_at', '<', stale_threshold)
                              .limit(100))
                
                for video_doc in videos_query.stream():
                    video_data = video_doc.to_dict()
                    updated_at = video_data.get('updated_at')
                    
                    if updated_at:
                        if hasattr(updated_at, 'replace'):
                            last_update = updated_at.replace(tzinfo=timezone.utc)
                        else:
                            continue
                        
                        stuck_hours = (datetime.now(timezone.utc) - last_update).total_seconds() / 3600
                        
                        severity = 'critical' if last_update < critical_threshold else 'warning'
                        
                        stuck_videos.append({
                            'job_ref': f"videos/{video_doc.id}",
                            'agent': 'video_processing',
                            'job_type': f'video_{status}',
                            'job_id': video_doc.id,
                            'video_id': video_data.get('video_id'),
                            'current_status': status,
                            'severity': severity,
                            'stuck_hours': round(stuck_hours, 1),
                            'job_created_at': video_data.get('created_at', '').isoformat() if hasattr(video_data.get('created_at'), 'isoformat') else 'unknown',
                            'likely_cause': self._diagnose_video_stuck_cause(status, stuck_hours)
                        })
                        
        except Exception:
            # Continue if video scanning fails
            pass
        
        return stuck_videos
    
    def _diagnose_stuck_cause(self, job_data: Dict[str, Any], stuck_hours: float) -> str:
        """Diagnose the likely cause of a stuck job."""
        job_type = job_data.get('job_type', 'unknown')
        status = job_data.get('status', 'unknown')
        retry_count = job_data.get('retry_count', 0)
        
        if retry_count > 0:
            return "retry_loop"
        elif stuck_hours > 24:
            return "abandoned_job"
        elif job_type in ['single_video', 'batch_transcribe'] and status == 'pending':
            return "transcription_queue_backlog"
        elif job_type in ['channel_scrape', 'sheet_backfill'] and status == 'pending':
            return "quota_exhaustion"
        elif status == 'in_progress':
            return "processing_hang"
        elif status == 'pending':
            return "queue_backlog"
        else:
            return "unknown_bottleneck"
    
    def _diagnose_video_stuck_cause(self, status: str, stuck_hours: float) -> str:
        """Diagnose why a video is stuck in processing."""
        if status == 'transcription_queued' and stuck_hours > 6:
            return "transcription_service_down"
        elif status == 'transcribing' and stuck_hours > 4:
            return "transcription_timeout"
        elif status == 'summarizing' and stuck_hours > 2:
            return "llm_service_issues"
        else:
            return "processing_delay"
    
    def _analyze_stuck_patterns(self, stuck_jobs: List[Dict[str, Any]], stale_threshold: datetime, critical_threshold: datetime) -> Dict[str, Any]:
        """Analyze patterns in stuck jobs."""
        if not stuck_jobs:
            return {
                "total_stuck": 0,
                "by_severity": {"warning": 0, "critical": 0},
                "by_agent": {},
                "by_cause": {},
                "by_job_type": {},
                "average_stuck_hours": 0
            }
        
        # Analyze by severity
        by_severity = {"warning": 0, "critical": 0}
        for job in stuck_jobs:
            by_severity[job['severity']] += 1
        
        # Analyze by agent
        by_agent = {}
        for job in stuck_jobs:
            agent = job.get('agent', 'unknown')
            by_agent[agent] = by_agent.get(agent, 0) + 1
        
        # Analyze by cause
        by_cause = {}
        for job in stuck_jobs:
            cause = job.get('likely_cause', 'unknown')
            by_cause[cause] = by_cause.get(cause, 0) + 1
        
        # Analyze by job type
        by_job_type = {}
        for job in stuck_jobs:
            job_type = job.get('job_type', 'unknown')
            by_job_type[job_type] = by_job_type.get(job_type, 0) + 1
        
        # Calculate average stuck time
        total_stuck_hours = sum(job.get('stuck_hours', 0) for job in stuck_jobs)
        avg_stuck_hours = total_stuck_hours / len(stuck_jobs)
        
        return {
            "total_stuck": len(stuck_jobs),
            "by_severity": by_severity,
            "by_agent": by_agent,
            "by_cause": by_cause,
            "by_job_type": by_job_type,
            "average_stuck_hours": round(avg_stuck_hours, 1),
            "longest_stuck_hours": max((job.get('stuck_hours', 0) for job in stuck_jobs), default=0)
        }
    
    def _generate_escalations(self, stuck_jobs: List[Dict[str, Any]], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate escalation actions for stuck jobs."""
        escalations = []
        
        # Critical job escalations
        critical_jobs = [job for job in stuck_jobs if job['severity'] == 'critical']
        if critical_jobs:
            escalations.append({
                "type": "critical_jobs_alert",
                "priority": "urgent",
                "job_count": len(critical_jobs),
                "action": "Immediate manual intervention required",
                "affected_jobs": [job['job_ref'] for job in critical_jobs[:5]],  # Top 5
                "escalate_to": "operations_team"
            })
        
        # Agent-specific escalations
        by_agent = analysis.get('by_agent', {})
        for agent, count in by_agent.items():
            if count >= 5:  # Many stuck jobs for one agent
                escalations.append({
                    "type": "agent_bottleneck",
                    "priority": "high",
                    "agent": agent,
                    "stuck_count": count,
                    "action": f"Investigate {agent} agent performance and capacity",
                    "escalate_to": "engineering_team"
                })
        
        # Cause-specific escalations
        by_cause = analysis.get('by_cause', {})
        for cause, count in by_cause.items():
            if count >= 3 and cause in ['quota_exhaustion', 'transcription_service_down', 'retry_loop']:
                escalations.append({
                    "type": "systemic_issue",
                    "priority": "high",
                    "root_cause": cause,
                    "affected_count": count,
                    "action": self._get_cause_specific_action(cause),
                    "escalate_to": "engineering_team"
                })
        
        return escalations
    
    def _get_cause_specific_action(self, cause: str) -> str:
        """Get specific action for a diagnosed cause."""
        actions = {
            "quota_exhaustion": "Review quota limits and implement better throttling",
            "transcription_service_down": "Check AssemblyAI service status and failover options",
            "retry_loop": "Review retry logic and consider circuit breaker patterns",
            "processing_hang": "Restart affected agents and investigate memory leaks",
            "queue_backlog": "Scale up processing capacity or optimize job prioritization",
            "abandoned_job": "Clean up orphaned jobs and improve job lifecycle management"
        }
        return actions.get(cause, "Investigate root cause and implement appropriate fix")
    
    def _calculate_health_impact(self, stuck_jobs: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate the health impact of stuck jobs on the system."""
        total_stuck = analysis.get('total_stuck', 0)
        critical_count = analysis.get('by_severity', {}).get('critical', 0)
        
        # Calculate impact score (0-100, lower is worse)
        impact_score = 100
        
        # Penalize based on total stuck jobs
        if total_stuck > 0:
            impact_score -= min(50, total_stuck * 5)  # Max 50 point penalty
        
        # Extra penalty for critical jobs
        if critical_count > 0:
            impact_score -= min(30, critical_count * 10)  # Max 30 point penalty
        
        # Penalty for long stuck times
        avg_stuck = analysis.get('average_stuck_hours', 0)
        if avg_stuck > 6:
            impact_score -= min(20, (avg_stuck - 6) * 2)
        
        impact_score = max(0, impact_score)
        
        if impact_score >= 80:
            severity = "low"
        elif impact_score >= 60:
            severity = "medium"
        elif impact_score >= 40:
            severity = "high"
        else:
            severity = "critical"
        
        return {
            "impact_score": round(impact_score, 1),
            "severity": severity,
            "affected_agents": list(analysis.get('by_agent', {}).keys()),
            "pipeline_blocked": critical_count > 0,
            "estimated_backlog_hours": sum(job.get('stuck_hours', 0) for job in stuck_jobs)
        }
    
    def _generate_recommendations(self, analysis: Dict[str, Any], health_impact: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate operational recommendations based on stuck job analysis."""
        recommendations = []
        
        total_stuck = analysis.get('total_stuck', 0)
        
        if total_stuck == 0:
            recommendations.append({
                "category": "maintenance",
                "priority": "low",
                "action": "System operating normally - consider preventive maintenance",
                "rationale": "No stuck jobs detected"
            })
            return recommendations
        
        # High-level recommendations
        if health_impact.get('severity') in ['critical', 'high']:
            recommendations.append({
                "category": "immediate_action",
                "priority": "urgent",
                "action": "Implement emergency job recovery procedures",
                "rationale": f"System health severely impacted with {total_stuck} stuck jobs"
            })
        
        # Agent-specific recommendations
        by_agent = analysis.get('by_agent', {})
        worst_agent = max(by_agent.items(), key=lambda x: x[1]) if by_agent else None
        if worst_agent and worst_agent[1] >= 3:
            recommendations.append({
                "category": "capacity_planning",
                "priority": "high",
                "action": f"Scale up {worst_agent[0]} agent capacity or optimize processing",
                "rationale": f"{worst_agent[0]} has {worst_agent[1]} stuck jobs"
            })
        
        # Cause-based recommendations
        by_cause = analysis.get('by_cause', {})
        top_cause = max(by_cause.items(), key=lambda x: x[1]) if by_cause else None
        if top_cause and top_cause[1] >= 2:
            recommendations.append({
                "category": "root_cause",
                "priority": "medium",
                "action": self._get_cause_specific_action(top_cause[0]),
                "rationale": f"'{top_cause[0]}' is the primary cause of {top_cause[1]} stuck jobs"
            })
        
        return recommendations
    
    def _initialize_firestore(self):
        """Initialize Firestore client with proper authentication."""
        try:
            project_id = get_required_env_var("GCP_PROJECT_ID", "Google Cloud Project ID for Firestore")
            credentials_path = get_required_env_var("GOOGLE_APPLICATION_CREDENTIALS", "Google service account credentials file path")
            
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Service account file not found: {credentials_path}")
            
            return firestore.Client(project=project_id)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firestore client: {str(e)}")


if __name__ == "__main__":
    # Test stuck job scanning
    print("Testing stuck_job_scanner...")
    test_tool = StuckJobScanner(
        staleness_threshold_hours=4,
        critical_threshold_hours=12,
        include_status_breakdown=True
    )
    
    try:
        result = test_tool.run()
        print("Stuck job scanner result:")
        print(result)
        
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            analysis = data['analysis']
            print(f"Total stuck jobs: {analysis['total_stuck']}")
            print(f"Critical: {analysis['by_severity']['critical']}, Warning: {analysis['by_severity']['warning']}")
            print(f"Health impact: {data['health_impact']['severity']} (score: {data['health_impact']['impact_score']})")
            print(f"Escalations: {len(data['escalations'])}")
            print(f"Recommendations: {len(data['recommendations'])}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\nTesting with aggressive thresholds...")
    test_tool_aggressive = StuckJobScanner(
        staleness_threshold_hours=1,
        critical_threshold_hours=3,
        include_status_breakdown=False
    )
    
    try:
        result = test_tool_aggressive.run()
        data = json.loads(result)
        if "error" not in data:
            print(f"Aggressive scan: {data['analysis']['total_stuck']} stuck jobs")
        
    except Exception as e:
        print(f"Aggressive test error: {str(e)}")