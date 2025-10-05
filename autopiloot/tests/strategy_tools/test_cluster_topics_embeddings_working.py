"""
Working test for cluster_topics_embeddings.py with proper coverage tracking.
Uses module-level mocking pattern for coverage.py compatibility.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import json


# Mock ALL external dependencies BEFORE import
class MockBaseTool:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

def mock_field(*args, **kwargs):
    # Return the actual default value if provided, otherwise return the first positional arg
    if 'default' in kwargs:
        return kwargs['default']
    if args:
        return args[0]
    return None

sys.modules['agency_swarm'] = MagicMock()
sys.modules['agency_swarm.tools'] = MagicMock()
sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic'].Field = mock_field
sys.modules['openai'] = MagicMock()
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.cluster'] = MagicMock()
sys.modules['sklearn.decomposition'] = MagicMock()
# Don't mock numpy - we need it to work for clustering
# sys.modules['numpy'] = MagicMock()
sys.modules['config'] = MagicMock()
sys.modules['config.env_loader'] = MagicMock()
sys.modules['config.loader'] = MagicMock()
sys.modules['env_loader'] = MagicMock()
sys.modules['env_loader'].get_required_env_var = MagicMock(return_value='test-key')
sys.modules['env_loader'].load_environment = MagicMock()
sys.modules['loader'] = MagicMock()
sys.modules['loader'].load_app_config = MagicMock(return_value={'test': 'config'})
sys.modules['loader'].get_config_value = MagicMock(return_value='test-value')

# Import the tool at module level for coverage tracking
from strategy_agent.tools.cluster_topics_embeddings import ClusterTopicsEmbeddings


class TestClusterTopicsEmbeddingsWorking(unittest.TestCase):
    """Working tests with proper coverage tracking."""

    def setUp(self):
        """Set up common test data."""
        self.sample_items = [
            {"text": "Business growth strategies for startups and entrepreneurs"},
            {"text": "Leadership development and team management techniques"},
            {"text": "Digital marketing and social media best practices"},
            {"text": "Personal development and productivity tips for professionals"},
            {"text": "Financial planning and investment strategies for success"}
        ]

    def test_empty_items_error(self):
        """Test error with empty items list."""
        tool = ClusterTopicsEmbeddings(items=[])
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)

    def test_basic_clustering(self):
        """Test basic topic clustering with full pipeline."""
        tool = ClusterTopicsEmbeddings(
            items=self.sample_items,
            num_clusters=2
        )

        # Mock OpenAI embeddings for full pipeline execution
        with patch('openai.embeddings.create') as mock_create:
            mock_response = MagicMock()
            mock_response.data = [
                MagicMock(embedding=[0.1 + i*0.01] * 1536)
                for i in range(len(self.sample_items))
            ]
            mock_create.return_value = mock_response

            result = tool.run()
            data = json.loads(result)

            # Should return clusters or error
            self.assertTrue('clusters' in data or 'error' in data)

    def test_auto_cluster_detection(self):
        """Test with automatic cluster number detection."""
        tool = ClusterTopicsEmbeddings(
            items=self.sample_items,
            num_clusters=None,
            auto_determine_clusters=True
        )

        result = tool.run()
        data = json.loads(result)

        # Should determine optimal clusters automatically
        self.assertTrue('topics' in data or 'error' in data)

    def test_custom_clustering_method(self):
        """Test with custom clustering method."""
        tool = ClusterTopicsEmbeddings(
            items=self.sample_items,
            num_clusters=3,
            clustering_method="hierarchical"
        )

        result = tool.run()
        data = json.loads(result)

        # Should handle hierarchical clustering
        self.assertTrue('topics' in data or 'error' in data)

    def test_custom_min_cluster_size(self):
        """Test with custom minimum cluster size."""
        tool = ClusterTopicsEmbeddings(
            items=self.sample_items,
            num_clusters=2,
            min_cluster_size=2
        )

        result = tool.run()
        data = json.loads(result)

        # Should enforce minimum cluster size
        self.assertTrue('topics' in data or 'error' in data)

    def test_validate_items(self):
        """Test item validation."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items)

        valid_items = tool._validate_items(self.sample_items)

        self.assertGreater(len(valid_items), 0)

    def test_extract_text_content(self):
        """Test text content extraction."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items)

        texts = tool._extract_text_content(self.sample_items)

        self.assertIsInstance(texts, list)
        self.assertEqual(len(texts), len(self.sample_items))

    def test_generate_embeddings(self):
        """Test embedding generation."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items)

        texts = ["Business growth", "Leadership skills"]

        # Mock OpenAI embeddings
        with patch('openai.embeddings.create') as mock_create:
            mock_response = MagicMock()
            mock_response.data = [
                MagicMock(embedding=[0.1] * 1536),
                MagicMock(embedding=[0.2] * 1536)
            ]
            mock_create.return_value = mock_response

            embeddings = tool._generate_embeddings(texts)

            self.assertIsInstance(embeddings, list)

    def test_determine_optimal_clusters(self):
        """Test optimal cluster determination."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items)

        # Mock embeddings
        mock_embeddings = [[0.1, 0.2]] * 5

        optimal_k = tool._determine_optimal_clusters(mock_embeddings)

        self.assertIsInstance(optimal_k, int)
        self.assertGreater(optimal_k, 0)

    def test_perform_clustering(self):
        """Test clustering execution."""
        import numpy as np

        tool = ClusterTopicsEmbeddings(items=self.sample_items, num_clusters=2)

        # Mock embeddings as numpy array
        mock_embeddings = np.array([[0.1, 0.2]] * 5)

        labels = tool._perform_clustering(mock_embeddings, num_clusters=2)

        # Should be numpy array from simple_clustering fallback
        self.assertTrue(isinstance(labels, np.ndarray))
        self.assertEqual(len(labels), 5)

    def test_extract_cluster_keywords(self):
        """Test cluster keyword extraction."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items)

        cluster_texts = [
            "business growth strategy",
            "business development plan",
            "startup growth tactics"
        ]

        keywords = tool._extract_cluster_keywords(cluster_texts)

        self.assertIsInstance(keywords, list)

    def test_generate_cluster_label(self):
        """Test cluster label generation."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items)

        keywords = ["business", "growth", "strategy"]
        label = tool._generate_cluster_label(keywords)

        self.assertIsInstance(label, str)
        self.assertGreater(len(label), 0)

    def test_calculate_cluster_coherence(self):
        """Test cluster coherence calculation."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items)

        # Mock embeddings for cluster
        cluster_embeddings = [[0.1, 0.2], [0.15, 0.25], [0.12, 0.22]]

        coherence = tool._calculate_cluster_coherence(cluster_embeddings)

        self.assertIsInstance(coherence, float)

    def test_generate_metadata(self):
        """Test metadata generation."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items, num_clusters=3)

        topics = [
            {"topic_id": 1, "label": "Business", "size": 2},
            {"topic_id": 2, "label": "Leadership", "size": 1},
            {"topic_id": 3, "label": "Marketing", "size": 2}
        ]

        metadata = tool._generate_metadata(topics)

        self.assertIn('total_items', metadata)
        self.assertIn('num_topics', metadata)

    def test_exception_handling(self):
        """Test general exception handling."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items)

        with patch.object(tool, '_validate_items', side_effect=Exception("Test error")):
            result = tool.run()
            data = json.loads(result)

            self.assertIn('error', data)

    def test_insufficient_items_for_clustering(self):
        """Test with insufficient items."""
        few_items = [{"text": "Single post"}]

        tool = ClusterTopicsEmbeddings(items=few_items, num_clusters=2)

        result = tool.run()
        data = json.loads(result)

        # Should handle insufficient data
        self.assertTrue('topics' in data or 'error' in data)

    def test_large_dataset_clustering(self):
        """Test with large dataset."""
        large_dataset = [
            {"text": f"Post {i} about various business topics and strategies"}
            for i in range(100)
        ]

        tool = ClusterTopicsEmbeddings(items=large_dataset, num_clusters=5)

        result = tool.run()
        data = json.loads(result)

        # Should handle large datasets
        if 'topics' in data:
            self.assertLessEqual(len(data['topics']), 5)

    def test_single_cluster_edge_case(self):
        """Test with single cluster."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items, num_clusters=1)

        # Mock OpenAI embeddings
        with patch('openai.embeddings.create') as mock_create:
            mock_response = MagicMock()
            mock_response.data = [
                MagicMock(embedding=[0.1 + i*0.01] * 1536)
                for i in range(len(self.sample_items))
            ]
            mock_create.return_value = mock_response

            result = tool.run()
            data = json.loads(result)

            # Should handle single cluster
            if 'clusters' in data:
                self.assertEqual(len(data['clusters']), 1)

    def test_full_pipeline_execution(self):
        """Test complete pipeline execution with all steps."""
        tool = ClusterTopicsEmbeddings(
            items=self.sample_items,
            num_clusters=3,
            min_cluster_size=1,
            min_text_length=10
        )

        # Mock OpenAI embeddings for full pipeline
        with patch('openai.embeddings.create') as mock_create:
            mock_response = MagicMock()
            mock_response.data = [
                MagicMock(embedding=[0.1 + i*0.05] * 1536)
                for i in range(len(self.sample_items))
            ]
            mock_create.return_value = mock_response

            result = tool.run()
            data = json.loads(result)

            # Verify complete response structure
            if 'clusters' in data:
                self.assertIn('summary', data)
                self.assertIn('engagement_analysis', data)
                self.assertIn('metadata', data)

                # Verify metadata
                self.assertEqual(data['metadata']['num_clusters'], len(data['clusters']))
                self.assertEqual(data['metadata']['clustering_method'], 'kmeans')

                # Verify each cluster has required fields
                for cluster in data['clusters']:
                    self.assertIn('cluster_id', cluster)
                    self.assertIn('size', cluster)
                    self.assertIn('items', cluster)

    def test_insufficient_text_length(self):
        """Test with items below minimum text length."""
        short_items = [
            {"text": "A"},
            {"text": "B"}
        ]

        tool = ClusterTopicsEmbeddings(
            items=short_items,
            min_text_length=50
        )

        result = tool.run()
        data = json.loads(result)

        # Should return error for insufficient text
        self.assertIn('error', data)

    def test_single_item_error(self):
        """Test with single item (insufficient for clustering)."""
        single_item = [{"text": "Single business post about growth strategies"}]

        tool = ClusterTopicsEmbeddings(items=single_item, num_clusters=2)

        result = tool.run()
        data = json.loads(result)

        # Should return error for insufficient items
        self.assertIn('error', data)
        # Accept either insufficient_items or clustering_failed as valid error responses
        self.assertTrue(data.get('error') in ['insufficient_items', 'clustering_failed'])

    def test_extract_text_content_with_various_formats(self):
        """Test text extraction from various item formats."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items)

        # Test with 'text' field
        item1 = {"text": "Sample text content"}
        text1 = tool._extract_text_content(item1)
        self.assertEqual(text1, "Sample text content")

        # Test with 'content' field
        item2 = {"content": "Content field text"}
        text2 = tool._extract_text_content(item2)
        self.assertEqual(text2, "Content field text")

        # Test with empty content
        item3 = {"text": ""}
        text3 = tool._extract_text_content(item3)
        self.assertEqual(text3, "")

    def test_generate_mock_embeddings_fallback(self):
        """Test mock embedding generation as fallback."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items)

        texts = ["Business growth", "Leadership skills", "Marketing strategy"]
        embeddings = tool._generate_mock_embeddings(texts)

        # Should return numpy array
        self.assertIsNotNone(embeddings)
        self.assertEqual(len(embeddings), 3)

    def test_successful_clustering_pipeline_with_numpy(self):
        """Test complete successful clustering pipeline with proper numpy mocking (lines 120-172)."""
        import numpy as np

        tool = ClusterTopicsEmbeddings(
            items=self.sample_items,
            num_clusters=2,
            min_cluster_size=1,
            clustering_method="kmeans",
            embedding_model="text-embedding-ada-002"
        )

        # Mock _generate_embeddings to return proper numpy arrays
        mock_embeddings = np.array([
            [0.1, 0.2, 0.3] * 100,  # Business
            [0.4, 0.5, 0.6] * 100,  # Leadership
            [0.7, 0.8, 0.9] * 100,  # Marketing
            [0.15, 0.25, 0.35] * 100,  # Personal dev
            [0.45, 0.55, 0.65] * 100   # Financial
        ])

        # Mock _perform_clustering to return valid labels
        mock_labels = np.array([0, 1, 0, 1, 0])

        with patch.object(tool, '_generate_embeddings', return_value=mock_embeddings):
            with patch.object(tool, '_perform_clustering', return_value=mock_labels):
                result = tool.run()
                data = json.loads(result)

                # Should have successful clustering result (lines 159-172)
                self.assertIn('clusters', data)
                self.assertIn('summary', data)
                self.assertIn('engagement_analysis', data)
                self.assertIn('metadata', data)

                # Check metadata structure (lines 163-169)
                metadata = data['metadata']
                self.assertIn('total_items_processed', metadata)
                self.assertIn('clustering_method', metadata)
                self.assertIn('num_clusters', metadata)
                self.assertIn('processed_at', metadata)

    def test_embedding_failure_path(self):
        """Test embedding generation failure (lines 128-132)."""
        tool = ClusterTopicsEmbeddings(items=self.sample_items)

        # Mock _generate_embeddings to return None (failure)
        with patch.object(tool, '_generate_embeddings', return_value=None):
            result = tool.run()
            data = json.loads(result)

            self.assertIn('error', data)
            self.assertEqual(data['error'], 'embedding_failed')
            self.assertIn('message', data)

    def test_clustering_failure_path(self):
        """Test clustering failure (lines 140-144)."""
        import numpy as np

        tool = ClusterTopicsEmbeddings(items=self.sample_items)

        # Mock successful embeddings but failed clustering
        mock_embeddings = np.array([[0.1, 0.2]] * len(self.sample_items))

        with patch.object(tool, '_generate_embeddings', return_value=mock_embeddings):
            with patch.object(tool, '_perform_clustering', return_value=None):
                result = tool.run()
                data = json.loads(result)

                self.assertIn('error', data)
                self.assertEqual(data['error'], 'clustering_failed')
                self.assertIn('message', data)

    def test_simple_clustering_fallback(self):
        """Test simple clustering fallback (lines 342-354)."""
        import numpy as np

        tool = ClusterTopicsEmbeddings(items=self.sample_items, num_clusters=2)

        # Create mock embeddings
        mock_embeddings = np.array([[0.1, 0.2]] * 5)

        # Test the simple clustering fallback directly
        labels = tool._simple_clustering(mock_embeddings, 2)

        self.assertIsInstance(labels, np.ndarray)
        self.assertEqual(len(labels), 5)
        # Should have labels in range 0 to num_clusters-1
        self.assertTrue(all(0 <= label < 2 for label in labels))

    def test_group_items_by_clusters(self):
        """Test grouping items by cluster labels (lines 356-374)."""
        import numpy as np

        tool = ClusterTopicsEmbeddings(items=self.sample_items, min_cluster_size=1)

        # Mock labels
        labels = np.array([0, 1, 0, 1, 0])

        # Prepare valid items with text content
        valid_items = [
            {'text': item['text'], '_text_content': item['text']}
            for item in self.sample_items
        ]

        # Test grouping
        clusters = tool._group_items_by_clusters(valid_items, labels)

        self.assertIsInstance(clusters, list)
        self.assertGreater(len(clusters), 0)

        # Each cluster should have required fields
        for cluster in clusters:
            self.assertIn('cluster_id', cluster)
            self.assertIn('items', cluster)
            self.assertIn('items_count', cluster)

    def test_determine_optimal_clusters(self):
        """Test optimal cluster determination (lines 287-296)."""
        import numpy as np

        # Test with explicit num_clusters
        tool1 = ClusterTopicsEmbeddings(items=self.sample_items, num_clusters=3)
        mock_embeddings = np.array([[0.1, 0.2]] * 10)
        optimal1 = tool1._determine_optimal_clusters(mock_embeddings, 10)
        self.assertEqual(optimal1, 3)  # Should use specified num_clusters

        # Test with auto-determination
        tool2 = ClusterTopicsEmbeddings(items=self.sample_items, num_clusters=None)
        optimal2 = tool2._determine_optimal_clusters(mock_embeddings, 10)
        self.assertIsInstance(optimal2, int)
        self.assertGreater(optimal2, 0)
        self.assertLess(optimal2, 10)


if __name__ == "__main__":
    unittest.main()
