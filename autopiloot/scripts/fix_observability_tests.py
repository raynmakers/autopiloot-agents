#!/usr/bin/env python3
"""
Script to systematically fix all observability tool tests to use the proven mocking pattern.
"""

import os
import re
import glob

def fix_observability_test_file(file_path):
    """Fix a single observability test file to use the proven mocking pattern."""
    print(f"Fixing {file_path}...")

    with open(file_path, 'r') as f:
        content = f.read()

    # Extract tool name from file name
    tool_name = os.path.basename(file_path).replace('test_', '').replace('.py', '')

    # Pattern 1: Replace the import section
    old_import_pattern = re.compile(
        r'# Add.*?path.*?\n.*?sys\.path\..*?\n.*?\nfrom observability_agent\.tools\.[a-zA-Z_]+ import [a-zA-Z_]+',
        re.DOTALL
    )

    new_import_section = f"""# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from .test_utils import load_observability_tool, create_mock_firestore_client, create_sample_firestore_data

# Load the tool with proper mocking
module = load_observability_tool('{tool_name}')
# Extract the class name from the module
tool_class_name = [name for name in dir(module) if name[0].isupper() and 'Tool' not in name][0]
ToolClass = getattr(module, tool_class_name)"""

    content = old_import_pattern.sub(new_import_section, content)

    # Pattern 2: Remove @patch decorators
    content = re.sub(r'    @patch\([^)]+\)\n', '', content)

    # Pattern 3: Fix function signatures - remove mock parameters
    content = re.sub(r'def test_[^(]+\([^,]+, [^)]*mock[^)]*\):', r'def \g<0>', content)
    content = re.sub(r', mock_[a-zA-Z_]+', '', content)

    # Pattern 4: Remove mock setup lines
    content = re.sub(r'        mock_[a-zA-Z_]+\.[a-zA-Z_.]+.*?\n', '', content)
    content = re.sub(r'        # Setup mocks\n', '', content)

    # Pattern 5: Replace class instantiation with dynamic reference
    class_pattern = re.compile(r'([A-Z][a-zA-Z]+)\(', re.MULTILINE)
    content = class_pattern.sub(r'ToolClass(', content)

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"Fixed {file_path}")

def main():
    """Fix all observability tool test files."""
    # Get all test files in observability_tools directory
    test_dir = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/tests/observability_tools"
    test_files = glob.glob(os.path.join(test_dir, "test_*.py"))

    # Exclude files we already fixed or don't need to fix
    exclude_files = ['test_utils.py', 'test_alert_engine.py']
    test_files = [f for f in test_files if os.path.basename(f) not in exclude_files]

    for test_file in test_files:
        try:
            fix_observability_test_file(test_file)
        except Exception as e:
            print(f"Error fixing {test_file}: {e}")

if __name__ == "__main__":
    main()