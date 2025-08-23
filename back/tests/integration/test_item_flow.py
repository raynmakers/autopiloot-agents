"""Integration tests for item management flow."""

import pytest
import requests
from src.apis.Db import Db
from src.documents.items.Item import Item
from src.documents.categories.Category import Category
from tests.util.item_flow_setup import ItemFlowSetup


class TestItemFlow:
    """Test suite for item management flow using actual brokers."""

    def test_create_item_missing_name(self, firebase_emulator, item_flow_setup: ItemFlowSetup):
        """Test create_item_callable with missing name parameter."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/create_item_callable"
        
        headers = {
            "User-Id": item_flow_setup.user_id,
        }
        
        # Act - Missing name
        response = requests.post(
            url,
            json={"data": {"categoryId": item_flow_setup.category_id}},
            headers=headers,
        )
        
        # Assert
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        response_data = response.json()
        assert "error" in response_data, "Response should contain error field"
        assert response_data.get("result") is None, "Result should be None"

    def test_create_item_missing_category(self, firebase_emulator, item_flow_setup: ItemFlowSetup):
        """Test create_item_callable with missing categoryId parameter."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/create_item_callable"
        
        headers = {
            "User-Id": item_flow_setup.user_id,
        }
        
        # Act - Missing categoryId
        response = requests.post(
            url,
            json={"data": {"name": "Test Item"}},
            headers=headers,
        )
        
        # Assert
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        response_data = response.json()
        assert "error" in response_data, "Response should contain error field"
        assert response_data.get("result") is None, "Result should be None"

    def test_create_item_invalid_category(self, firebase_emulator, item_flow_setup: ItemFlowSetup):
        """Test create_item_callable with non-existent category."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/create_item_callable"
        
        headers = {
            "User-Id": item_flow_setup.user_id,
        }
        
        # Act - Invalid categoryId
        response = requests.post(
            url,
            json={
                "data": {
                    "name": "Test Item",
                    "categoryId": "invalid-category-id"
                }
            },
            headers=headers,
        )
        
        # Assert
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        response_data = response.json()
        assert "error" in response_data, "Response should contain error field"
        assert response_data.get("result") is None, "Result should be None"

    def test_create_item_unauthenticated(self, firebase_emulator, item_flow_setup: ItemFlowSetup):
        """Test create_item_callable with unauthenticated request."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/create_item_callable"
        
        # Act - No authentication headers
        response = requests.post(
            url,
            json={
                "data": {
                    "name": "Test Item",
                    "categoryId": item_flow_setup.category_id
                }
            },
        )
        
        # Assert
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        
        response_data = response.json()
        assert "error" in response_data, "Unauthenticated request should return error"
        assert response_data.get("result") is None, "Result should be None"

    def test_create_item_success_scenario(self, firebase_emulator, item_flow_setup: ItemFlowSetup):
        """Test successful item creation and verify Firestore document."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/create_item_callable"
        
        headers = {
            "User-Id": item_flow_setup.user_id,
        }
        
        # Act
        response = requests.post(
            url,
            json={
                "data": {
                    "name": "Test Item",
                    "description": "A test item",
                    "categoryId": item_flow_setup.category_id,
                    "tags": ["test", "integration"],
                    "metadata": {"source": "test"}
                }
            },
            headers=headers,
        )
        
        # Assert HTTP response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        response_data = response.json()
        result = response_data["result"]
        assert "error" not in result, "Response should not contain error field"
        
        item_id = result.get("itemId")
        assert item_id is not None, "Response should contain itemId"
        assert result.get("success") is True, "Response should indicate success"
        
        # Verify document was created in Firestore
        item = Item(item_id)
        assert item.doc.name == "Test Item", "Item should have correct name"
        assert item.doc.description == "A test item", "Item should have correct description"
        assert item.doc.categoryId == item_flow_setup.category_id, "Item should be in correct category"
        assert item.doc.ownerUid == item_flow_setup.user_id, "Item should be owned by correct user"
        assert item.doc.status == "active", "Item should be active"
        assert "test" in item.doc.tags, "Item should have test tag"
        assert "integration" in item.doc.tags, "Item should have integration tag"
        assert item.doc.metadata["source"] == "test", "Item should have correct metadata"
        assert item.doc.createdAt is not None, "Item should have createdAt timestamp"
        
        # Verify activity was logged
        activities = item.get_activities(limit=5)
        assert len(activities) > 0, "Item should have activity logs"
        assert activities[0].action == "created", "Most recent activity should be 'created'"
        assert activities[0].userId == item_flow_setup.user_id, "Activity should be by correct user"

    def test_get_item_not_found(self, firebase_emulator, item_flow_setup: ItemFlowSetup):
        """Test get_item_callable with non-existent item."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/get_item_callable"
        
        headers = {
            "User-Id": item_flow_setup.user_id,
        }
        
        # Act
        response = requests.post(
            url,
            json={
                "data": {
                    "itemId": "non-existent-item-id"
                }
            },
            headers=headers,
        )
        
        # Assert
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        response_data = response.json()
        assert "error" in response_data, "Response should contain error field"

    def test_get_item_success_scenario(self, firebase_emulator, item_flow_setup: ItemFlowSetup):
        """Test successful item retrieval."""
        # First create an item
        create_url = f"{firebase_emulator['base_url']}/create_item_callable"
        headers = {"User-Id": item_flow_setup.user_id}
        
        create_response = requests.post(
            create_url,
            json={
                "data": {
                    "name": "Get Test Item",
                    "description": "Item for get testing",
                    "categoryId": item_flow_setup.category_id,
                    "tags": ["get-test"]
                }
            },
            headers=headers,
        )
        
        assert create_response.status_code == 200
        item_id = create_response.json()["result"]["itemId"]
        
        # Now test getting the item
        get_url = f"{firebase_emulator['base_url']}/get_item_callable"
        
        # Act
        response = requests.post(
            get_url,
            json={
                "data": {
                    "itemId": item_id,
                    "includeActivities": True
                }
            },
            headers=headers,
        )
        
        # Assert
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        response_data = response.json()
        result = response_data["result"]
        assert result.get("success") is True, "Response should indicate success"
        
        item_data = result.get("item")
        assert item_data is not None, "Response should contain item data"
        assert item_data["name"] == "Get Test Item", "Item should have correct name"
        assert item_data["description"] == "Item for get testing", "Item should have correct description"
        assert item_data["categoryId"] == item_flow_setup.category_id, "Item should be in correct category"
        
        activities = result.get("activities")
        assert activities is not None, "Response should contain activities"
        assert len(activities) >= 1, "Should have at least created activity"

    def test_complete_item_lifecycle(self, firebase_emulator, item_flow_setup: ItemFlowSetup):
        """Test complete item lifecycle: create -> get -> verify firestore state."""
        base_url = firebase_emulator["base_url"]
        headers = {"User-Id": item_flow_setup.user_id}
        
        # Step 1: Create item
        create_response = requests.post(
            f"{base_url}/create_item_callable",
            json={
                "data": {
                    "name": "Lifecycle Test Item",
                    "description": "Testing complete lifecycle",
                    "categoryId": item_flow_setup.category_id,
                    "tags": ["lifecycle", "test"],
                    "metadata": {"test_type": "lifecycle"}
                }
            },
            headers=headers,
        )
        
        assert create_response.status_code == 200
        item_id = create_response.json()["result"]["itemId"]
        
        # Step 2: Get item via API
        get_response = requests.post(
            f"{base_url}/get_item_callable",
            json={
                "data": {
                    "itemId": item_id,
                    "includeActivities": True
                }
            },
            headers=headers,
        )
        
        assert get_response.status_code == 200
        get_result = get_response.json()["result"]
        
        # Step 3: Verify direct Firestore access matches API response
        item = Item(item_id)
        api_item = get_result["item"]
        
        assert item.doc.name == api_item["name"], "Firestore and API should match"
        assert item.doc.description == api_item["description"], "Firestore and API should match"
        assert item.doc.status == api_item["status"], "Firestore and API should match"
        assert len(item.doc.tags) == len(api_item["tags"]), "Tags count should match"
        
        # Step 4: Verify activities were logged correctly
        activities = item.get_activities()
        api_activities = get_result["activities"]
        
        assert len(activities) >= 2, "Should have created and viewed activities"
        assert activities[0].action == "viewed", "Most recent should be viewed"
        assert activities[1].action == "created", "Second most recent should be created"
        
        # Step 5: Verify item can be found in category queries
        category_items = (
            item_flow_setup.db.collections["items"]
            .where("categoryId", "==", item_flow_setup.category_id)
            .where("ownerUid", "==", item_flow_setup.user_id)
            .get()
        )
        
        item_ids = [doc.id for doc in category_items]
        assert item_id in item_ids, "Item should be findable via category query"