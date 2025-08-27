import os
import sys
import subprocess
import argparse
from tests.util.firebase_emulator import start_functions_emulator
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv(".env.dev", override=True)
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run Firebase Functions tests with emulator")
    parser.add_argument("--test-type", 
                       choices=["unit", "integration", "all"], 
                       default="all",
                       help="Type of tests to run")
    parser.add_argument("--show-logs", 
                       action="store_true",
                       help="Show emulator logs")
    parser.add_argument("--no-emulator", 
                       action="store_true",
                       help="Run tests without starting emulators (assumes they're already running)")
    
    args = parser.parse_args()

    tests_cmd = [
        "python",
        "-m",
        "pytest",
    ]

    # Unit tests (currently empty but structure is there)
    unit_test_cmd = [
        *tests_cmd,
        "tests/unit",
        "-v",
    ]

    # Integration test commands for this template
    callable_example_test_cmd = [
        *tests_cmd,
        "tests/integration/test_callable_example.py",
        "-v",
    ]

    item_flow_test_cmd = [
        *tests_cmd,
        "tests/integration/test_item_flow.py",
        "-v",
    ]

    triggered_functions_test_cmd = [
        *tests_cmd,
        "tests/integration/test_triggered_functions.py",
        "-v",
    ]

    # Run all integration tests at once
    all_integration_test_cmd = [
        *tests_cmd,
        "tests/integration/",
        "-v",
    ]

    # ------------------------------------------------------------------------------------------------
    # With Firestore Emulator
    # ------------------------------------------------------------------------------------------------
    emulator_proc = None
    
    if not args.no_emulator:
        print("\n======= Starting Functions Emulator with Firestore Emulator =======\n")
        emulator_proc = start_functions_emulator(
            use_firestore_emulator=True, 
            use_storage_emulator=True, 
            show_logs=args.show_logs or True  # Show logs by default for debugging
        )

        # Environment variables are set by start_functions_emulator but verify
        assert (
            "FIRESTORE_EMULATOR_HOST" in os.environ
        ), "FIRESTORE_EMULATOR_HOST should be set"
    else:
        print("\n======= Using existing emulators (--no-emulator specified) =======\n")
    
    try:
        results = []
        
        if args.test_type in ["unit", "all"]:
            print("\n======= Running Unit Tests =======\n")
            unit_result = subprocess.run(unit_test_cmd)
            results.append(("Unit Tests", unit_result.returncode))
        
        if args.test_type in ["integration", "all"]:
            print("\n======= Running Callable Example Tests =======\n")
            callable_example_result = subprocess.run(callable_example_test_cmd)
            results.append(("Callable Example Tests", callable_example_result.returncode))

            print("\n======= Running Item Flow Tests =======\n")
            item_flow_result = subprocess.run(item_flow_test_cmd)
            results.append(("Item Flow Tests", item_flow_result.returncode))

            print("\n======= Running Triggered Functions Tests =======\n")
            triggered_functions_result = subprocess.run(triggered_functions_test_cmd)
            results.append(("Triggered Functions Tests", triggered_functions_result.returncode))

            print("\n======= Running All Integration Tests =======\n")
            all_integration_result = subprocess.run(all_integration_test_cmd)
            results.append(("All Integration Tests", all_integration_result.returncode))
    
    finally:
        if emulator_proc:
            print("\n======= Killing Functions Emulator with Firestore Emulator =======\n")
            try:
                emulator_proc.terminate()
                emulator_proc.wait(timeout=10)
                print("Functions Emulator terminated successfully")
            except subprocess.TimeoutExpired:
                print("Emulator process didn't terminate gracefully, killing forcefully...")
                emulator_proc.kill()
                emulator_proc.wait(timeout=5)
            except Exception as e:
                print(f"Error stopping emulator: {e}")
            
            # Additional cleanup
            from tests.util.firebase_emulator import stop_emulators
            stop_emulators()
            print("\n======= Functions Emulator with Firestore Emulator Killed =======\n")
        else:
            print("\n======= No emulator to clean up =======\n")

    # Display results
    print("\n======= Test Results =======")
    for name, code in results:
        print(f"{name}: {'PASSED' if code == 0 else 'FAILED'}")

    # Exit with failure if any test set failed
    if any(code != 0 for _, code in results):
        print(f"\n======= {len([c for _, c in results if c != 0])} out of {len(results)} test suites FAILED =======")
        sys.exit(1)
    else:
        print(f"\n======= All {len(results)} Test Suites Passed =======")
        sys.exit(0)
