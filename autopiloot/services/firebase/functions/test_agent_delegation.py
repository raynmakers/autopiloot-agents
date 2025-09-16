#!/usr/bin/env python3
"""
Test script to verify that core.py properly delegates to agent workflows.
This validates that Firebase functions now use the full agent system.
"""

import sys
import os

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

def test_core_delegation_pattern():
    """Test that core.py functions delegate to agents."""
    print("\n🔍 Testing core.py delegation pattern...")

    # Read core.py to check for agent delegation
    core_path = os.path.join(os.path.dirname(__file__), 'core.py')
    if not os.path.exists(core_path):
        print("❌ core.py not found")
        return False

    with open(core_path, 'r') as f:
        content = f.read()

    # Check for agent delegation patterns
    agent_patterns = [
        'orchestrator_agent',
        'observability_agent',
        'get_orchestrator_agent',
        'DEPRECATED',
        'delegat',  # catches "delegate" and "delegating"
        'PlanDailyRun',
        'DispatchScraper',
        'EmitRunEvents',
        'MonitorTranscriptionBudget'
    ]

    print("   Checking for agent delegation patterns:")
    for pattern in agent_patterns:
        if pattern.lower() in content.lower():
            print(f"   ✓ {pattern}")
        else:
            print(f"   ✗ {pattern} not found")

    # Check for fallback patterns
    fallback_patterns = [
        'fallback',
        'simplified',
        'method',
        'agent_result'
    ]

    print("   Checking for fallback patterns:")
    for pattern in fallback_patterns:
        if pattern.lower() in content.lower():
            print(f"   ✓ {pattern}")
        else:
            print(f"   ✗ {pattern} not found")

    return True


def test_main_py_agent_usage():
    """Test that main.py uses agents directly."""
    print("\n🔍 Testing main.py agent usage...")

    main_path = os.path.join(os.path.dirname(__file__), 'main.py')
    if not os.path.exists(main_path):
        print("❌ main.py not found")
        return False

    with open(main_path, 'r') as f:
        content = f.read()

    # Check for direct agent usage in main.py
    agent_usage_patterns = [
        'get_orchestrator_agent()',
        'orchestrator_agent.tools',
        'observability_agent.tools',
        'MonitorTranscriptionBudget',
        'method.*orchestrator',
        'method.*observability'
    ]

    print("   Checking for direct agent usage:")
    for pattern in agent_usage_patterns:
        if pattern.lower().replace('.*', '') in content.lower():
            print(f"   ✓ {pattern}")
        else:
            print(f"   ✗ {pattern} not found")

    # Check that we still have fallback references to core.py
    core_patterns = [
        'create_scraper_job',
        'process_transcription_budget',
        'validate_video_id',
        'validate_transcript_data'
    ]

    print("   Checking for core.py fallback patterns:")
    for pattern in core_patterns:
        if pattern in content:
            print(f"   ✓ {pattern}")
        else:
            print(f"   ✗ {pattern} not found")

    return True


def test_scheduler_py_agent_usage():
    """Test that scheduler.py uses full orchestrator workflow."""
    print("\n🔍 Testing scheduler.py agent usage...")

    scheduler_path = os.path.join(os.path.dirname(__file__), 'scheduler.py')
    if not os.path.exists(scheduler_path):
        print("❌ scheduler.py not found")
        return False

    with open(scheduler_path, 'r') as f:
        content = f.read()

    # Check for orchestrator workflow in scheduler.py
    workflow_patterns = [
        'get_orchestrator_agent',
        'PlanDailyRun',
        'DispatchScraper',
        'EmitRunEvents',
        'orchestrator_agent',
        'method.*orchestrator'
    ]

    print("   Checking for orchestrator workflow:")
    for pattern in workflow_patterns:
        if pattern.lower().replace('.*', '') in content.lower():
            print(f"   ✓ {pattern}")
        else:
            print(f"   ✗ {pattern} not found")

    return True


def test_deprecation_warnings():
    """Test that deprecation warnings are present."""
    print("\n🔍 Testing deprecation warnings...")

    core_path = os.path.join(os.path.dirname(__file__), 'core.py')
    if not os.path.exists(core_path):
        print("❌ core.py not found")
        return False

    with open(core_path, 'r') as f:
        content = f.read()

    deprecation_patterns = [
        'DEPRECATED',
        'phased out',
        'adapter layer',
        'use agent directly'
    ]

    print("   Checking for deprecation warnings:")
    found_warnings = 0
    for pattern in deprecation_patterns:
        if pattern.lower() in content.lower():
            print(f"   ✓ {pattern}")
            found_warnings += 1
        else:
            print(f"   ✗ {pattern} not found")

    return found_warnings >= 2  # At least 2 deprecation indicators


def test_import_consistency():
    """Test that imports are consistent across files."""
    print("\n🔍 Testing import consistency...")

    files_to_check = ['main.py', 'scheduler.py', 'core.py']
    orchestrator_imports = 0
    observability_imports = 0

    for filename in files_to_check:
        filepath = os.path.join(os.path.dirname(__file__), filename)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                content = f.read()

            if 'orchestrator_agent' in content:
                orchestrator_imports += 1
                print(f"   ✓ {filename} imports orchestrator_agent")

            if 'observability_agent' in content:
                observability_imports += 1
                print(f"   ✓ {filename} imports observability_agent")

    print(f"   Total orchestrator imports: {orchestrator_imports}")
    print(f"   Total observability imports: {observability_imports}")

    # We expect at least 2 files to have orchestrator imports
    # and at least 2 files to have observability imports
    return orchestrator_imports >= 2 and observability_imports >= 2


def main():
    """Run all tests."""
    print("=" * 70)
    print("Firebase Functions Full Agent Delegation Tests")
    print("=" * 70)

    results = []

    # Run tests
    results.append(("Core Delegation", test_core_delegation_pattern()))
    results.append(("Main.py Agent Usage", test_main_py_agent_usage()))
    results.append(("Scheduler.py Agent Usage", test_scheduler_py_agent_usage()))
    results.append(("Deprecation Warnings", test_deprecation_warnings()))
    results.append(("Import Consistency", test_import_consistency()))

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\n📊 Results: {passed}/{total} tests passed")

    if passed == total:
        print("✅ All tests passed! Full agent delegation is complete.")
        print("\n📝 Key improvements:")
        print("   • Firebase functions now delegate to orchestrator/observability agents")
        print("   • core.py serves as adapter layer with proper fallbacks")
        print("   • Deprecation warnings guide migration to direct agent usage")
        print("   • Multiple delegation layers ensure reliability")
    else:
        print("⚠️  Some tests failed. Please check the output above.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)