"""
Unit tests for GetPostReactions tool.
Tests reaction metrics aggregation and cross-post analysis.
"""

import unittest
import json
from unittest.mock import patch, Mock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from linkedin_agent.tools.get_post_reactions import GetPostReactions


class TestGetPostReactions(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.tool = GetPostReactions(
            post_ids=["urn:li:activity:12345", "urn:li:activity:12346"],
            include_reaction_details=True
        )

        self.mock_response_data = {
            "data": {
                "urn:li:activity:12345": {
                    "total_reactions": 250,
                    "reaction_breakdown": {
                        "like": 180,
                        "celebrate": 35,
                        "support": 20,
                        "love": 10,
                        "insightful": 5
                    },
                    "top_reactors": [
                        {"name": "John Doe", "reaction": "like", "profile_url": "https://linkedin.com/in/johndoe"},
                        {"name": "Jane Smith", "reaction": "celebrate", "profile_url": "https://linkedin.com/in/janesmith"}
                    ]
                },
                "urn:li:activity:12346": {
                    "total_reactions": 150,
                    "reaction_breakdown": {
                        "like": 100,
                        "celebrate": 30,
                        "support": 15,
                        "love": 5
                    },
                    "top_reactors": []
                }
            },
            "summary": {
                "total_posts": 2,
                "total_reactions": 400,
                "average_reactions_per_post": 200.0
            }
        }

    @patch('linkedin_agent.tools.get_post_reactions.requests.post')
    @patch('linkedin_agent.tools.get_post_reactions.load_environment')
    @patch('linkedin_agent.tools.get_post_reactions.get_required_env_var')
    def test_successful_reactions_fetch(self, mock_env_var, mock_load_env, mock_requests):
        """Test successful reaction metrics fetching."""
        # Mock environment variables
        mock_env_var.side_effect = lambda var, desc: {
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key",
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api8.p.rapidapi.com"
        }[var]

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_response_data
        mock_requests.return_value = mock_response

        # Run the tool
        result = self.tool.run()
        result_data = json.loads(result)

        # Assertions
        self.assertEqual(result_data["status"], "success")
        self.assertEqual(result_data["summary"]["total_posts"], 2)
        self.assertEqual(result_data["summary"]["total_reactions"], 400)
        self.assertEqual(result_data["summary"]["average_reactions_per_post"], 200.0)

        # Check reaction data structure
        reactions = result_data["reactions"]
        self.assertEqual(len(reactions), 2)

        # Verify first post reactions
        post_1_reactions = next((r for r in reactions if r["post_id"] == "urn:li:activity:12345"), None)
        self.assertIsNotNone(post_1_reactions)
        self.assertEqual(post_1_reactions["total_reactions"], 250)
        self.assertEqual(post_1_reactions["reaction_breakdown"]["like"], 180)
        self.assertEqual(len(post_1_reactions["top_reactors"]), 2)

    def test_field_validation(self):
        """Test Pydantic field validation."""
        # Test required fields
        with self.assertRaises(Exception):
            GetPostReactions()  # Missing required post_ids

        # Test default values
        tool = GetPostReactions(post_ids=["urn:li:activity:12345"])
        self.assertTrue(tool.include_reaction_details)
        self.assertEqual(tool.max_reactors_per_post, 10)


if __name__ == '__main__':
    unittest.main()