"""
List tracked Google Drive targets from configuration
Returns normalized targets with their settings for processing
"""

import os
import json
import sys
from typing import List, Dict, Any
from pydantic import Field
from agency_swarm.tools import BaseTool

# Add config directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from loader import load_app_config, get_config_value


class ListTrackedTargetsFromConfig(BaseTool):
    """
    Load and normalize Google Drive tracking targets from settings.yaml configuration.
    Returns list of configured files and folders with their tracking parameters.
    """

    include_defaults: bool = Field(
        default=True,
        description="Whether to include default settings for each target (sync_interval, max_file_size, etc.)"
    )

    def run(self) -> str:
        """
        Load tracked targets from configuration and return normalized list.

        Returns:
            JSON string containing list of tracked targets with their configuration
        """
        try:
            # Load app configuration
            config = load_app_config()

            # Get Drive tracking configuration
            drive_config = get_config_value("drive", {})
            tracking_config = drive_config.get("tracking", {})

            # Get targets list
            targets = tracking_config.get("targets", [])

            if not targets:
                return json.dumps({
                    "targets": [],
                    "message": "No tracking targets configured in settings.yaml"
                })

            # Get default settings if requested
            default_settings = {}
            if self.include_defaults:
                default_settings = {
                    "sync_interval_minutes": tracking_config.get("sync_interval_minutes", 60),
                    "max_file_size_mb": tracking_config.get("max_file_size_mb", 10),
                    "supported_formats": tracking_config.get("supported_formats", [
                        ".txt", ".md", ".pdf", ".docx", ".html", ".csv"
                    ])
                }

            # Normalize targets
            normalized_targets = []
            for target in targets:
                if not isinstance(target, dict):
                    continue

                # Ensure required fields
                if "id" not in target or "type" not in target:
                    continue

                normalized = {
                    "id": target.get("id"),
                    "type": target.get("type"),  # "file" or "folder"
                    "name": target.get("name", "Unnamed Target"),
                    "recursive": target.get("recursive", True) if target.get("type") == "folder" else False
                }

                # Add optional fields if present
                if "include_patterns" in target:
                    normalized["include_patterns"] = target.get("include_patterns")
                if "exclude_patterns" in target:
                    normalized["exclude_patterns"] = target.get("exclude_patterns")

                normalized_targets.append(normalized)

            # Get Zep namespace configuration
            rag_config = get_config_value("rag", {})
            zep_config = rag_config.get("zep", {})
            namespace_config = zep_config.get("namespace", {})
            zep_namespace = namespace_config.get("drive", "autopiloot_drive_content")

            result = {
                "targets": normalized_targets,
                "count": len(normalized_targets),
                "zep_namespace": zep_namespace
            }

            if self.include_defaults:
                result["defaults"] = default_settings

            return json.dumps(result)

        except Exception as e:
            return json.dumps({
                "error": "configuration_error",
                "message": f"Failed to load tracking targets: {str(e)}",
                "details": {
                    "type": type(e).__name__
                }
            })


if __name__ == "__main__":
    # Test the tool
    print("Testing ListTrackedTargetsFromConfig tool...")

    # Test without defaults
    tool = ListTrackedTargetsFromConfig(include_defaults=False)
    result = tool.run()
    print("\nTargets without defaults:")
    print(json.dumps(json.loads(result), indent=2))

    # Test with defaults
    tool = ListTrackedTargetsFromConfig(include_defaults=True)
    result = tool.run()
    print("\nTargets with defaults:")
    print(json.dumps(json.loads(result), indent=2))