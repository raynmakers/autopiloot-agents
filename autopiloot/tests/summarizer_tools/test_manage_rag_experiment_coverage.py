"""
Comprehensive test suite for ManageRAGExperiment tool.
Tests experiment CRUD operations, weight validation, and status management.
Target: 80%+ coverage with success paths, error paths, and edge cases.
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Mock agency_swarm before importing tool
mock_agency_swarm = MagicMock()
mock_base_tool = MagicMock()
mock_agency_swarm.tools.BaseTool = mock_base_tool
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['agency_swarm.tools'] = mock_agency_swarm.tools


class TestManageRAGExperiment(unittest.TestCase):
    """Test suite for ManageRAGExperiment tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Import tool after mocks are in place
        import importlib.util
        tool_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'summarizer_agent',
            'tools',
            'manage_rag_experiment.py'
        )
        spec = importlib.util.spec_from_file_location("manage_rag_experiment", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.ManageRAGExperiment

        # Clear experiments before each test
        self.ToolClass._experiments = {}

    def tearDown(self):
        """Clean up after each test."""
        # Clear experiments after each test
        self.ToolClass._experiments = {}

    def test_create_experiment_success(self):
        """Test successful experiment creation."""
        tool = self.ToolClass(
            operation="create",
            experiment_name="Test Experiment",
            experiment_tag="weight-tuning",
            description="Test description",
            weights_semantic=0.6,
            weights_keyword=0.4,
            weights_sql=0.0,
            top_k=20,
            status="active"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["operation"], "create")
        self.assertIn("experiment_id", data)
        self.assertTrue(data["experiment_id"].startswith("exp_"))
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["experiment"]["experiment_name"], "Test Experiment")

    def test_create_experiment_missing_name(self):
        """Test create experiment with missing name."""
        tool = self.ToolClass(
            operation="create",
            # Missing experiment_name
            weights_semantic=0.6,
            weights_keyword=0.4
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "missing_experiment_name")

    def test_create_experiment_invalid_weights_sum(self):
        """Test create experiment with weights that don't sum to 1.0."""
        tool = self.ToolClass(
            operation="create",
            experiment_name="Invalid Weights",
            weights_semantic=0.5,
            weights_keyword=0.3,
            weights_sql=0.3  # Sum = 1.1
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "invalid_weights")

    def test_create_experiment_invalid_weight_range(self):
        """Test create experiment with weight outside 0.0-1.0 range."""
        tool = self.ToolClass(
            operation="create",
            experiment_name="Out of Range",
            weights_semantic=1.5  # > 1.0
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "invalid_weights")

    def test_update_experiment_success(self):
        """Test successful experiment update."""
        # Create experiment first
        tool_create = self.ToolClass(
            operation="create",
            experiment_name="Original Name",
            weights_semantic=0.6,
            weights_keyword=0.4,
            weights_sql=0.0
        )
        result_create = tool_create.run()
        data_create = json.loads(result_create)
        experiment_id = data_create["experiment_id"]

        # Update experiment
        tool_update = self.ToolClass(
            operation="update",
            experiment_id=experiment_id,
            experiment_name="Updated Name",
            weights_semantic=0.7,
            weights_keyword=0.3,
            notes="Updated notes"
        )
        result_update = tool_update.run()
        data_update = json.loads(result_update)

        self.assertEqual(data_update["operation"], "update")
        self.assertEqual(data_update["experiment"]["experiment_name"], "Updated Name")
        self.assertEqual(data_update["experiment"]["parameters"]["weights"]["semantic"], 0.7)

    def test_update_experiment_missing_id(self):
        """Test update experiment with missing ID."""
        tool = self.ToolClass(
            operation="update",
            # Missing experiment_id
            experiment_name="Updated Name"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "missing_experiment_id")

    def test_update_experiment_not_found(self):
        """Test update experiment that doesn't exist."""
        tool = self.ToolClass(
            operation="update",
            experiment_id="nonexistent_id",
            experiment_name="Updated Name"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "experiment_not_found")

    def test_read_experiment_success(self):
        """Test successful experiment read."""
        # Create experiment first
        tool_create = self.ToolClass(
            operation="create",
            experiment_name="Test Experiment"
        )
        result_create = tool_create.run()
        data_create = json.loads(result_create)
        experiment_id = data_create["experiment_id"]

        # Read experiment
        tool_read = self.ToolClass(
            operation="read",
            experiment_id=experiment_id
        )
        result_read = tool_read.run()
        data_read = json.loads(result_read)

        self.assertEqual(data_read["operation"], "read")
        self.assertEqual(data_read["experiment_id"], experiment_id)
        self.assertEqual(data_read["experiment"]["experiment_name"], "Test Experiment")

    def test_read_experiment_not_found(self):
        """Test read experiment that doesn't exist."""
        tool = self.ToolClass(
            operation="read",
            experiment_id="nonexistent_id"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "experiment_not_found")

    def test_list_experiments_all(self):
        """Test listing all experiments."""
        # Create multiple experiments
        for i in range(3):
            tool = self.ToolClass(
                operation="create",
                experiment_name=f"Experiment {i}",
                experiment_tag="weight-tuning"
            )
            tool.run()

        # List all
        tool_list = self.ToolClass(operation="list")
        result_list = tool_list.run()
        data_list = json.loads(result_list)

        self.assertEqual(data_list["operation"], "list")
        self.assertEqual(data_list["count"], 3)
        self.assertEqual(len(data_list["experiments"]), 3)

    def test_list_experiments_by_tag(self):
        """Test listing experiments filtered by tag."""
        # Create experiments with different tags
        tool1 = self.ToolClass(
            operation="create",
            experiment_name="Experiment 1",
            experiment_tag="weight-tuning"
        )
        tool1.run()

        tool2 = self.ToolClass(
            operation="create",
            experiment_name="Experiment 2",
            experiment_tag="top-k-optimization"
        )
        tool2.run()

        # List by tag
        tool_list = self.ToolClass(
            operation="list",
            experiment_tag="weight-tuning"
        )
        result_list = tool_list.run()
        data_list = json.loads(result_list)

        self.assertEqual(data_list["count"], 1)
        self.assertEqual(data_list["experiments"][0]["experiment_name"], "Experiment 1")

    def test_list_experiments_by_status(self):
        """Test listing experiments filtered by status."""
        # Create experiments with different statuses
        tool1 = self.ToolClass(
            operation="create",
            experiment_name="Active Experiment",
            status="active"
        )
        tool1.run()

        tool2 = self.ToolClass(
            operation="create",
            experiment_name="Inactive Experiment",
            status="inactive"
        )
        tool2.run()

        # List by status
        tool_list = self.ToolClass(
            operation="list",
            status="active"
        )
        result_list = tool_list.run()
        data_list = json.loads(result_list)

        self.assertEqual(data_list["count"], 1)
        self.assertEqual(data_list["experiments"][0]["experiment_name"], "Active Experiment")

    def test_delete_experiment_success(self):
        """Test successful experiment deletion."""
        # Create experiment first
        tool_create = self.ToolClass(
            operation="create",
            experiment_name="To Delete"
        )
        result_create = tool_create.run()
        data_create = json.loads(result_create)
        experiment_id = data_create["experiment_id"]

        # Delete experiment
        tool_delete = self.ToolClass(
            operation="delete",
            experiment_id=experiment_id
        )
        result_delete = tool_delete.run()
        data_delete = json.loads(result_delete)

        self.assertEqual(data_delete["operation"], "delete")
        self.assertEqual(data_delete["deleted_experiment"]["experiment_name"], "To Delete")
        self.assertNotIn(experiment_id, self.ToolClass._experiments)

    def test_delete_experiment_not_found(self):
        """Test delete experiment that doesn't exist."""
        tool = self.ToolClass(
            operation="delete",
            experiment_id="nonexistent_id"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "experiment_not_found")

    def test_activate_experiment_success(self):
        """Test successful experiment activation."""
        # Create inactive experiment
        tool_create = self.ToolClass(
            operation="create",
            experiment_name="To Activate",
            status="inactive"
        )
        result_create = tool_create.run()
        data_create = json.loads(result_create)
        experiment_id = data_create["experiment_id"]

        # Activate experiment
        tool_activate = self.ToolClass(
            operation="activate",
            experiment_id=experiment_id
        )
        result_activate = tool_activate.run()
        data_activate = json.loads(result_activate)

        self.assertEqual(data_activate["operation"], "activate")
        self.assertEqual(data_activate["experiment"]["status"], "active")
        self.assertIsNotNone(data_activate["experiment"]["activated_at"])

    def test_deactivate_experiment_success(self):
        """Test successful experiment deactivation."""
        # Create active experiment
        tool_create = self.ToolClass(
            operation="create",
            experiment_name="To Deactivate",
            status="active"
        )
        result_create = tool_create.run()
        data_create = json.loads(result_create)
        experiment_id = data_create["experiment_id"]

        # Deactivate experiment
        tool_deactivate = self.ToolClass(
            operation="deactivate",
            experiment_id=experiment_id
        )
        result_deactivate = tool_deactivate.run()
        data_deactivate = json.loads(result_deactivate)

        self.assertEqual(data_deactivate["operation"], "deactivate")
        self.assertEqual(data_deactivate["experiment"]["status"], "inactive")
        self.assertIsNotNone(data_deactivate["experiment"]["deactivated_at"])

    def test_invalid_operation(self):
        """Test invalid operation type."""
        tool = self.ToolClass(operation="invalid_op")

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "invalid_operation")

    def test_experiment_id_generation(self):
        """Test experiment ID generation format."""
        tool = self.ToolClass(
            operation="create",
            experiment_name="Test"
        )

        result = tool.run()
        data = json.loads(result)

        experiment_id = data["experiment_id"]
        self.assertTrue(experiment_id.startswith("exp_"))
        self.assertGreater(len(experiment_id), 10)

    def test_create_experiment_with_all_parameters(self):
        """Test creating experiment with all parameters."""
        tool = self.ToolClass(
            operation="create",
            experiment_name="Full Parameters",
            experiment_tag="algorithm-comparison",
            description="Full parameter test",
            weights_semantic=0.5,
            weights_keyword=0.3,
            weights_sql=0.2,
            top_k=15,
            timeout_ms=1500,
            fusion_algorithm="weighted",
            rrf_k=50,
            enable_reranking=True,
            reranking_model="cohere-rerank-v3",
            status="active",
            notes="Test notes"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        exp = data["experiment"]
        self.assertEqual(exp["parameters"]["weights"]["semantic"], 0.5)
        self.assertEqual(exp["parameters"]["retrieval"]["top_k"], 15)
        self.assertEqual(exp["parameters"]["fusion"]["algorithm"], "weighted")
        self.assertEqual(exp["parameters"]["reranking"]["enabled"], True)

    def test_weight_validation_edge_case(self):
        """Test weight validation with floating point precision."""
        tool = self.ToolClass(
            operation="create",
            experiment_name="Floating Point",
            weights_semantic=0.333333,
            weights_keyword=0.333333,
            weights_sql=0.333334  # Sum = 1.0
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")

    def test_experiment_timestamps(self):
        """Test that timestamps are generated correctly."""
        tool = self.ToolClass(
            operation="create",
            experiment_name="Timestamp Test"
        )

        result = tool.run()
        data = json.loads(result)

        exp = data["experiment"]
        self.assertIn("created_at", exp)
        self.assertIn("updated_at", exp)
        self.assertTrue(exp["created_at"].endswith("Z"))
        self.assertTrue(exp["updated_at"].endswith("Z"))

    def test_exception_handling(self):
        """Test exception handling in run method."""
        tool = self.ToolClass(operation="create")

        # Mock _create_experiment to raise exception
        with patch.object(tool, '_create_experiment', side_effect=Exception("Test error")):
            result = tool.run()
            data = json.loads(result)

            self.assertIn("error", data)
            self.assertEqual(data["error"], "experiment_operation_failed")
            self.assertIn("Test error", data["message"])


if __name__ == '__main__':
    unittest.main()
