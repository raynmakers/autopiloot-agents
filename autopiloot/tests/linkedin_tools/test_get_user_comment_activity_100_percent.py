"""
100% coverage test suite for GetUserCommentActivity tool.
Tests every line of code in the implementation.
"""

import unittest
import os
import sys
import json
from unittest.mock import patch, Mock, MagicMock
from io import StringIO

# Add the linkedin_agent tools directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'linkedin_agent', 'tools'))


class TestGetUserCommentActivity100Percent(unittest.TestCase):
    """Test GetUserCommentActivity with 100% line coverage."""

    def setUp(self):
        """Set up test environment with proper mocking."""
        # Create necessary mock modules
        self.original_modules = {}
        self.mock_modules = [
            'agency_swarm',
            'agency_swarm.tools',
            'pydantic',
            'requests',
            'dotenv',
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

        # Mock requests properly
        mock_requests = MagicMock()
        mock_requests.exceptions = MagicMock()
        mock_requests.exceptions.Timeout = Exception
        mock_requests.exceptions.RequestException = Exception
        sys.modules['requests'] = mock_requests

        # Mock environment loaders
        mock_env_loader = MagicMock()
        mock_env_loader.get_required_env_var = MagicMock()
        mock_env_loader.load_environment = MagicMock()
        sys.modules['env_loader'] = mock_env_loader

        mock_loader = MagicMock()
        mock_loader.load_app_config = MagicMock()
        mock_loader.get_config_value = MagicMock()
        sys.modules['loader'] = mock_loader

    def tearDown(self):
        """Clean up mocks."""
        # Restore original modules
        for module_name in self.mock_modules:
            if module_name in self.original_modules:
                sys.modules[module_name] = self.original_modules[module_name]
            elif module_name in sys.modules:
                del sys.modules[module_name]

        # Clear the get_user_comment_activity module if it was imported
        if 'get_user_comment_activity' in sys.modules:
            del sys.modules['get_user_comment_activity']

    def test_successful_run_with_context_lines_97_168(self):
        """Test successful run method execution with post context (lines 97-168)."""
        from get_user_comment_activity import GetUserCommentActivity

        # Mock environment variables
        sys.modules['env_loader'].get_required_env_var.side_effect = lambda key, desc: {
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api.rapidapi.com",
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key-12345"
        }.get(key)

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "comment_123",
                    "text": "Great insights! Thanks for sharing this.",
                    "createdAt": "2024-01-15T10:30:00Z",
                    "likes": 15,
                    "repliesCount": 3,
                    "isEdited": False,
                    "postContext": {
                        "postId": "post_456",
                        "authorName": "John Doe",
                        "authorHeadline": "CEO at TechCorp",
                        "title": "5 Ways to Scale Your Business",
                        "url": "https://linkedin.com/posts/post_456",
                        "publishedAt": "2024-01-15T09:00:00Z"
                    }
                }
            ],
            "pagination": {
                "hasMore": True,
                "totalCount": 125
            },
            "totalCount": 125
        }

        sys.modules['requests'].get.return_value = mock_response

        tool = GetUserCommentActivity()
        tool.user_urn = "testuser"
        tool.page = 1
        tool.page_size = 50
        tool.include_post_context = True
        tool.since_iso = "2024-01-01T00:00:00Z"

        result = tool.run()
        result_data = json.loads(result)

        # Verify successful response structure
        self.assertIn("comments", result_data)
        self.assertIn("activity_metrics", result_data)
        self.assertIn("pagination", result_data)
        self.assertIn("metadata", result_data)

        # Verify since_filter is added (line 165-166)
        self.assertIn("since_filter", result_data["metadata"])
        self.assertEqual(result_data["metadata"]["since_filter"], "2024-01-01T00:00:00Z")

        print("✅ Successful run with context tested (lines 97-168)")

    def test_successful_run_without_context_lines_97_168(self):
        """Test successful run method execution without post context."""
        from get_user_comment_activity import GetUserCommentActivity

        # Mock environment variables
        sys.modules['env_loader'].get_required_env_var.side_effect = lambda key, desc: {
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api.rapidapi.com",
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key-12345"
        }.get(key)

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "comment_123",
                    "text": "Great post!",
                    "createdAt": "2024-01-15T10:30:00Z",
                    "likes": 5,
                    "repliesCount": 0,
                    "isEdited": False
                }
            ],
            "pagination": {"hasMore": False},
            "totalCount": 1
        }

        sys.modules['requests'].get.return_value = mock_response

        tool = GetUserCommentActivity()
        tool.user_urn = "testuser"
        tool.page = 1
        tool.page_size = 50
        tool.include_post_context = False
        tool.since_iso = None

        result = tool.run()
        result_data = json.loads(result)

        # Verify since_filter is NOT added when since_iso is None
        self.assertNotIn("since_filter", result_data["metadata"])

        print("✅ Successful run without context tested")

    def test_page_size_validation_lines_106_107(self):
        """Test page_size validation and capping (lines 106-107)."""
        from get_user_comment_activity import GetUserCommentActivity

        # Mock environment variables
        sys.modules['env_loader'].get_required_env_var.side_effect = lambda key, desc: {
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api.rapidapi.com",
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key-12345"
        }.get(key)

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [],
            "pagination": {"hasMore": False},
            "totalCount": 0
        }

        sys.modules['requests'].get.return_value = mock_response

        tool = GetUserCommentActivity()
        tool.user_urn = "testuser"
        tool.page = 1
        tool.page_size = 150  # Over the limit
        tool.include_post_context = True

        tool.run()

        # Verify page_size was capped at 100
        self.assertEqual(tool.page_size, 100)

        print("✅ Page size validation tested (lines 106-107)")

    def test_since_iso_parameter_inclusion_lines_125_126(self):
        """Test since_iso parameter inclusion in API params (lines 125-126)."""
        from get_user_comment_activity import GetUserCommentActivity

        # Mock environment variables
        sys.modules['env_loader'].get_required_env_var.side_effect = lambda key, desc: {
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api.rapidapi.com",
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key-12345"
        }.get(key)

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [],
            "pagination": {"hasMore": False},
            "totalCount": 0
        }

        sys.modules['requests'].get.return_value = mock_response

        tool = GetUserCommentActivity()
        tool.user_urn = "testuser"
        tool.page = 1
        tool.page_size = 50
        tool.include_post_context = True
        tool.since_iso = "2024-01-01T00:00:00Z"

        tool.run()

        # Verify API was called with since parameter
        call_args = sys.modules['requests'].get.call_args
        params = call_args[1]["params"]
        self.assertEqual(params["since"], "2024-01-01T00:00:00Z")

        print("✅ since_iso parameter inclusion tested (lines 125-126)")

    def test_failed_request_response_lines_131_136(self):
        """Test failed request handling (lines 131-136)."""
        from get_user_comment_activity import GetUserCommentActivity

        # Mock environment variables
        sys.modules['env_loader'].get_required_env_var.side_effect = lambda key, desc: {
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api.rapidapi.com",
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key-12345"
        }.get(key)

        tool = GetUserCommentActivity()
        tool.user_urn = "testuser"
        tool.page = 1
        tool.page_size = 50
        tool.include_post_context = True

        # Mock _make_request_with_retry to return None (failed request)
        tool._make_request_with_retry = MagicMock(return_value=None)

        result = tool.run()
        result_data = json.loads(result)

        # Verify error response structure
        self.assertEqual(result_data["error"], "activity_fetch_failed")
        self.assertEqual(result_data["message"], "Failed to fetch user comment activity")
        self.assertEqual(result_data["user_urn"], "testuser")

        print("✅ Failed request handling tested (lines 131-136)")

    def test_exception_handling_lines_170_176(self):
        """Test exception handling in run method (lines 170-176)."""
        from get_user_comment_activity import GetUserCommentActivity

        # Mock environment variables to raise an exception
        sys.modules['env_loader'].get_required_env_var.side_effect = Exception("Missing API key")

        tool = GetUserCommentActivity()
        tool.user_urn = "testuser"

        result = tool.run()
        result_data = json.loads(result)

        # Verify exception handling
        self.assertEqual(result_data["error"], "comment_activity_failed")
        self.assertIn("Missing API key", result_data["message"])
        self.assertEqual(result_data["user_urn"], "testuser")

        print("✅ Exception handling tested (lines 170-176)")

    def test_process_comments_with_context_lines_201_210(self):
        """Test _process_comments with post context (lines 201-210)."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()
        tool.include_post_context = True

        raw_comments = [
            {
                "id": "comment_123",
                "text": "Great post!",
                "createdAt": "2024-01-15T10:30:00Z",
                "likes": 5,
                "repliesCount": 2,
                "isEdited": True,
                "postContext": {
                    "postId": "post_456",
                    "authorName": "John Doe",
                    "authorHeadline": "CEO at TechCorp",
                    "title": "Business Tips",
                    "url": "https://linkedin.com/posts/post_456",
                    "publishedAt": "2024-01-15T09:00:00Z"
                }
            }
        ]

        processed = tool._process_comments(raw_comments)

        # Verify post context is included
        self.assertIn("post_context", processed[0])
        context = processed[0]["post_context"]
        self.assertEqual(context["post_id"], "post_456")
        self.assertEqual(context["post_author"], "John Doe")
        self.assertEqual(context["post_author_headline"], "CEO at TechCorp")
        self.assertEqual(context["post_title"], "Business Tips")
        self.assertEqual(context["post_url"], "https://linkedin.com/posts/post_456")
        self.assertEqual(context["post_date"], "2024-01-15T09:00:00Z")

        print("✅ Process comments with context tested (lines 201-210)")

    def test_process_comments_without_context_lines_188_221(self):
        """Test _process_comments without post context."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()
        tool.include_post_context = False

        raw_comments = [
            {
                "id": "comment_123",
                "text": "Great post!",
                "createdAt": "2024-01-15T10:30:00Z",
                "likes": 5,
                "repliesCount": 2,
                "isEdited": True,
                "postContext": {
                    "postId": "post_456",
                    "authorName": "John Doe"
                }
            }
        ]

        processed = tool._process_comments(raw_comments)

        # Verify post context is NOT included when include_post_context is False
        self.assertNotIn("post_context", processed[0])

        # Verify engagement metrics are included
        self.assertIn("engagement", processed[0])
        engagement = processed[0]["engagement"]
        self.assertEqual(engagement["likes"], 5)
        self.assertEqual(engagement["replies"], 2)
        self.assertEqual(engagement["total_engagement"], 7)

        print("✅ Process comments without context tested")

    def test_process_comments_missing_fields_lines_188_221(self):
        """Test _process_comments with missing fields."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()
        tool.include_post_context = True

        raw_comments = [
            {
                "id": "comment_123"
                # Missing most fields
            },
            {
                # Missing id field too
            }
        ]

        processed = tool._process_comments(raw_comments)

        # Verify default values are applied
        comment1 = processed[0]
        self.assertEqual(comment1["comment_id"], "comment_123")
        self.assertEqual(comment1["text"], "")
        self.assertEqual(comment1["likes"], 0)
        self.assertEqual(comment1["replies_count"], 0)
        self.assertEqual(comment1["is_edited"], False)

        comment2 = processed[1]
        self.assertEqual(comment2["comment_id"], "")

        print("✅ Process comments with missing fields tested")

    def test_calculate_metrics_empty_comments_lines_234_239(self):
        """Test _calculate_metrics with empty comments list (lines 234-239)."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()

        metrics = tool._calculate_metrics([], {})

        # Verify empty metrics structure
        self.assertEqual(metrics["total_comments"], 0)
        self.assertEqual(metrics["comments_this_page"], 0)
        self.assertEqual(metrics["average_likes_per_comment"], 0)

        print("✅ Calculate metrics with empty comments tested (lines 234-239)")

    def test_calculate_metrics_with_comments_lines_241_297(self):
        """Test _calculate_metrics with comments (lines 241-297)."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()
        tool.include_post_context = True

        comments = [
            {
                "comment_id": "1",
                "text": "A" * 150,  # Long text for truncation test
                "created_at": "2024-01-15T10:30:00Z",
                "likes": 10,
                "replies_count": 2,
                "post_context": {"post_author": "John Doe"}
            },
            {
                "comment_id": "2",
                "text": "Short text",
                "created_at": "2024-01-16T15:45:00Z",
                "likes": 5,
                "replies_count": 0,
                "post_context": {"post_author": "Jane Smith"}
            },
            {
                "comment_id": "3",
                "text": "Another comment",
                "created_at": "2024-01-14T08:20:00Z",
                "likes": 0,
                "replies_count": 1,
                "post_context": {"post_author": "John Doe"}
            }
        ]

        response_data = {"totalCount": 125}

        metrics = tool._calculate_metrics(comments, response_data)

        # Verify basic metrics
        self.assertEqual(metrics["total_comments"], 125)
        self.assertEqual(metrics["comments_this_page"], 3)
        self.assertEqual(metrics["average_likes_per_comment"], 5.0)  # (10+5+0)/3
        self.assertEqual(metrics["total_likes_received"], 15)
        self.assertEqual(metrics["comments_with_replies"], 2)

        # Verify most liked comment (lines 272-278)
        self.assertIn("most_liked_comment", metrics)
        most_liked = metrics["most_liked_comment"]
        self.assertEqual(most_liked["comment_id"], "1")
        self.assertEqual(most_liked["likes"], 10)
        # Test text truncation
        self.assertEqual(len(most_liked["text_preview"]), 103)  # 100 + "..."
        self.assertTrue(most_liked["text_preview"].endswith("..."))

        # Verify top engaged authors (lines 280-284)
        self.assertIn("top_engaged_authors", metrics)
        top_authors = metrics["top_engaged_authors"]
        self.assertEqual(len(top_authors), 2)
        # John Doe should have 2 comments, Jane Smith should have 1
        john_entry = next((author for author in top_authors if author["author"] == "John Doe"), None)
        self.assertIsNotNone(john_entry)
        self.assertEqual(john_entry["comment_count"], 2)

        # Verify time-based metrics (lines 287-295)
        self.assertIn("earliest_comment", metrics)
        self.assertIn("latest_comment", metrics)
        self.assertEqual(metrics["earliest_comment"], "2024-01-14T08:20:00Z")
        self.assertEqual(metrics["latest_comment"], "2024-01-16T15:45:00Z")

        print("✅ Calculate metrics with comments tested (lines 241-297)")

    def test_calculate_metrics_no_likes_most_liked_lines_272_278(self):
        """Test _calculate_metrics when most liked comment has 0 likes."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()

        comments = [
            {
                "comment_id": "1",
                "text": "Comment with no likes",
                "likes": 0,
                "replies_count": 0
            }
        ]

        metrics = tool._calculate_metrics(comments, {})

        # When most liked comment has 0 likes, it shouldn't be included
        self.assertNotIn("most_liked_comment", metrics)

        print("✅ Calculate metrics with no likes tested")

    def test_calculate_metrics_date_parsing_error_lines_294_295(self):
        """Test _calculate_metrics with date parsing errors (lines 294-295)."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()

        comments = [
            {
                "comment_id": "1",
                "text": "Comment",
                "created_at": "invalid-date-format",
                "likes": 5,
                "replies_count": 0
            }
        ]

        # Should not raise exception even with invalid dates
        metrics = tool._calculate_metrics(comments, {})

        # Verify metrics still calculated despite date error
        self.assertEqual(metrics["total_likes_received"], 5)
        # Time-based metrics should not be present due to parsing error
        self.assertNotIn("earliest_comment", metrics)

        print("✅ Calculate metrics with date parsing error tested (lines 294-295)")

    def test_calculate_metrics_without_post_context_lines_250_255(self):
        """Test _calculate_metrics when include_post_context is False."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()
        tool.include_post_context = False

        comments = [
            {
                "comment_id": "1",
                "text": "Comment",
                "likes": 5,
                "replies_count": 0,
                "post_context": {"post_author": "John Doe"}  # This should be ignored
            }
        ]

        metrics = tool._calculate_metrics(comments, {})

        # Should not have top_engaged_authors when include_post_context is False
        self.assertNotIn("top_engaged_authors", metrics)

        print("✅ Calculate metrics without post context tested")

    def test_calculate_metrics_author_name_filtering_lines_254_255(self):
        """Test author engagement tracking with empty author names."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()
        tool.include_post_context = True

        comments = [
            {
                "comment_id": "1",
                "text": "Comment",
                "likes": 5,
                "replies_count": 0,
                "post_context": {"post_author": ""}  # Empty author name
            },
            {
                "comment_id": "2",
                "text": "Comment",
                "likes": 3,
                "replies_count": 0,
                "post_context": {"post_author": "John Doe"}
            }
        ]

        metrics = tool._calculate_metrics(comments, {})

        # Only John Doe should be in top authors (empty author filtered out)
        top_authors = metrics.get("top_engaged_authors", [])
        self.assertEqual(len(top_authors), 1)
        self.assertEqual(top_authors[0]["author"], "John Doe")

        print("✅ Author name filtering tested (lines 254-255)")

    def test_make_request_success_lines_319_320(self):
        """Test _make_request_with_retry success case (lines 319-320)."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [], "totalCount": 0}

        sys.modules['requests'].get.return_value = mock_response

        result = tool._make_request_with_retry("http://test.com", {}, {})

        self.assertEqual(result, {"data": [], "totalCount": 0})

        print("✅ Make request success tested (lines 319-320)")

    def test_make_request_429_retry_lines_323_327(self):
        """Test _make_request_with_retry 429 handling (lines 323-327)."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()

        # Mock 429 response followed by success
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "2"}

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"data": []}

        sys.modules['requests'].get.side_effect = [mock_response_429, mock_response_success]

        with patch('time.sleep') as mock_sleep:
            result = tool._make_request_with_retry("http://test.com", {}, {})

        # Verify retry occurred and sleep was called with capped value
        self.assertEqual(sys.modules['requests'].get.call_count, 2)
        mock_sleep.assert_called_once_with(2)  # Retry-After value

        print("✅ Make request 429 retry tested (lines 323-327)")

    def test_make_request_429_retry_after_cap_lines_325(self):
        """Test _make_request_with_retry 429 with Retry-After cap (line 325)."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()

        # Mock 429 response with excessive retry-after
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "120"}  # Exceeds 60 second max

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"data": []}

        sys.modules['requests'].get.side_effect = [mock_response_429, mock_response_success]

        with patch('time.sleep') as mock_sleep:
            tool._make_request_with_retry("http://test.com", {}, {})

        # Verify sleep was capped at 60 seconds
        mock_sleep.assert_called_once_with(60)

        print("✅ Make request 429 retry-after cap tested (line 325)")

    def test_make_request_500_retry_lines_330_333(self):
        """Test _make_request_with_retry 500 handling (lines 330-333)."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()

        # Mock 500 response followed by success
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"data": []}

        sys.modules['requests'].get.side_effect = [mock_response_500, mock_response_success]

        with patch('time.sleep') as mock_sleep:
            result = tool._make_request_with_retry("http://test.com", {}, {})

        # Verify retry occurred
        self.assertEqual(sys.modules['requests'].get.call_count, 2)
        mock_sleep.assert_called_once()

        print("✅ Make request 500 retry tested (lines 330-333)")

    def test_make_request_client_error_lines_336_338(self):
        """Test _make_request_with_retry client error handling (lines 336-338)."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()

        # Mock 404 response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"

        sys.modules['requests'].get.return_value = mock_response

        with patch('builtins.print') as mock_print:
            result = tool._make_request_with_retry("http://test.com", {}, {})

        # Verify client error handling
        self.assertIsNone(result)
        mock_print.assert_called_once_with("Client error 404: Not found")

        print("✅ Make request client error tested (lines 336-338)")

    def test_make_request_timeout_lines_340_343(self):
        """Test _make_request_with_retry timeout handling (lines 340-343)."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()

        # Mock timeout followed by success
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"data": []}

        sys.modules['requests'].get.side_effect = [
            sys.modules['requests'].exceptions.Timeout("Request timed out"),
            mock_response_success
        ]

        with patch('time.sleep') as mock_sleep, patch('builtins.print') as mock_print:
            result = tool._make_request_with_retry("http://test.com", {}, {})

        # Verify timeout handling
        mock_print.assert_called_with("Request timeout on attempt 1")
        mock_sleep.assert_called_once()

        print("✅ Make request timeout tested (lines 340-343)")

    def test_make_request_exception_lines_344_347(self):
        """Test _make_request_with_retry general exception handling (lines 344-347)."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()

        # Mock request exception followed by success
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"data": []}

        sys.modules['requests'].get.side_effect = [
            sys.modules['requests'].exceptions.RequestException("Connection error"),
            mock_response_success
        ]

        with patch('time.sleep') as mock_sleep, patch('builtins.print') as mock_print:
            result = tool._make_request_with_retry("http://test.com", {}, {})

        # Verify exception handling
        mock_print.assert_called_with("Request failed on attempt 1: Connection error")
        mock_sleep.assert_called_once()

        print("✅ Make request exception tested (lines 344-347)")

    def test_make_request_max_retries_lines_349(self):
        """Test _make_request_with_retry max retries exhausted (line 349)."""
        from get_user_comment_activity import GetUserCommentActivity

        tool = GetUserCommentActivity()

        # Mock all retries failing
        mock_response = MagicMock()
        mock_response.status_code = 500

        sys.modules['requests'].get.return_value = mock_response

        with patch('time.sleep'):
            result = tool._make_request_with_retry("http://test.com", {}, {}, max_retries=2)

        # Verify all retries were attempted and None returned
        self.assertEqual(sys.modules['requests'].get.call_count, 2)
        self.assertIsNone(result)

        print("✅ Make request max retries tested (line 349)")

    def test_main_block_lines_352_362(self):
        """Test the main block execution (lines 352-362)."""
        # Mock environment variables
        sys.modules['env_loader'].get_required_env_var.side_effect = lambda key, desc: {
            "RAPIDAPI_LINKEDIN_HOST": "linkedin-api.rapidapi.com",
            "RAPIDAPI_LINKEDIN_KEY": "test-api-key-12345"
        }.get(key)

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [],
            "pagination": {"hasMore": False},
            "totalCount": 0
        }

        sys.modules['requests'].get.return_value = mock_response

        # Capture print output
        with patch('builtins.print') as mock_print:
            # Execute the main block by importing the module
            exec(open(os.path.join(os.path.dirname(__file__), '..', '..', 'linkedin_agent', 'tools', 'get_user_comment_activity.py')).read())

        # Verify main block was executed
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        self.assertIn("Testing GetUserCommentActivity tool...", print_calls)

        print("✅ Main block execution tested (lines 352-362)")


if __name__ == '__main__':
    unittest.main()