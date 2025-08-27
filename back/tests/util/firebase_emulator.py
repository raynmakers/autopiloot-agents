"""Firebase emulator setup and management for tests."""

import pytest
import os
import subprocess
import time
import firebase_admin

base_host = "127.0.0.1"
base_port = 5001
firestore_emulator_port = 8080
storage_emulator_port = 9199
firebase_emulator_base_url = f"http://{base_host}:{base_port}/test-project/us-central1"


@pytest.fixture(scope="session")
def firebase_emulator():
    """Fixture to set up Firebase Emulator connection."""
    return {
        "base_url": firebase_emulator_base_url,
        "firestore_host": f"localhost:{firestore_emulator_port}",
        "storage_host": f"localhost:{storage_emulator_port}",
        "functions_host": f"localhost:{base_port}"
    }


def start_functions_emulator(use_firestore_emulator: bool = True, use_storage_emulator: bool = True, show_logs: bool = False):
    """Start Firebase emulators for testing."""
    env = os.environ.copy()
    project_dir_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../")
    )

    firebase_config_path = os.path.join(project_dir_root, "firebase.json")
    
    # Debug: Print paths
    print(f"Project root: {project_dir_root}")
    print(f"Firebase config path: {firebase_config_path}")
    print(f"Firebase config exists: {os.path.exists(firebase_config_path)}")

    # Clean up any existing Firebase app
    try:
        app = firebase_admin.get_app()
        firebase_admin.delete_app(app)
        print("Deleted existing Firebase app.")
    except ValueError:
        print("No existing Firebase app to delete.")
    except Exception as e:
        print(f"Error deleting existing Firebase app: {e}")

    # Kill processes on required ports
    _kill_process_on_port(base_port)
    _kill_process_on_port(firestore_emulator_port)
    _kill_process_on_port(storage_emulator_port)

    # Set environment variables for emulators
    emulator_services = ["functions"]
    
    if use_firestore_emulator:
        env["FIRESTORE_EMULATOR_HOST"] = f"localhost:{firestore_emulator_port}"
        os.environ["FIRESTORE_EMULATOR_HOST"] = f"localhost:{firestore_emulator_port}"
        emulator_services.append("firestore")
        
    if use_storage_emulator:
        env["FIREBASE_STORAGE_EMULATOR_HOST"] = f"localhost:{storage_emulator_port}"
        os.environ["FIREBASE_STORAGE_EMULATOR_HOST"] = f"localhost:{storage_emulator_port}"
        emulator_services.append("storage")

    # Set project environment
    env["GCLOUD_PROJECT"] = "test-project"
    os.environ["GCLOUD_PROJECT"] = "test-project"

    cmd = [
        "firebase",
        "emulators:start",
        "--only",
        ",".join(emulator_services),
        "--project",
        "test-project",
        "--config",
        firebase_config_path,
    ]

    print(f"Starting Firebase Emulators: {emulator_services}...")
    emulator_proc = subprocess.Popen(
        cmd,
        env=env,
        cwd=project_dir_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
    )

    print("Waiting for Firebase Emulators to become ready...")
    try:
        timeout = 120  # 2 minutes timeout
        start_time = time.time()
        ready_found = False
        
        while time.time() - start_time < timeout:
            # Check if process is still running
            if emulator_proc.poll() is not None:
                stdout, stderr = emulator_proc.communicate()
                print(f"Emulator process died. Exit code: {emulator_proc.returncode}")
                print(f"Output: {stdout}")
                raise RuntimeError("Firebase emulator process died unexpectedly")
            
            # Try to read output (non-blocking)
            try:
                # Use select to check if there's data to read (Unix only)
                import select
                if select.select([emulator_proc.stdout], [], [], 1):
                    line = emulator_proc.stdout.readline()
                    if line:
                        if show_logs:
                            print(line.rstrip())
                        if "All emulators ready!" in line:
                            ready_found = True
                            break
            except ImportError:
                # Fallback for non-Unix systems - just wait a bit
                time.sleep(2)
                if time.time() - start_time > 30:  # Give it at least 30 seconds
                    ready_found = True
                    break
            except Exception as e:
                print(f"Error reading emulator output: {e}")
                break
            
            time.sleep(1)
        
        if not ready_found:
            raise RuntimeError("Firebase emulators did not start in time.")
            
        print("Emulators are ready!")
        
    except Exception as e:
        print(f"Error starting emulators: {e}")
        if emulator_proc:
            emulator_proc.terminate()
            try:
                emulator_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                emulator_proc.kill()
        raise e

    time.sleep(5)  # Additional wait for stability
    print("Firebase emulators should be ready now.")
    return emulator_proc


def stop_emulators():
    """Stop all Firebase emulators."""
    try:
        subprocess.run(
            ["firebase", "emulators:exec", "--", "echo", "stopping"],
            check=False,
            timeout=10
        )
    except:
        pass
        
    _kill_process_on_port(base_port)
    _kill_process_on_port(firestore_emulator_port)
    _kill_process_on_port(storage_emulator_port)


def _kill_process_on_port(port: int):
    """Kill any process using the specified port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"], capture_output=True, text=True, check=False
        )

        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                if pid:
                    print(f"Killing process {pid} using port {port}...")
                    subprocess.run(["kill", "-9", pid], check=False)
                    time.sleep(1)

    except Exception as e:
        print(f"Warning: Could not check/kill processes on port {port}: {e}")


@pytest.fixture(scope="session")
def setup_emulators():
    """Start emulators for the test session when explicitly requested."""
    emulator_proc = None
    try:
        emulator_proc = start_functions_emulator(
            use_firestore_emulator=True,
            use_storage_emulator=True,
            show_logs=False
        )
        yield
    finally:
        if emulator_proc:
            emulator_proc.terminate()
            emulator_proc.wait(timeout=10)
        stop_emulators()


@pytest.fixture(scope="session")
def emulator_session():
    """Optional emulator session fixture - use when you need emulators running."""
    import os
    if os.getenv("SKIP_EMULATORS", "false").lower() == "true":
        print("Skipping emulator setup due to SKIP_EMULATORS=true")
        yield
        return
        
    emulator_proc = None
    try:
        print("Starting Firebase emulators for test session...")
        emulator_proc = start_functions_emulator(
            use_firestore_emulator=True,
            use_storage_emulator=True,
            show_logs=False
        )
        yield
    finally:
        if emulator_proc:
            print("Stopping Firebase emulators...")
            emulator_proc.terminate()
            emulator_proc.wait(timeout=10)
        stop_emulators()
