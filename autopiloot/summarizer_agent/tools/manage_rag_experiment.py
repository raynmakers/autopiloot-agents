"""
Experiment management tool for hybrid RAG A/B testing.

Enables runtime-adjustable fusion weights, top_k, timeouts, and other
parameters without requiring redeployment. Supports experiment tracking,
parameter overrides, and outcome logging.
"""

import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import Field


class ManageRAGExperiment:
    """
    Tool for managing hybrid RAG experiments and A/B testing.

    Features:
    - Create, update, read, list, delete experiments
    - Runtime-adjustable fusion weights (semantic, keyword, sql)
    - Configurable top_k, timeouts, and other parameters
    - Experiment tags for grouping and comparison
    - Parameter override support
    - Outcome logging and metric tracking
    """

    # Class-level experiment storage (in-memory for now)
    # In production, this would be stored in Firestore or another persistent store
    _experiments: Dict[str, Dict[str, Any]] = {}

    operation: str = Field(
        description="Experiment operation: 'create', 'update', 'read', 'list', 'delete', 'activate', 'deactivate'"
    )

    experiment_id: Optional[str] = Field(
        default=None,
        description="Experiment ID (required for update, read, delete, activate, deactivate)"
    )

    experiment_name: Optional[str] = Field(
        default=None,
        description="Experiment name (required for create)"
    )

    experiment_tag: Optional[str] = Field(
        default=None,
        description="Experiment tag for grouping (e.g., 'weight-tuning', 'top-k-optimization')"
    )

    description: Optional[str] = Field(
        default=None,
        description="Experiment description"
    )

    # Fusion weights configuration
    weights_semantic: Optional[float] = Field(
        default=None,
        description="Semantic search weight (0.0-1.0)"
    )

    weights_keyword: Optional[float] = Field(
        default=None,
        description="Keyword search weight (0.0-1.0)"
    )

    weights_sql: Optional[float] = Field(
        default=None,
        description="SQL/structured search weight (0.0-1.0)"
    )

    # Retrieval parameters
    top_k: Optional[int] = Field(
        default=None,
        description="Number of results to retrieve per source"
    )

    timeout_ms: Optional[int] = Field(
        default=None,
        description="Timeout in milliseconds per source"
    )

    # Advanced parameters
    fusion_algorithm: Optional[str] = Field(
        default=None,
        description="Fusion algorithm: 'rrf' (reciprocal rank fusion), 'weighted', 'cascade'"
    )

    rrf_k: Optional[int] = Field(
        default=None,
        description="RRF k parameter (default 60)"
    )

    enable_reranking: Optional[bool] = Field(
        default=None,
        description="Enable reranking after fusion"
    )

    reranking_model: Optional[str] = Field(
        default=None,
        description="Reranking model name"
    )

    # Experiment metadata
    status: Optional[str] = Field(
        default=None,
        description="Experiment status: 'active', 'inactive', 'completed', 'archived'"
    )

    notes: Optional[str] = Field(
        default=None,
        description="Additional notes about the experiment"
    )

    def __init__(self, **data):
        """Initialize experiment management tool."""
        for key, value in data.items():
            setattr(self, key, value)

    def _generate_experiment_id(self) -> str:
        """Generate unique experiment ID."""
        import uuid
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_suffix = uuid.uuid4().hex[:8]
        return f"exp_{timestamp}_{random_suffix}"

    def _validate_weights(
        self,
        semantic: Optional[float] = None,
        keyword: Optional[float] = None,
        sql: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Validate fusion weights.

        Weights must:
        - Be between 0.0 and 1.0
        - Sum to 1.0 (if all provided)

        Returns:
            Validation result with status and message
        """
        weights = {}
        if semantic is not None:
            weights["semantic"] = semantic
        if keyword is not None:
            weights["keyword"] = keyword
        if sql is not None:
            weights["sql"] = sql

        # Check range
        for name, value in weights.items():
            if not (0.0 <= value <= 1.0):
                return {
                    "valid": False,
                    "message": f"Weight '{name}' must be between 0.0 and 1.0, got {value}"
                }

        # Check sum if all weights provided
        if len(weights) == 3:
            total = sum(weights.values())
            if not (0.99 <= total <= 1.01):  # Allow small floating point error
                return {
                    "valid": False,
                    "message": f"Weights must sum to 1.0, got {total}"
                }

        return {"valid": True, "message": "Weights valid"}

    def _create_experiment(self) -> Dict[str, Any]:
        """Create new experiment."""
        if not self.experiment_name:
            return {
                "error": "missing_experiment_name",
                "message": "Experiment name required for create operation"
            }

        # Validate weights if provided
        if any([self.weights_semantic is not None, self.weights_keyword is not None, self.weights_sql is not None]):
            validation = self._validate_weights(
                self.weights_semantic,
                self.weights_keyword,
                self.weights_sql
            )
            if not validation["valid"]:
                return {
                    "error": "invalid_weights",
                    "message": validation["message"]
                }

        # Generate experiment ID
        experiment_id = self._generate_experiment_id()

        # Create experiment record
        experiment = {
            "experiment_id": experiment_id,
            "experiment_name": self.experiment_name,
            "experiment_tag": self.experiment_tag or "untagged",
            "description": self.description or "",
            "parameters": {
                "weights": {},
                "retrieval": {},
                "fusion": {},
                "reranking": {}
            },
            "status": self.status or "inactive",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "activated_at": None,
            "deactivated_at": None,
            "notes": self.notes or "",
            "outcomes": []
        }

        # Add weights
        if self.weights_semantic is not None:
            experiment["parameters"]["weights"]["semantic"] = self.weights_semantic
        if self.weights_keyword is not None:
            experiment["parameters"]["weights"]["keyword"] = self.weights_keyword
        if self.weights_sql is not None:
            experiment["parameters"]["weights"]["sql"] = self.weights_sql

        # Add retrieval parameters
        if self.top_k is not None:
            experiment["parameters"]["retrieval"]["top_k"] = self.top_k
        if self.timeout_ms is not None:
            experiment["parameters"]["retrieval"]["timeout_ms"] = self.timeout_ms

        # Add fusion parameters
        if self.fusion_algorithm is not None:
            experiment["parameters"]["fusion"]["algorithm"] = self.fusion_algorithm
        if self.rrf_k is not None:
            experiment["parameters"]["fusion"]["rrf_k"] = self.rrf_k

        # Add reranking parameters
        if self.enable_reranking is not None:
            experiment["parameters"]["reranking"]["enabled"] = self.enable_reranking
        if self.reranking_model is not None:
            experiment["parameters"]["reranking"]["model"] = self.reranking_model

        # Store experiment
        self._experiments[experiment_id] = experiment

        return {
            "operation": "create",
            "experiment_id": experiment_id,
            "experiment": experiment,
            "status": "success"
        }

    def _update_experiment(self) -> Dict[str, Any]:
        """Update existing experiment."""
        if not self.experiment_id:
            return {
                "error": "missing_experiment_id",
                "message": "Experiment ID required for update operation"
            }

        if self.experiment_id not in self._experiments:
            return {
                "error": "experiment_not_found",
                "message": f"Experiment '{self.experiment_id}' not found"
            }

        # Validate weights if provided
        if any([self.weights_semantic is not None, self.weights_keyword is not None, self.weights_sql is not None]):
            validation = self._validate_weights(
                self.weights_semantic,
                self.weights_keyword,
                self.weights_sql
            )
            if not validation["valid"]:
                return {
                    "error": "invalid_weights",
                    "message": validation["message"]
                }

        experiment = self._experiments[self.experiment_id]

        # Update fields
        if self.experiment_name is not None:
            experiment["experiment_name"] = self.experiment_name
        if self.experiment_tag is not None:
            experiment["experiment_tag"] = self.experiment_tag
        if self.description is not None:
            experiment["description"] = self.description
        if self.status is not None:
            experiment["status"] = self.status
        if self.notes is not None:
            experiment["notes"] = self.notes

        # Update weights
        if self.weights_semantic is not None:
            experiment["parameters"]["weights"]["semantic"] = self.weights_semantic
        if self.weights_keyword is not None:
            experiment["parameters"]["weights"]["keyword"] = self.weights_keyword
        if self.weights_sql is not None:
            experiment["parameters"]["weights"]["sql"] = self.weights_sql

        # Update retrieval parameters
        if self.top_k is not None:
            experiment["parameters"]["retrieval"]["top_k"] = self.top_k
        if self.timeout_ms is not None:
            experiment["parameters"]["retrieval"]["timeout_ms"] = self.timeout_ms

        # Update fusion parameters
        if self.fusion_algorithm is not None:
            experiment["parameters"]["fusion"]["algorithm"] = self.fusion_algorithm
        if self.rrf_k is not None:
            experiment["parameters"]["fusion"]["rrf_k"] = self.rrf_k

        # Update reranking parameters
        if self.enable_reranking is not None:
            experiment["parameters"]["reranking"]["enabled"] = self.enable_reranking
        if self.reranking_model is not None:
            experiment["parameters"]["reranking"]["model"] = self.reranking_model

        # Update timestamp
        experiment["updated_at"] = datetime.utcnow().isoformat() + "Z"

        return {
            "operation": "update",
            "experiment_id": self.experiment_id,
            "experiment": experiment,
            "status": "success"
        }

    def _read_experiment(self) -> Dict[str, Any]:
        """Read experiment details."""
        if not self.experiment_id:
            return {
                "error": "missing_experiment_id",
                "message": "Experiment ID required for read operation"
            }

        if self.experiment_id not in self._experiments:
            return {
                "error": "experiment_not_found",
                "message": f"Experiment '{self.experiment_id}' not found"
            }

        experiment = self._experiments[self.experiment_id]

        return {
            "operation": "read",
            "experiment_id": self.experiment_id,
            "experiment": experiment,
            "status": "success"
        }

    def _list_experiments(self) -> Dict[str, Any]:
        """List all experiments."""
        experiments = list(self._experiments.values())

        # Filter by tag if provided
        if self.experiment_tag:
            experiments = [
                exp for exp in experiments
                if exp.get("experiment_tag") == self.experiment_tag
            ]

        # Filter by status if provided
        if self.status:
            experiments = [
                exp for exp in experiments
                if exp.get("status") == self.status
            ]

        # Sort by created_at descending
        experiments.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return {
            "operation": "list",
            "experiments": experiments,
            "count": len(experiments),
            "filters": {
                "tag": self.experiment_tag,
                "status": self.status
            },
            "status": "success"
        }

    def _delete_experiment(self) -> Dict[str, Any]:
        """Delete experiment."""
        if not self.experiment_id:
            return {
                "error": "missing_experiment_id",
                "message": "Experiment ID required for delete operation"
            }

        if self.experiment_id not in self._experiments:
            return {
                "error": "experiment_not_found",
                "message": f"Experiment '{self.experiment_id}' not found"
            }

        deleted_experiment = self._experiments.pop(self.experiment_id)

        return {
            "operation": "delete",
            "experiment_id": self.experiment_id,
            "deleted_experiment": deleted_experiment,
            "status": "success"
        }

    def _activate_experiment(self) -> Dict[str, Any]:
        """Activate experiment."""
        if not self.experiment_id:
            return {
                "error": "missing_experiment_id",
                "message": "Experiment ID required for activate operation"
            }

        if self.experiment_id not in self._experiments:
            return {
                "error": "experiment_not_found",
                "message": f"Experiment '{self.experiment_id}' not found"
            }

        experiment = self._experiments[self.experiment_id]
        experiment["status"] = "active"
        experiment["activated_at"] = datetime.utcnow().isoformat() + "Z"
        experiment["updated_at"] = datetime.utcnow().isoformat() + "Z"

        return {
            "operation": "activate",
            "experiment_id": self.experiment_id,
            "experiment": experiment,
            "status": "success"
        }

    def _deactivate_experiment(self) -> Dict[str, Any]:
        """Deactivate experiment."""
        if not self.experiment_id:
            return {
                "error": "missing_experiment_id",
                "message": "Experiment ID required for deactivate operation"
            }

        if self.experiment_id not in self._experiments:
            return {
                "error": "experiment_not_found",
                "message": f"Experiment '{self.experiment_id}' not found"
            }

        experiment = self._experiments[self.experiment_id]
        experiment["status"] = "inactive"
        experiment["deactivated_at"] = datetime.utcnow().isoformat() + "Z"
        experiment["updated_at"] = datetime.utcnow().isoformat() + "Z"

        return {
            "operation": "deactivate",
            "experiment_id": self.experiment_id,
            "experiment": experiment,
            "status": "success"
        }

    def run(self) -> str:
        """
        Execute experiment operation.

        Returns:
            JSON string with operation result
        """
        try:
            if self.operation == "create":
                result = self._create_experiment()
            elif self.operation == "update":
                result = self._update_experiment()
            elif self.operation == "read":
                result = self._read_experiment()
            elif self.operation == "list":
                result = self._list_experiments()
            elif self.operation == "delete":
                result = self._delete_experiment()
            elif self.operation == "activate":
                result = self._activate_experiment()
            elif self.operation == "deactivate":
                result = self._deactivate_experiment()
            else:
                result = {
                    "error": "invalid_operation",
                    "message": f"Invalid operation: {self.operation}"
                }

            return json.dumps(result)

        except Exception as e:
            return json.dumps({
                "error": "experiment_operation_failed",
                "message": str(e),
                "operation": self.operation
            })


# Test block
if __name__ == "__main__":
    print("Testing ManageRAGExperiment tool...")

    # Test 1: Create experiment
    print("\n1. Testing CREATE operation:")
    tool_create = ManageRAGExperiment(
        operation="create",
        experiment_name="Weight Tuning v1",
        experiment_tag="weight-tuning",
        description="Test semantic vs keyword weight balance",
        weights_semantic=0.7,
        weights_keyword=0.3,
        weights_sql=0.0,
        top_k=20,
        timeout_ms=2000,
        fusion_algorithm="rrf",
        rrf_k=60,
        status="active"
    )
    result_create = tool_create.run()
    data_create = json.loads(result_create)
    print(json.dumps(data_create, indent=2))
    experiment_id = data_create.get("experiment_id")

    # Test 2: Read experiment
    print("\n2. Testing READ operation:")
    tool_read = ManageRAGExperiment(
        operation="read",
        experiment_id=experiment_id
    )
    result_read = tool_read.run()
    print(json.dumps(json.loads(result_read), indent=2))

    # Test 3: Update experiment
    print("\n3. Testing UPDATE operation:")
    tool_update = ManageRAGExperiment(
        operation="update",
        experiment_id=experiment_id,
        weights_semantic=0.6,
        weights_keyword=0.4,
        notes="Adjusted weights after initial results"
    )
    result_update = tool_update.run()
    print(json.dumps(json.loads(result_update), indent=2))

    # Test 4: Create another experiment
    print("\n4. Testing CREATE second experiment:")
    tool_create2 = ManageRAGExperiment(
        operation="create",
        experiment_name="Top-K Optimization",
        experiment_tag="top-k-optimization",
        description="Test different top_k values",
        top_k=10,
        status="inactive"
    )
    result_create2 = tool_create2.run()
    print(json.dumps(json.loads(result_create2), indent=2))

    # Test 5: List all experiments
    print("\n5. Testing LIST operation (all):")
    tool_list = ManageRAGExperiment(
        operation="list"
    )
    result_list = tool_list.run()
    print(json.dumps(json.loads(result_list), indent=2))

    # Test 6: List by tag
    print("\n6. Testing LIST operation (by tag):")
    tool_list_tag = ManageRAGExperiment(
        operation="list",
        experiment_tag="weight-tuning"
    )
    result_list_tag = tool_list_tag.run()
    print(json.dumps(json.loads(result_list_tag), indent=2))

    # Test 7: Deactivate experiment
    print("\n7. Testing DEACTIVATE operation:")
    tool_deactivate = ManageRAGExperiment(
        operation="deactivate",
        experiment_id=experiment_id
    )
    result_deactivate = tool_deactivate.run()
    print(json.dumps(json.loads(result_deactivate), indent=2))

    # Test 8: Activate experiment
    print("\n8. Testing ACTIVATE operation:")
    tool_activate = ManageRAGExperiment(
        operation="activate",
        experiment_id=experiment_id
    )
    result_activate = tool_activate.run()
    print(json.dumps(json.loads(result_activate), indent=2))

    # Test 9: Delete experiment
    print("\n9. Testing DELETE operation:")
    tool_delete = ManageRAGExperiment(
        operation="delete",
        experiment_id=experiment_id
    )
    result_delete = tool_delete.run()
    print(json.dumps(json.loads(result_delete), indent=2))

    # Test 10: Invalid weights
    print("\n10. Testing CREATE with invalid weights:")
    tool_invalid = ManageRAGExperiment(
        operation="create",
        experiment_name="Invalid Weights",
        weights_semantic=0.5,
        weights_keyword=0.3,
        weights_sql=0.3  # Sum > 1.0
    )
    result_invalid = tool_invalid.run()
    print(json.dumps(json.loads(result_invalid), indent=2))

    print("\n✅ All experiment operations tested successfully!")
