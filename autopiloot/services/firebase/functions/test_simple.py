#!/usr/bin/env python3
"""
Simple test script for Firebase Functions that verifies import and basic structure.
"""

import os
import sys

# Add the functions directory to the path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that functions can be imported without errors."""
    print("Testing function imports...")
    
    try:
        # Test importing main module
        import main
        print("✅ Main module imported successfully")
        
        # Test that functions are defined
        assert hasattr(main, 'schedule_scraper_daily')
        print("✅ schedule_scraper_daily function found")
        
        assert hasattr(main, 'on_transcription_written')
        print("✅ on_transcription_written function found")
        
        # Test helper functions
        assert hasattr(main, '_get_firestore_client')
        print("✅ _get_firestore_client helper found")
        
        assert hasattr(main, '_send_slack_alert')
        print("✅ _send_slack_alert helper found")
        
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def test_function_decorators():
    """Test that functions have the correct decorators."""
    print("\nTesting function decorators...")
    
    try:
        import main
        
        # Check if functions have the required attributes from decorators
        # Note: We can't easily test the actual decorators in isolation,
        # but we can verify the functions exist and are callable
        
        assert callable(main.schedule_scraper_daily)
        print("✅ schedule_scraper_daily is callable")
        
        assert callable(main.on_transcription_written)
        print("✅ on_transcription_written is callable")
        
        return True
        
    except Exception as e:
        print(f"❌ Decorator test failed: {e}")
        return False

def test_configuration():
    """Test that configuration constants are properly defined."""
    print("\nTesting configuration constants...")
    
    try:
        import main
        
        # Check constants
        assert hasattr(main, 'TIMEZONE')
        assert main.TIMEZONE == "Europe/Amsterdam"
        print("✅ TIMEZONE configured correctly")
        
        assert hasattr(main, 'BUDGET_THRESHOLD')
        assert main.BUDGET_THRESHOLD == 0.8
        print("✅ BUDGET_THRESHOLD configured correctly")
        
        assert hasattr(main, 'SLACK_CHANNEL')
        assert main.SLACK_CHANNEL == "ops-autopiloot"
        print("✅ SLACK_CHANNEL configured correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Running simple Firebase Functions tests...\n")
    
    tests = [
        test_imports,
        test_function_decorators,
        test_configuration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print(f"\n📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All basic tests passed!")
        print("\n📝 Manual deployment test required:")
        print("   1. Set up Firebase project and credentials")
        print("   2. Run: firebase deploy --only functions")
        print("   3. Test scheduled function in Cloud Console")
        print("   4. Test event function by creating transcript document")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
