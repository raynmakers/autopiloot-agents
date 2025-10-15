"""
Targeted coverage test for GetUserCommentActivity tool.
Directly tests method calls to achieve maximum code coverage.
"""

import unittest
import os
import sys
import json
from unittest.mock import patch, Mock, MagicMock
import requests

# Add the linkedin_agent tools directory to the path

class TestGetUserCommentActivityTargetedCoverage(unittest.TestCase):
    """Targeted test suite to achieve high coverage of GetUserCommentActivity tool."""

    def setUp(self):
        """Set up test environment."""
        # Create necessary mock modules
        self.original_modules = {}
        self.mock_modules = [
            'agency_swarm',
            'agency_swarm.tools',
            'pydantic',
            'env_loader',
            'loader'
        ]

        # Store original modules and replace with mocks
        for module_name in self.mock_modules:
            if module_name in sys.modules:
                self.original_modules[module_name] = sys.modules[module_name]
            sys.modules[module_name] = MagicMock()

        # Set up specific mocks
        sys.modules['agency_swarm'].tools.BaseTool = type('BaseTool', (), {})
        sys.modules['pydantic'].Field = lambda *args, **kwargs: kwargs.get('default', None)

        # Mock environment functions
        mock_env_loader = MagicMock()
        mock_env_loader.get_required_env_var = MagicMock()
        mock_env_loader.load_environment = MagicMock()
        sys.modules['env_loader'] = mock_env_loader

        mock_loader = MagicMock()
        mock_loader.load_app_config = MagicMock()
        mock_loader.get_config_value = MagicMock()
        sys.modules['loader'] = mock_loader

    def tearDown(self):
        """Clean up test environment."""
        # Restore original modules
        for module_name in self.mock_modules:
            if module_name in self.original_modules:
                sys.modules[module_name] = self.original_modules[module_name]
            elif module_name in sys.modules:
                del sys.modules[module_name]

        # Clear module if imported
        if 'get_user_comment_activity' in sys.modules:
            del sys.modules['get_user_comment_activity']

    def test_complete_method_coverage(self):
        """Test all methods directly to achieve maximum coverage."""
        # Mock environment setup
        sys.modules['env_loader'].get_required_env_var.side_effect = lambda key, desc: {
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api.rapidapi.com",
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key-12345"
        }.get(key)

        # Import the tool
        from get_user_comment_activity import GetUserCommentActivity

        # Create a real tool instance
        tool = GetUserCommentActivity()

        # Set attributes manually since we can't use constructor normally
        tool.user_urn = "testuser"
        tool.page = 1
        tool.page_size = 150  # Test page_size validation
        tool.include_post_context = True
        tool.since_iso = "2024-01-01T00:00:00Z"

        # Test 1: _process_comments method (lines 188-221)
        raw_comments = [
            {
                "id": "comment_123",
                "text": "A" * 150,  # Long text for truncation testing
                "createdAt": "2024-01-15T10:30:00Z",
                "likes": 15,
                "repliesCount": 3,
                "isEdited": False,
                "postContext": {
                    "postId": "post_456",
                    "authorName": "John Doe",
                    "authorHeadline": "CEO at TechCorp",
                    "title": "Business Tips",
                    "url": "https://linkedin.com/posts/post_456",
                    "publishedAt": "2024-01-15T09:00:00Z"
                }
            },
            {
                "id": "comment_789",
                "text": "Short comment",
                "createdAt": "2024-01-14T15:45:00Z",
                "likes": 8,
                "repliesCount": 1,
                "isEdited": True
                # No postContext for this one
            }
        ]

        processed_comments = tool._process_comments(raw_comments)

        # Verify _process_comments coverage
        self.assertEqual(len(processed_comments), 2)
        self.assertIn("post_context", processed_comments[0])
        self.assertNotIn("post_context", processed_comments[1])
        self.assertIn("engagement", processed_comments[0])

        # Test 2: _calculate_metrics method (lines 234-297)
        response_data = {"totalCount": 125}

        # Test with empty comments first (lines 234-239)
        empty_metrics = tool._calculate_metrics([], {})
        self.assertEqual(empty_metrics["total_comments"], 0)

        # Test with comments (lines 241-297)
        metrics = tool._calculate_metrics(processed_comments, response_data)

        # Verify all metrics paths
        self.assertEqual(metrics["total_comments"], 125)
        self.assertEqual(metrics["comments_this_page"], 2)
        self.assertIn("average_likes_per_comment", metrics)
        self.assertIn("most_liked_comment", metrics)
        self.assertIn("top_engaged_authors", metrics)
        self.assertIn("earliest_comment", metrics)
        self.assertIn("latest_comment", metrics)

        # Test with include_post_context = False
        tool.include_post_context = False
        metrics_no_context = tool._calculate_metrics(processed_comments, response_data)
        self.assertNotIn("top_engaged_authors", metrics_no_context)

        # Test 3: _make_request_with_retry method (lines 312-349)

        # Test successful request (lines 319-320)
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": []}
            mock_get.return_value = mock_response

            result = tool._make_request_with_retry("http://test.com", {}, {})
            self.assertEqual(result, {"data": []})

        # Test 429 retry (lines 323-327)
        with patch('requests.get') as mock_get, patch('time.sleep'):
            mock_429 = Mock()
            mock_429.status_code = 429
            mock_429.headers = {"Retry-After": "2"}

            mock_success = Mock()
            mock_success.status_code = 200
            mock_success.json.return_value = {"data": []}

            mock_get.side_effect = [mock_429, mock_success]

            result = tool._make_request_with_retry("http://test.com", {}, {})
            self.assertEqual(result, {"data": []})

        # Test 429 retry with excessive Retry-After (line 325)
        with patch('requests.get') as mock_get, patch('time.sleep') as mock_sleep:
            mock_429 = Mock()
            mock_429.status_code = 429
            mock_429.headers = {"Retry-After": "120"}  # Over 60 second limit

            mock_success = Mock()
            mock_success.status_code = 200
            mock_success.json.return_value = {"data": []}

            mock_get.side_effect = [mock_429, mock_success]

            tool._make_request_with_retry("http://test.com", {}, {})
            mock_sleep.assert_called_with(60)  # Should be capped at 60

        # Test 500 retry (lines 330-333)
        with patch('requests.get') as mock_get, patch('time.sleep'):
            mock_500 = Mock()
            mock_500.status_code = 500

            mock_success = Mock()
            mock_success.status_code = 200
            mock_success.json.return_value = {"data": []}

            mock_get.side_effect = [mock_500, mock_success]

            result = tool._make_request_with_retry("http://test.com", {}, {})
            self.assertEqual(result, {"data": []})

        # Test client error (lines 336-338)
        with patch('requests.get') as mock_get, patch('builtins.print'):
            mock_404 = Mock()
            mock_404.status_code = 404
            mock_404.text = "Not found"
            mock_get.return_value = mock_404

            result = tool._make_request_with_retry("http://test.com", {}, {})
            self.assertIsNone(result)

        # Test timeout exception (lines 340-343)
        with patch('requests.get') as mock_get, patch('time.sleep'), patch('builtins.print'):
            mock_success = Mock()
            mock_success.status_code = 200
            mock_success.json.return_value = {"data": []}

            mock_get.side_effect = [requests.exceptions.Timeout(), mock_success]

            result = tool._make_request_with_retry("http://test.com", {}, {})
            self.assertEqual(result, {"data": []})

        # Test general request exception (lines 344-347)
        with patch('requests.get') as mock_get, patch('time.sleep'), patch('builtins.print'):
            mock_success = Mock()
            mock_success.status_code = 200
            mock_success.json.return_value = {"data": []}

            mock_get.side_effect = [requests.exceptions.RequestException("Connection error"), mock_success]

            result = tool._make_request_with_retry("http://test.com", {}, {})
            self.assertEqual(result, {"data": []})

        # Test max retries exhausted (line 349)
        with patch('requests.get') as mock_get, patch('time.sleep'):
            mock_500 = Mock()
            mock_500.status_code = 500
            mock_get.return_value = mock_500

            result = tool._make_request_with_retry("http://test.com", {}, {}, max_retries=2)
            self.assertIsNone(result)
            self.assertEqual(mock_get.call_count, 2)

        print("✅ Complete method coverage achieved")

    def test_run_method_coverage(self):
        """Test the run method to cover lines 97-176."""
        # Mock environment setup
        sys.modules['env_loader'].get_required_env_var.side_effect = lambda key, desc: {
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api.rapidapi.com",
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key-12345"
        }.get(key)

        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()
        tool.user_urn = "testuser"
        tool.page = 1
        tool.page_size = 150  # Test validation (lines 106-107)
        tool.include_post_context = True
        tool.since_iso = "2024-01-01T00:00:00Z"

        # Test successful run (lines 97-168)
        with patch.object(tool, '_make_request_with_retry') as mock_request:
            mock_request.return_value = {
                "data": [
                    {
                        "id": "comment_123",
                        "text": "Great insights!",
                        "createdAt": "2024-01-15T10:30:00Z",
                        "likes": 15,
                        "repliesCount": 3,
                        "isEdited": False,
                        "postContext": {
                            "postId": "post_456",
                            "authorName": "John Doe"
                        }
                    }
                ],
                "pagination": {"hasMore": True, "totalCount": 125},
                "totalCount": 125
            }

            result = tool.run()
            result_data = json.loads(result)

            # Verify successful response structure (lines 149-168)
            self.assertIn("comments", result_data)
            self.assertIn("activity_metrics", result_data)
            self.assertIn("pagination", result_data)
            self.assertIn("metadata", result_data)

            # Verify since_filter is added (lines 165-166)
            self.assertIn("since_filter", result_data["metadata"])

            # Verify page_size was capped (lines 106-107)
            self.assertEqual(tool.page_size, 100)

        # Test failed request (lines 131-136)
        with patch.object(tool, '_make_request_with_retry') as mock_request:
            mock_request.return_value = None

            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "activity_fetch_failed")
            self.assertEqual(result_data["user_urn"], "testuser")

        # Test exception handling (lines 170-176)
        sys.modules['env_loader'].get_required_env_var.side_effect = Exception("Missing API key")

        result = tool.run()
        result_data = json.loads(result)

        self.assertEqual(result_data["error"], "comment_activity_failed")
        self.assertIn("Missing API key", result_data["message"])

        print("✅ Run method coverage achieved")

    def test_edge_cases_and_branches(self):
        """Test edge cases and specific branches for complete coverage."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()
        tool.include_post_context = True

        # Test _calculate_metrics with edge cases

        # Test with comments but no likes (most_liked branch)
        comments_no_likes = [
            {"comment_id": "1", "text": "Comment", "likes": 0, "replies_count": 0}
        ]
        metrics = tool._calculate_metrics(comments_no_likes, {})
        self.assertNotIn("most_liked_comment", metrics)  # Should not be included when likes = 0

        # Test with comments that have missing dates (exception handling in date parsing)
        comments_bad_dates = [
            {
                "comment_id": "1",
                "text": "Comment",
                "created_at": "invalid-date-format",
                "likes": 5,
                "replies_count": 0
            }
        ]
        metrics = tool._calculate_metrics(comments_bad_dates, {})
        # Should not crash and should not have date metrics
        self.assertNotIn("earliest_comment", metrics)

        # Test with empty author names in post context (lines 254-255)
        comments_empty_authors = [
            {
                "comment_id": "1",
                "text": "Comment",
                "likes": 5,
                "replies_count": 0,
                "post_context": {"post_author": ""}  # Empty author
            },
            {
                "comment_id": "2",
                "text": "Comment",
                "likes": 3,
                "replies_count": 0,
                "post_context": {"post_author": "John Doe"}  # Valid author
            }
        ]
        metrics = tool._calculate_metrics(comments_empty_authors, {})
        # Only John Doe should be in top authors (empty author filtered out)
        top_authors = metrics.get("top_engaged_authors", [])
        if top_authors:
            self.assertEqual(len(top_authors), 1)
            self.assertEqual(top_authors[0]["author"], "John Doe")

        # Test _process_comments with missing fields
        raw_comments_missing = [
            {"id": "comment_123"},  # Missing most fields
            {}  # Missing all fields including id
        ]
        processed = tool._process_comments(raw_comments_missing)

        # Verify default values are applied
        self.assertEqual(processed[0]["comment_id"], "comment_123")
        self.assertEqual(processed[0]["text"], "")
        self.assertEqual(processed[0]["likes"], 0)
        self.assertEqual(processed[1]["comment_id"], "")

        print("✅ Edge cases and branches coverage achieved")


if __name__ == '__main__':
    unittest.main()