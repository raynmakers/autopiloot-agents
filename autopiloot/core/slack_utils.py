"""
Slack utilities for Autopiloot Agency.
Centralized channel normalization, block formatting, and message composition
for consistent Slack integration across all agents.
"""

import os
import re
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timezone


def normalize_channel_name(channel: str) -> str:
    """
    Normalize Slack channel name to standard format.
    
    Args:
        channel: Raw channel name (with or without #)
        
    Returns:
        Normalized channel name without # prefix
        
    Example:
        normalize_channel_name("#ops-autopiloot") -> "ops-autopiloot"
        normalize_channel_name("alerts") -> "alerts"
    """
    if not channel or not isinstance(channel, str):
        return "general"
    
    # Remove # prefix if present
    normalized = channel.strip().lstrip('#')
    
    # Slack channel names must be lowercase and use hyphens
    normalized = normalized.lower()
    
    # Replace spaces and underscores with hyphens
    normalized = re.sub(r'[_\s]+', '-', normalized)
    
    # Remove invalid characters (keep only alphanumeric and hyphens)
    normalized = re.sub(r'[^a-z0-9\-]', '', normalized)
    
    # Remove duplicate hyphens
    normalized = re.sub(r'-+', '-', normalized)
    
    # Remove leading/trailing hyphens
    normalized = normalized.strip('-')
    
    # Fallback to general if empty
    return normalized if normalized else "general"


def get_channel_for_alert_type(alert_type: str, default_channel: str = "ops-autopiloot") -> str:
    """
    Get appropriate Slack channel for a specific alert type.
    
    Args:
        alert_type: Type of alert (error, warning, info, critical)
        default_channel: Fallback channel name
        
    Returns:
        Normalized channel name for the alert type
    """
    # Environment-based channel mapping
    channel_mapping = {
        "error": os.getenv("SLACK_ERROR_CHANNEL", "alerts"),
        "critical": os.getenv("SLACK_CRITICAL_CHANNEL", "alerts-critical"),
        "warning": os.getenv("SLACK_WARNING_CHANNEL", "alerts"),
        "info": os.getenv("SLACK_INFO_CHANNEL", default_channel),
        "dlq": os.getenv("SLACK_DLQ_CHANNEL", "alerts-dlq"),
        "budget": os.getenv("SLACK_BUDGET_CHANNEL", "ops-budget"),
        "quota": os.getenv("SLACK_QUOTA_CHANNEL", "ops-quota"),
        "daily": os.getenv("SLACK_DAILY_CHANNEL", default_channel),
    }
    
    channel = channel_mapping.get(alert_type.lower(), default_channel)
    return normalize_channel_name(channel)


def format_alert_blocks(
    title: str,
    message: str,
    alert_type: str = "info",
    details: Optional[Dict[str, Any]] = None,
    timestamp: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Format alert message as Slack blocks with consistent styling.
    
    Args:
        title: Alert title
        message: Main alert message
        alert_type: Type of alert for color coding
        details: Additional details to include
        timestamp: Alert timestamp (defaults to now)
        
    Returns:
        List of Slack block objects
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    # Color mapping for different alert types
    color_mapping = {
        "critical": "#FF0000",  # Red
        "error": "#FF6B6B",     # Light red
        "warning": "#FFD93D",   # Yellow
        "info": "#6BCF7F",      # Green
        "dlq": "#FF8C00",       # Orange
        "budget": "#9B59B6",    # Purple
        "quota": "#E74C3C",     # Dark red
        "daily": "#3498DB"      # Blue
    }
    
    color = color_mapping.get(alert_type.lower(), "#6BCF7F")
    
    # Emoji mapping for alert types
    emoji_mapping = {
        "critical": "🚨",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
        "dlq": "🔄",
        "budget": "💰",
        "quota": "📊",
        "daily": "📅"
    }
    
    emoji = emoji_mapping.get(alert_type.lower(), "ℹ️")
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {title}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": message
            }
        }
    ]
    
    # Add details section if provided
    if details:
        detail_fields = []
        for key, value in details.items():
            # Format key as title case
            formatted_key = key.replace('_', ' ').title()
            detail_fields.append({
                "type": "mrkdwn",
                "text": f"*{formatted_key}:*\n{value}"
            })
        
        # Add fields in groups of 2 for better layout
        for i in range(0, len(detail_fields), 2):
            fields_batch = detail_fields[i:i+2]
            blocks.append({
                "type": "section",
                "fields": fields_batch
            })
    
    # Add timestamp footer
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"⏰ {timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC | Autopiloot Agency"
            }
        ]
    })
    
    return blocks


