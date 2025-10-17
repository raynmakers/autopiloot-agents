#!/usr/bin/env python3
"""
Replace duplicate _initialize_firestore() methods with centralized client.

This script automatically refactors tools to use core.firestore_client.get_firestore_client()
instead of implementing their own Firestore initialization.

Usage:
    python scripts/replace_firestore_init.py --dry-run    # Preview changes
    python scripts/replace_firestore_init.py --apply      # Apply changes
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

def replace_firestore_init_in_file(file_path: Path, dry_run: bool = True) -> Tuple[bool, str]:
    """
    Replace _initialize_firestore() method with centralized client usage.

    Returns:
        (modified, description) - Whether file was modified and what changed
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, f"Error reading: {e}"

    original_content = content
    changes = []

    # Pattern 1: Remove the entire _initialize_firestore method
    # Match from "def _initialize_firestore" to the next "def " or end of class
    init_pattern = re.compile(
        r'\n    def _initialize_firestore(?:_client)?\(self\):.*?(?=\n    def |\n\nclass |\Z)',
        re.DOTALL
    )

    if init_pattern.search(content):
        content = init_pattern.sub('', content)
        changes.append("Removed _initialize_firestore() method")

    # Pattern 2: Add import for centralized client (if not already present)
    if 'from core.firestore_client import' not in content:
        # Find where to insert the import (after other core imports or at the top)
        import_section_pattern = re.compile(r'(from config\.env_loader import[^\n]+\n)')
        match = import_section_pattern.search(content)

        if match:
            # Insert after env_loader import
            insert_pos = match.end()
            content = (
                content[:insert_pos] +
                'from core.firestore_client import get_firestore_client\n' +
                content[insert_pos:]
            )
            changes.append("Added import for get_firestore_client")
        else:
            # Fallback: insert after agency_swarm imports
            fallback_pattern = re.compile(r'(from agency_swarm\.tools import[^\n]+\n)')
            match = fallback_pattern.search(content)
            if match:
                insert_pos = match.end()
                content = (
                    content[:insert_pos] +
                    '\nfrom core.firestore_client import get_firestore_client\n' +
                    content[insert_pos:]
                )
                changes.append("Added import for get_firestore_client (after agency_swarm)")

    # Pattern 3: Replace calls to self._initialize_firestore() with direct client usage
    # Replace: self._initialize_firestore()
    # With: (nothing - will use get_firestore_client() directly)
    init_call_pattern = re.compile(r'\s*self\._initialize_firestore(?:_client)?\(\)\s*\n')
    if init_call_pattern.search(content):
        content = init_call_pattern.sub('', content)
        changes.append("Removed _initialize_firestore() calls")

    # Pattern 4: Replace self.db assignments with direct get_firestore_client() calls
    # Replace: self.db = ...
    # With: db = get_firestore_client()
    db_assignment_pattern = re.compile(r'self\.db\s*=\s*firestore\.Client\([^)]+\)')
    if db_assignment_pattern.search(content):
        content = db_assignment_pattern.sub('db = get_firestore_client()', content)
        changes.append("Replaced self.db with get_firestore_client()")

    # Pattern 5: Replace usage of self.db with db variable
    # Only do this if we're in the run() method context
    content = re.sub(r'(\s+)self\.db\.', r'\1db = get_firestore_client()\n\1db.', content, count=1)
    content = re.sub(r'self\.db\.', r'db.', content)
    if 'db = get_firestore_client()' in content:
        changes.append("Replaced self.db usage with local db variable")

    # Check if any changes were made
    if content != original_content:
        if not dry_run:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        return True, "; ".join(changes)

    return False, "No changes needed"


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Replace duplicate _initialize_firestore() with centralized client'
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

    args = parser.parse_args()

    # Default to dry-run if --apply not specified
    dry_run = not args.apply

    root = Path(__file__).parent.parent

    print(f"Scanning for tools with _initialize_firestore()...")
    print(f"Root directory: {root}")
    print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'APPLY (will modify files)'}")
    print("-" * 80)

    # Find all Python files in agent tool directories
    tools_with_init = []

    for agent_dir in root.glob("*_agent/tools"):
        for py_file in agent_dir.glob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if '_initialize_firestore' in content:
                        tools_with_init.append(py_file)
            except Exception:
                continue

    print(f"Found {len(tools_with_init)} tools with _initialize_firestore()\\n")

    # Process files
    total_modified = 0
    modified_files = []

    for py_file in tools_with_init:
        modified, description = replace_firestore_init_in_file(py_file, dry_run)

        if modified:
            total_modified += 1
            rel_path = py_file.relative_to(root)
            modified_files.append((rel_path, description))

            prefix = '[DRY RUN] ' if dry_run else ''
            print(f"{prefix}Modified: {rel_path}")
            print(f"  Changes: {description}")

    # Summary
    print("\\n" + "=" * 80)
    print(f"SUMMARY")
    print("=" * 80)
    print(f"Files modified: {total_modified}/{len(tools_with_init)}")

    if dry_run:
        print("\\n⚠️  This was a DRY RUN. No files were modified.")
        print("   Use --apply to make actual changes.")
    else:
        print("\\n✅ Changes applied successfully!")
        print("   Next steps:")
        print("   1. Review changes: git diff")
        print("   2. Run tests: export PYTHONPATH=. && python -m unittest discover tests -v")
        print("   3. Commit changes if tests pass")

    return 0 if total_modified == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
