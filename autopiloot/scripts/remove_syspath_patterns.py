#!/usr/bin/env python3
"""
Remove sys.path manipulation patterns from Python files.

no longer needed when PYTHONPATH=. is set properly.

Usage:
    python scripts/remove_syspath_patterns.py --dry-run    # Preview changes
    python scripts/remove_syspath_patterns.py --apply      # Apply changes
    python scripts/remove_syspath_patterns.py --apply --agent-tools-only  # Only agent tools
"""

import re
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Set


def should_keep_syspath_line(line: str, file_path: Path) -> bool:
    """
    Determine if a sys.path line should be kept.

    Keep sys.path manipulation in:
    - Firebase Functions (legitimate use case)
    - Lines that are commented out
    - Very specific dynamic path scenarios
    """
    # Keep commented lines
    if line.strip().startswith('#'):
        return True

    # Keep Firebase Functions sys.path (legitimate use case)
    if 'firebase' in str(file_path).lower() or 'FUNCTION_NAME' in line:
        return True

    return False


def remove_syspath_from_file(file_path: Path, dry_run: bool = True) -> Tuple[bool, int, List[str]]:
    """
    Remove sys.path manipulation from a Python file.

    Returns:
        (modified, lines_removed, removed_lines) - Whether file was modified,
        how many lines removed, and list of removed line contents
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # Try with latin-1 encoding as fallback
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                lines = f.readlines()
        except Exception:
            # Skip files that can't be decoded
            return False, 0, []

    new_lines = []
    lines_removed = 0
    removed_lines = []
    skip_next_blank = False

    for i, line in enumerate(lines):
        # Detect sys.path manipulation patterns
            if should_keep_syspath_line(line, file_path):
                new_lines.append(line)
                continue

            # Remove this line
            lines_removed += 1
            removed_lines.append(line.strip())
            skip_next_blank = True
            continue

        # Skip blank lines immediately after removed sys.path lines
        if skip_next_blank and line.strip() == '':
            skip_next_blank = False
            continue

        skip_next_blank = False
        new_lines.append(line)

    # Write changes if not dry run and file was modified
    if lines_removed > 0:
        if not dry_run:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        return True, lines_removed, removed_lines

    return False, 0, []


def find_python_files(root: Path, agent_tools_only: bool = False) -> List[Path]:
    """Find all Python files to process."""
    exclude_patterns = {'venv', '.venv', '__pycache__', '.git', 'node_modules'}

    all_files = []
    for py_file in root.rglob("*.py"):
        # Skip excluded directories
        if any(part in exclude_patterns for part in py_file.parts):
            continue

        # If agent_tools_only, only include files in *_agent/tools/ directories
        if agent_tools_only:
            parts = py_file.parts
            is_agent_tool = any(
                i < len(parts) - 1 and parts[i].endswith('_agent') and parts[i+1] == 'tools'
                for i in range(len(parts))
            )
            if not is_agent_tool:
                continue

        all_files.append(py_file)

    return sorted(all_files)


def main():
    parser = argparse.ArgumentParser(
        description='Remove sys.path manipulation patterns from Python files'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Preview changes without modifying files (default if --apply not specified)'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply changes to files'
    )
    parser.add_argument(
        '--agent-tools-only',
        action='store_true',
        help='Only process files in *_agent/tools/ directories'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed information about removed lines'
    )

    args = parser.parse_args()

    # Default to dry-run if --apply not specified
    dry_run = not args.apply

    root = Path(__file__).parent.parent

    print(f"Scanning for Python files with sys.path patterns...")
    print(f"Root directory: {root}")
    print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'APPLY (will modify files)'}")
    print(f"Filter: {'Agent tools only' if args.agent_tools_only else 'All Python files'}")
    print("-" * 80)

    # Find all relevant Python files
    py_files = find_python_files(root, args.agent_tools_only)
    print(f"Found {len(py_files)} Python files to check\n")

    # Process files
    total_modified = 0
    total_lines_removed = 0
    modified_files = []

    for py_file in py_files:
        modified, lines_removed, removed_lines = remove_syspath_from_file(py_file, dry_run)

        if modified:
            total_modified += 1
            total_lines_removed += lines_removed
            rel_path = py_file.relative_to(root)
            modified_files.append((rel_path, lines_removed, removed_lines))

            prefix = '[DRY RUN] ' if dry_run else ''
            print(f"{prefix}Modified: {rel_path} (-{lines_removed} lines)")

            if args.verbose:
                for removed_line in removed_lines:
                    print(f"  - {removed_line}")

    # Summary
    print("\n" + "=" * 80)
    print(f"SUMMARY")
    print("=" * 80)
    print(f"Files modified: {total_modified}")
    print(f"Lines removed: {total_lines_removed}")

    if dry_run:
        print("\n⚠️  This was a DRY RUN. No files were modified.")
        print("   Use --apply to make actual changes.")
    else:
        print("\n✅ Changes applied successfully!")
        print("   Run tests to verify: export PYTHONPATH=. && python -m unittest discover tests -v")

    # File breakdown by category
    if total_modified > 0:
        print("\nFile breakdown by category:")
        agent_tools = [f for f, _, _ in modified_files if '_agent/tools/' in str(f)]
        test_files = [f for f, _, _ in modified_files if 'test' in str(f).lower()]
        other_files = [f for f, _, _ in modified_files if f not in agent_tools and f not in test_files]

        print(f"  Agent tools: {len(agent_tools)} files")
        print(f"  Test files: {len(test_files)} files")
        print(f"  Other files: {len(other_files)} files")

    return 0 if total_modified == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
