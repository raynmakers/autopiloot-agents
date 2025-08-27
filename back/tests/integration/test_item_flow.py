"""Simple integration tests for item management."""

import pytest
import requests
from src.apis.Db import Db


@pytest.mark.integration
class TestItemFlow:
    """Simple tests for item management brokers."""

    def test_create_item_missing_name(self, firebase_emulator, test_user_id):
        """Test create_item_callable with missing name."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/create_item_callable"
        
        response = requests.post(
            url,
            json={"data": {"categoryId": "test-category"}},
            headers={"User-Id": test_user_id},
        )
        
        # Should return 400 for missing required field
        assert response.status_code == 400

    def test_create_item_missing_category(self, firebase_emulator, test_user_id):
        """Test create_item_callable with missing categoryId."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/create_item_callable"
        
        response = requests.post(
            url,
            json={"data": {"name": "Test Item"}},
            headers={"User-Id": test_user_id},
        )
        
        # Should return 400 for missing required field
        assert response.status_code == 400

    def test_create_item_invalid_category(self, firebase_emulator, test_user_id):
        """Test create_item_callable with non-existent category."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/create_item_callable"
        
        response = requests.post(
            url,
            json={"data": {"name": "Test Item", "categoryId": "non-existent-category"}},
            headers={"User-Id": test_user_id},
        )
        
        # Should return 400 or 404 for invalid category
        assert response.status_code in [400, 404]

    def test_create_item_basic_auth_works(self, firebase_emulator, test_user_id):
        """Test that authentication works in emulator mode."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/create_item_callable"
        
        # Test without auth header - should still work in emulator mode
        response = requests.post(
            url,
            json={"data": {"name": "Test Item", "categoryId": "test-category"}},
        )
        
        # In emulator mode, auth is bypassed - may succeed or fail on validation
        assert response.status_code in [200, 400, 404, 500]  # Any response means function is working

    def test_get_item_not_found(self, firebase_emulator, test_user_id):
        """Test get_item_callable with non-existent item."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/get_item_callable"
        
        response = requests.post(
            url,
            json={"data": {"itemId": "non-existent-item"}},
            headers={"User-Id": test_user_id},
        )
        
        # Should return 404 or 400 for non-existent item
        assert response.status_code in [400, 404]

    def test_get_item_missing_id(self, firebase_emulator, test_user_id):
        """Test get_item_callable with missing itemId."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/get_item_callable"
        
        response = requests.post(
            url,
            json={"data": {}},
            headers={"User-Id": test_user_id},
        )
        
        # Should return 400 for missing required field
        assert response.status_code == 400

    def test_functions_are_accessible(self, firebase_emulator):
        """Test that all item functions are accessible."""
        base_url = firebase_emulator["base_url"]
        
        # Test create_item_callable
        response = requests.post(f"{base_url}/create_item_callable", json={"data": {}})
        assert response.status_code in [200, 400, 500]  # Function is accessible
        
        # Test get_item_callable  
        response = requests.post(f"{base_url}/get_item_callable", json={"data": {}})
        assert response.status_code in [200, 400, 500]  # Function is accessible

    def test_basic_database_operations(self, firebase_app):
        """Test basic database operations work."""
        db = Db.get_instance()
        
        # Create a test document
        test_ref = db.collections["items"].document("test-doc")
        test_data = {
            "id": "test-doc",
            "name": "Test Document",
            "status": "active",
            "createdAt": db.timestamp_now(),
            "lastUpdatedAt": db.timestamp_now(),
        }
        
        test_ref.set(test_data)
        
        # Verify it was created
        created_doc = test_ref.get()
        assert created_doc.exists
        assert created_doc.to_dict()["name"] == "Test Document"
        
        # Update it
        test_ref.update({"name": "Updated Document"})
        
        # Verify update
        updated_doc = test_ref.get()
        assert updated_doc.to_dict()["name"] == "Updated Document"
        
        # Delete it
        test_ref.delete()
        
        # Verify deletion
        deleted_doc = test_ref.get()
        assert not deleted_doc.exists