def format_daily_summary_blocks(
    date: str,
    metrics: Dict[str, Any],
    highlights: List[str] = None,
    issues: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Format daily summary as Slack blocks with structured layout.
    
    Args:
        date: Date of the summary (YYYY-MM-DD)
        metrics: Dictionary of key metrics
        highlights: List of notable achievements
        issues: List of issues or concerns
        
    Returns:
        List of Slack block objects
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📅 Daily Summary - {date}",
                "emoji": True
            }
        },
        {
            "type": "divider"
        }
    ]
    
    # Add metrics section
    if metrics:
        metric_fields = []
        for key, value in metrics.items():
            formatted_key = key.replace('_', ' ').title()
            if isinstance(value, (int, float)):
                if key.endswith('_usd') or key.startswith('cost'):
                    formatted_value = f"${value:.2f}"
                elif key.endswith('_count') or key.endswith('_total'):
                    formatted_value = f"{value:,}"
                else:
                    formatted_value = str(value)
            else:
                formatted_value = str(value)
            
            metric_fields.append({
                "type": "mrkdwn",
                "text": f"*{formatted_key}:*\n{formatted_value}"
            })
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*📊 Key Metrics*"
            }
        })
        
        # Add metrics in groups of 2
        for i in range(0, len(metric_fields), 2):
            fields_batch = metric_fields[i:i+2]
            blocks.append({
                "type": "section",
                "fields": fields_batch
            })
    
    # Add highlights section
    if highlights:
        highlights_text = "\n".join([f"• {highlight}" for highlight in highlights])
        blocks.extend([
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*✨ Highlights*\n{highlights_text}"
                }
            }
        ])
    
    # Add issues section
    if issues:
        issues_text = "\n".join([f"• {issue}" for issue in issues])
        blocks.extend([
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*⚠️ Issues & Concerns*\n{issues_text}"
                }
            }
        ])
    
    # Add footer
    blocks.extend([
        {
            "type": "divider"
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Generated by Autopiloot Agency Observability System"
                }
            ]
        }
    ])
    
    return blocks


def format_table_blocks(
    title: str,
    headers: List[str],
    rows: List[List[str]],
    max_rows: int = 10
) -> List[Dict[str, Any]]:
    """
    Format tabular data as Slack blocks with ASCII table layout.
    
    Args:
        title: Table title
        headers: Column headers
        rows: List of row data
        max_rows: Maximum rows to display
        
    Returns:
        List of Slack block objects
    """
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title}*"
            }
        }
    ]
    
    if not rows:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_No data available_"
            }
        })
        return blocks
    
    # Limit rows to prevent message size issues
    display_rows = rows[:max_rows]
    truncated = len(rows) > max_rows
    
    # Calculate column widths
    all_data = [headers] + display_rows
    col_widths = []
    for col_idx in range(len(headers)):
        max_width = max(len(str(row[col_idx])) for row in all_data if col_idx < len(row))
        col_widths.append(min(max_width, 15))  # Cap width for readability
    
    # Format table as monospace text
    table_lines = []
    
    # Header row
    header_line = " | ".join(header.ljust(col_widths[i])[:col_widths[i]] for i, header in enumerate(headers))
    table_lines.append(header_line)
    
    # Separator
    separator = "-|-".join("-" * width for width in col_widths)
    table_lines.append(separator)
    
    # Data rows
    for row in display_rows:
        row_line = " | ".join(
            str(row[i]).ljust(col_widths[i])[:col_widths[i]] if i < len(row) else " " * col_widths[i]
            for i in range(len(headers))
        )
        table_lines.append(row_line)
    
    if truncated:
        table_lines.append(f"... and {len(rows) - max_rows} more rows")
    
    table_text = "```\n" + "\n".join(table_lines) + "\n```"
    
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": table_text
        }
    })
    
    return blocks


def validate_slack_message(blocks: List[Dict[str, Any]]) -> bool:
    """
    Validate Slack message blocks for basic compliance.
    
    Args:
        blocks: List of Slack block objects
        
    Returns:
        True if blocks are valid, False otherwise
    """
    if not isinstance(blocks, list):
        return False
    
    if len(blocks) == 0:
        return False
    
    # Check each block has required fields
    for block in blocks:
        if not isinstance(block, dict):
            return False
        
        if "type" not in block:
            return False
        
        block_type = block["type"]
        
        # Basic validation for common block types
        if block_type == "section" and "text" not in block and "fields" not in block:
            return False
        
        if block_type == "header" and "text" not in block:
            return False
    
    return True


def create_slack_webhook_payload(
    channel: str,
    blocks: List[Dict[str, Any]],
    text: str = "",
    username: str = "Autopiloot Agency"
) -> Dict[str, Any]:
    """
    Create complete Slack webhook payload.
    
    Args:
        channel: Target channel (will be normalized)
        blocks: Slack block objects
        text: Fallback text for notifications
        username: Bot username
        
    Returns:
        Complete webhook payload dict
    """
    return {
        "channel": f"#{normalize_channel_name(channel)}",
        "username": username,
        "text": text,
        "blocks": blocks,
        "unfurl_links": False,
        "unfurl_media": False
    }


# Convenience functions for common alert patterns
def create_error_alert(error_message: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Create standardized error alert blocks."""
    return format_alert_blocks(
        title="System Error",
        message=error_message,
        alert_type="error",
        details=context
    )


def create_warning_alert(warning_message: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Create standardized warning alert blocks."""
    return format_alert_blocks(
        title="System Warning",
        message=warning_message,
        alert_type="warning", 
        details=context
    )


def create_info_alert(info_message: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Create standardized info alert blocks."""
    return format_alert_blocks(
        title="System Information",
        message=info_message,
        alert_type="info",
        details=context
    )


def create_dlq_alert(job_count: int, details: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Create standardized DLQ alert blocks."""
    return format_alert_blocks(
        title="Dead Letter Queue Alert",
        message=f"Found {job_count} jobs in dead letter queue requiring attention.",
        alert_type="dlq",
        details=details
    )