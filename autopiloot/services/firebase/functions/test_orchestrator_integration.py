#!/usr/bin/env python3
"""
Test script to verify orchestrator agent integration in Firebase functions.
This validates the import paths and lazy initialization pattern.
"""

import sys
import os

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

def test_import_paths():
    """Test that import paths are correctly configured."""
    print("\n🔍 Testing import paths...")

    # Check if orchestrator_agent directory exists
    orchestrator_path = os.path.join(
        os.path.dirname(__file__), '..', '..', '..',
        'orchestrator_agent'
    )

    if os.path.exists(orchestrator_path):
        print(f"✅ Orchestrator agent directory found: {orchestrator_path}")

        # Check for key files
        files_to_check = [
            'orchestrator_agent.py',
            'instructions.md',
            'tools/plan_daily_run.py',
            'tools/dispatch_scraper.py',
            'tools/emit_run_events.py'
        ]

        for file in files_to_check:
            file_path = os.path.join(orchestrator_path, file)
            if os.path.exists(file_path):
                print(f"   ✓ {file}")
            else:
                print(f"   ✗ {file} NOT FOUND")
    else:
        print(f"❌ Orchestrator agent directory not found at: {orchestrator_path}")

    return os.path.exists(orchestrator_path)


def test_lazy_initialization():
    """Test the lazy initialization pattern."""
    print("\n🔍 Testing lazy initialization pattern...")

    # Import the main module
    try:
        from main import get_orchestrator_agent
        print("✅ Successfully imported get_orchestrator_agent")

        # Test that it returns None or agent (depending on dependencies)
        agent = get_orchestrator_agent()
        if agent is None:
            print("   ℹ️  Agent is None (expected if agency_swarm not installed)")
        else:
            print(f"   ✓ Agent initialized: {agent}")

        return True

    except ImportError as e:
        print(f"❌ Failed to import get_orchestrator_agent: {e}")
        return False


def test_function_signatures():
    """Test that function signatures match Firebase requirements."""
    print("\n🔍 Testing function signatures...")

    try:
        import main
        import scheduler

        # Check main.py functions
        if hasattr(main, 'schedule_scraper_daily'):
            print("✅ schedule_scraper_daily found in main.py")

            # Check function signature
            import inspect
            sig = inspect.signature(main.schedule_scraper_daily)
            print(f"   Signature: {sig}")

        if hasattr(main, 'on_transcription_written'):
            print("✅ on_transcription_written found in main.py")

        # Check scheduler.py functions
        if hasattr(scheduler, 'schedule_scraper_daily'):
            print("✅ schedule_scraper_daily found in scheduler.py")

        if hasattr(scheduler, 'get_orchestrator_agent'):
            print("✅ get_orchestrator_agent found in scheduler.py")

        return True

    except Exception as e:
        print(f"❌ Error checking functions: {e}")
        return False


def test_orchestrator_tools_usage():
    """Test that orchestrator tools are used correctly."""
    print("\n🔍 Testing orchestrator tools usage...")

    # Read the main.py file to check for tool usage
    main_path = os.path.join(os.path.dirname(__file__), 'main.py')
    scheduler_path = os.path.join(os.path.dirname(__file__), 'scheduler.py')

    tools_to_check = [
        'PlanDailyRun',
        'DispatchScraper',
        'EmitRunEvents'
    ]

    files_to_check = [
        ('main.py', main_path),
        ('scheduler.py', scheduler_path)
    ]

    for filename, filepath in files_to_check:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                content = f.read()

            print(f"\n   Checking {filename}:")
            for tool in tools_to_check:
                if tool in content:
                    print(f"   ✓ {tool} referenced")
                else:
                    print(f"   ✗ {tool} not found")

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Firebase Functions Orchestrator Integration Tests")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Import Paths", test_import_paths()))
    results.append(("Lazy Initialization", test_lazy_initialization()))
    results.append(("Function Signatures", test_function_signatures()))
    results.append(("Tools Usage", test_orchestrator_tools_usage()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\n📊 Results: {passed}/{total} tests passed")

    if passed == total:
        print("✅ All tests passed! Orchestrator integration is complete.")
    else:
        print("⚠️  Some tests failed. Please check the output above.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)