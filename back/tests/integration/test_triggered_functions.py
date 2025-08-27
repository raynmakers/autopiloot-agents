"""Integration tests for triggered function business logic - Direct handler calls."""

import pytest
from src.apis.Db import Db


@pytest.mark.integration
class TestTriggeredFunctionHandlers:
    """Test the business logic handlers of Firebase Functions triggers."""
    
    def test_handle_item_created_business_logic(self, firebase_app, item_flow_setup):
        """Test handle_item_created function business logic directly."""
        from src.brokers.triggered.on_item_created import handle_item_created
        
        db = Db.get_instance()
        item_id = "handler-test-item-created"
        
        # Get initial category count
        category_ref = db.collections["categories"].document(item_flow_setup.category_id)
        initial_doc = category_ref.get().to_dict()
        initial_count = initial_doc.get("itemCount", 0)
        
        # Create item data
        item_data = {
            "id": item_id,
            "name": "Handler Test Item",
            "categoryId": item_flow_setup.category_id,
            "ownerUid": item_flow_setup.user_id,
            "status": "active",
            "createdAt": db.timestamp_now(),
            "lastUpdatedAt": db.timestamp_now(),
        }
        
        # Call the handler function directly
        handle_item_created(item_id, item_data)
        
        # Verify business logic effects:
        # 1. Category counter should be incremented
        updated_doc = category_ref.get().to_dict()
        updated_count = updated_doc.get("itemCount", 0)
        assert updated_count == initial_count + 1, f"Expected count {initial_count + 1}, got {updated_count}"
        
        # 2. System activity should be logged
        activities_collection = db.collections["itemActivities"](item_id)
        activities = activities_collection.get()
        system_activities = [
            activity for activity in activities 
            if activity.to_dict().get("action") == "system_processed"
            and activity.to_dict().get("userId") == "system"
        ]
        assert len(system_activities) > 0, "Expected system_processed activity to be logged"
        
        # Verify activity details
        activity_data = system_activities[0].to_dict()
        assert activity_data["itemId"] == item_id
        assert activity_data["details"]["trigger"] == "on_item_created"
        assert activity_data["details"]["category_updated"] == item_flow_setup.category_id
        
        # Cleanup
        db.increment_counter(f"categories/{item_flow_setup.category_id}", "itemCount", -1)
        for activity in activities:
            activity.reference.delete()
    
    def test_handle_item_updated_status_change_logic(self, firebase_app, item_flow_setup):
        """Test handle_item_updated function business logic for status changes."""
        from src.brokers.triggered.on_item_updated import handle_item_updated
        
        db = Db.get_instance()
        item_id = "handler-test-item-updated-status"
        
        # Create before and after data for status change (active -> inactive)
        before_data = {
            "id": item_id,
            "name": "Status Test Item",
            "categoryId": item_flow_setup.category_id,
            "ownerUid": item_flow_setup.user_id,
            "status": "active",
            "createdAt": db.timestamp_now(),
            "lastUpdatedAt": db.timestamp_now(),
        }
        after_data = before_data.copy()
        after_data["status"] = "inactive"
        after_data["lastUpdatedAt"] = db.timestamp_now()
        
        # Call the handler function directly
        handle_item_updated(item_id, before_data, after_data)
        
        # Verify business logic effects:
        # System activity should be logged for the update
        activities_collection = db.collections["itemActivities"](item_id)
        activities = activities_collection.get()
        system_update_activities = [
            activity for activity in activities 
            if activity.to_dict().get("action") == "system_updated"
            and activity.to_dict().get("userId") == "system"
        ]
        assert len(system_update_activities) > 0, "Expected system_updated activity to be logged"
        
        # Check that the activity details indicate status change
        activity_data = system_update_activities[0].to_dict()
        assert activity_data["itemId"] == item_id
        assert activity_data["details"]["trigger"] == "on_item_updated"
        assert activity_data["details"]["status_changed"] is True
        assert activity_data["details"]["category_changed"] is False
        
        # Cleanup
        for activity in activities:
            activity.reference.delete()
    
    def test_handle_item_updated_category_change_logic(self, firebase_app, item_flow_setup):
        """Test handle_item_updated function business logic for category changes."""
        from src.brokers.triggered.on_item_updated import handle_item_updated
        
        db = Db.get_instance()
        item_id = "handler-test-item-updated-category"
        
        # Create a second category for testing
        category2_id = "handler-test-category-2"
        category2_ref = db.collections["categories"].document(category2_id)
        category2_data = {
            "id": category2_id,
            "name": "Test Category 2",
            "ownerUid": item_flow_setup.user_id,
            "itemCount": 0,
            "createdAt": db.timestamp_now(),
            "lastUpdatedAt": db.timestamp_now(),
        }
        category2_ref.set(category2_data)
        
        # Get initial counts
        category1_ref = db.collections["categories"].document(item_flow_setup.category_id)
        initial_count1 = category1_ref.get().to_dict().get("itemCount", 0)
        initial_count2 = category2_ref.get().to_dict().get("itemCount", 0)
        
        # Create before and after data for category change
        before_data = {
            "id": item_id,
            "name": "Category Test Item",
            "categoryId": item_flow_setup.category_id,
            "ownerUid": item_flow_setup.user_id,
            "status": "active",
            "createdAt": db.timestamp_now(),
            "lastUpdatedAt": db.timestamp_now(),
        }
        after_data = before_data.copy()
        after_data["categoryId"] = category2_id
        after_data["lastUpdatedAt"] = db.timestamp_now()
        
        # Call the handler function directly
        handle_item_updated(item_id, before_data, after_data)
        
        # Verify business logic effects:
        # Category 1 count should decrease, Category 2 count should increase
        updated_count1 = category1_ref.get().to_dict().get("itemCount", 0)
        updated_count2 = category2_ref.get().to_dict().get("itemCount", 0)
        
        assert updated_count1 == initial_count1 - 1, f"Expected category 1 count {initial_count1 - 1}, got {updated_count1}"
        assert updated_count2 == initial_count2 + 1, f"Expected category 2 count {initial_count2 + 1}, got {updated_count2}"
        
        # System activity should be logged for the update
        activities_collection = db.collections["itemActivities"](item_id)
        activities = activities_collection.get()
        system_update_activities = [
            activity for activity in activities 
            if activity.to_dict().get("action") == "system_updated"
            and activity.to_dict().get("userId") == "system"
        ]
        assert len(system_update_activities) > 0, "Expected system_updated activity to be logged"
        
        # Check that the activity details indicate category change
        activity_data = system_update_activities[0].to_dict()
        assert activity_data["itemId"] == item_id
        assert activity_data["details"]["trigger"] == "on_item_updated"
        assert activity_data["details"]["status_changed"] is False
        assert activity_data["details"]["category_changed"] is True
        
        # Cleanup - reset counters before deleting category
        db.increment_counter(f"categories/{item_flow_setup.category_id}", "itemCount", 1)
        db.increment_counter(f"categories/{category2_id}", "itemCount", -1)
        category2_ref.delete()
        for activity in activities:
            activity.reference.delete()
    
    def test_handle_item_deleted_business_logic(self, firebase_app, item_flow_setup):
        """Test handle_item_deleted function business logic directly."""
        from src.brokers.triggered.on_item_deleted import handle_item_deleted
        
        db = Db.get_instance()
        item_id = "handler-test-item-deleted"
        
        # Get initial category count
        category_ref = db.collections["categories"].document(item_flow_setup.category_id)
        initial_doc = category_ref.get().to_dict()
        initial_count = initial_doc.get("itemCount", 0)
        
        # Create some test activities first
        activities_collection = db.collections["itemActivities"](item_id)
        activity_refs = []
        for i in range(3):
            activity_ref = activities_collection.document()
            activity_data = {
                "id": activity_ref.id,
                "itemId": item_id,
                "action": f"test_action_{i}",
                "userId": item_flow_setup.user_id,
                "details": {"test": f"data_{i}"},
                "createdAt": db.timestamp_now(),
                "lastUpdatedAt": db.timestamp_now(),
            }
            activity_ref.set(activity_data)
            activity_refs.append(activity_ref)
        
        # Verify activities were created
        activities_before = activities_collection.get()
        assert len(activities_before) >= 3, "Expected at least 3 activities to be created"
        
        # Create item data for deletion
        item_data = {
            "id": item_id,
            "name": "Delete Test Item",
            "categoryId": item_flow_setup.category_id,
            "ownerUid": item_flow_setup.user_id,
            "status": "active",
            "createdAt": db.timestamp_now(),
            "lastUpdatedAt": db.timestamp_now(),
        }
        
        # Call the handler function directly
        handle_item_deleted(item_id, item_data)
        
        # Verify business logic effects:
        # 1. All activities should be deleted
        activities_after = activities_collection.get()
        assert len(activities_after) == 0, f"Expected 0 activities after deletion, got {len(activities_after)}"
        
        # 2. Category counter should be decremented
        updated_doc = category_ref.get().to_dict()
        updated_count = updated_doc.get("itemCount", 0)
        assert updated_count == initial_count - 1, f"Expected count {initial_count - 1}, got {updated_count}"
        
        # Reset counter for cleanup
        db.increment_counter(f"categories/{item_flow_setup.category_id}", "itemCount", 1)
    
    def test_all_handler_functions_importable(self):
        """Test that all handler functions can be imported successfully."""
        # This verifies the handler functions are properly defined and importable
        from src.brokers.triggered.on_item_created import handle_item_created
        from src.brokers.triggered.on_item_updated import handle_item_updated
        from src.brokers.triggered.on_item_deleted import handle_item_deleted
        
        # Verify functions exist and are callable
        assert callable(handle_item_created), "handle_item_created should be callable"
        assert callable(handle_item_updated), "handle_item_updated should be callable"  
        assert callable(handle_item_deleted), "handle_item_deleted should be callable"
        
        # Verify functions have proper docstrings
        assert handle_item_created.__doc__, "handle_item_created should have docstring"
        assert handle_item_updated.__doc__, "handle_item_updated should have docstring"
        assert handle_item_deleted.__doc__, "handle_item_deleted should have docstring"
    
    def test_all_trigger_functions_importable(self):
        """Test that all Firebase trigger functions can be imported successfully."""
        # This verifies the actual Firebase Functions are properly defined
        from src.brokers.triggered.on_item_created import on_item_created
        from src.brokers.triggered.on_item_updated import on_item_updated
        from src.brokers.triggered.on_item_deleted import on_item_deleted
        
        # Verify functions exist and are callable
        assert callable(on_item_created), "on_item_created should be callable"
        assert callable(on_item_updated), "on_item_updated should be callable"  
        assert callable(on_item_deleted), "on_item_deleted should be callable"
        
        # Verify functions have proper decorators/attributes
        assert hasattr(on_item_created, '__name__'), "on_item_created should have __name__"
        assert hasattr(on_item_updated, '__name__'), "on_item_updated should have __name__"
        assert hasattr(on_item_deleted, '__name__'), "on_item_deleted should have __name__"