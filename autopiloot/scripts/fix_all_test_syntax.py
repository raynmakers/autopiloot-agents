#!/usr/bin/env python3
"""
Script to fix syntax errors in all test files.
Fixes misplaced @unittest.skip decorators.
"""

import os
import re
from pathlib import Path

def fix_unittest_skip_syntax(file_path):
    """Fix misplaced @unittest.skip decorators in a file."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Pattern 1: Class with skip decorator after class definition
    pattern1 = r'class (\w+)\(unittest\.TestCase\):\s*\n\s*@unittest\.skip\(["\']([^"\']+)["\']\)\s*\n\s*"""'
    replacement1 = r'@unittest.skip("\2")\nclass \1(unittest.TestCase):\n    """'

    # Pattern 2: Already has decorator but docstring in wrong place
    pattern2 = r'class (\w+)\(unittest\.TestCase\):\s*\n\s*@unittest\.skip.*?\n\s*"""([^"]*)"""'
    replacement2 = r'@unittest.skip("Test skipped due to import issues")\nclass \1(unittest.TestCase):\n    """\2"""'

    # Apply fixes
    modified = False
    if re.search(pattern1, content):
        content = re.sub(pattern1, replacement1, content)
        modified = True

    if re.search(pattern2, content):
        content = re.sub(pattern2, replacement2, content)
        modified = True

    # Fix other common patterns
    # Pattern: Skip decorator without proper indentation after class
    if '    @unittest.skip' in content and 'class ' in content:
        lines = content.split('\n')
        new_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if 'class ' in line and '(unittest.TestCase)' in line:
                # Check if next line has misplaced skip
                if i + 1 < len(lines) and '@unittest.skip' in lines[i + 1]:
                    # Get the skip line
                    skip_line = lines[i + 1].strip()
                    # Add skip before class
                    new_lines.append(skip_line)
                    new_lines.append(line)
                    i += 2  # Skip the original skip line
                    continue
            new_lines.append(line)
            i += 1
        content = '\n'.join(new_lines)
        modified = True

    if modified:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    """Main function to fix all test files."""
    project_root = Path(__file__).parent.parent
    tests_dir = project_root / "tests"

    fixed_count = 0
    error_count = 0

    # Process all Python test files
    for test_file in tests_dir.rglob("test_*.py"):
        try:
            if fix_unittest_skip_syntax(test_file):
                print(f"✅ Fixed: {test_file.name}")
                fixed_count += 1
        except Exception as e:
            print(f"❌ Error fixing {test_file.name}: {e}")
            error_count += 1

    print(f"\n📊 Summary: Fixed {fixed_count} files, {error_count} errors")

if __name__ == "__main__":
    main()