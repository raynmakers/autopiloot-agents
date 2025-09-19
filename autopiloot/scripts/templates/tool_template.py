"""
{tool_description}

{tool_description}
"""

import json
import logging
from typing import Dict, Any, Optional
from pydantic import Field
from agency_swarm.tools import BaseTool
from config.env_loader import get_required_var, get_optional_var
from core.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class {tool_class_name}(BaseTool):
    """
    {tool_description}

    Attributes:
    {tool_attributes}

    Returns:
        JSON string with operation result and metadata
    """

    # Tool parameters
    {tool_parameters}

    def run(self) -> str:
        """
        Execute {tool_name} operation.

        Returns:
            JSON string with operation result
        """
        audit_logger = AuditLogger()

        try:
            # Validate environment and configuration
            self._validate_environment()

            # Log operation start
            audit_logger.log_action(
                actor="{agent_name_title}Agent",
                action="{tool_name}",
                entity="{tool_entity}",
                entity_id=str(getattr(self, 'entity_id', 'unknown')),
                details={{"operation": "start", "parameters": self._get_parameters()}}
            )

            # Core operation logic
            result = self._execute_operation()

            # Log successful completion
            audit_logger.log_action(
                actor="{agent_name_title}Agent",
                action="{tool_name}",
                entity="{tool_entity}",
                entity_id=str(getattr(self, 'entity_id', 'unknown')),
                details={{"operation": "completed", "result": result}}
            )

            return json.dumps({{
                "success": True,
                "operation": "{tool_name}",
                "result": result,
                "message": "{tool_description} completed successfully"
            }})

        except Exception as e:
            error_msg = f"{tool_description} failed: {{str(e)}}"
            logger.error(error_msg)

            # Log failure
            audit_logger.log_action(
                actor="{agent_name_title}Agent",
                action="{tool_name}",
                entity="{tool_entity}",
                entity_id=str(getattr(self, 'entity_id', 'unknown')),
                details={{"operation": "failed", "error": str(e)}}
            )

            return json.dumps({{
                "success": False,
                "operation": "{tool_name}",
                "error": "operation_failed",
                "message": error_msg,
                "details": {{"error_type": type(e).__name__, "error_message": str(e)}}
            }})

    def _validate_environment(self) -> None:
        """Validate required environment variables and configuration."""
        # Add environment validation logic here
        # Example:
        # get_required_var("REQUIRED_API_KEY")
        pass

    def _execute_operation(self) -> Dict[str, Any]:
        """
        Execute the core operation logic.

        Returns:
            Dict with operation results
        """
        # Implement core operation logic here

        # Placeholder implementation
        return {{
            "operation": "{tool_name}",
            "status": "completed",
            "timestamp": "2025-01-16T00:00:00Z"
        }}

    def _get_parameters(self) -> Dict[str, Any]:
        """Get tool parameters for logging."""
        return {{
            param: getattr(self, param, None)
            for param in {tool_parameter_names}
        }}


if __name__ == "__main__":
    # Test the tool
    try:
        tool = {tool_class_name}({tool_test_parameters})
        result = tool.run()
        print(f"Tool execution result: {{result}}")

    except Exception as e:
        print(f"Tool test failed: {{e}}")
        import traceback
        traceback.print_exc()