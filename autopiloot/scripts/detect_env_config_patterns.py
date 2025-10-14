#!/usr/bin/env python3
"""
Detection script for TASK-0075: Standardize env/config loading

Scans the codebase for:
1. Direct os.getenv usage (excluding config/env_loader.py which is the source of truth)
2. sys.path manipulation patterns
3. Generates reports with file locations and line numbers

Usage:
    python scripts/detect_env_config_patterns.py [--fix-agent-tools]

Options:
    --fix-agent-tools    Automatically fix os.getenv in agent tools (dry run by default)
    --apply-fixes        Apply fixes (use with --fix-agent-tools)
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class PatternMatch:
    """Represents a pattern match in a file."""
    file_path: str
    line_number: int
    line_content: str
    pattern_type: str


class EnvironmentPatternDetector:
    """Detects environment and config loading patterns that need standardization."""

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.matches: List[PatternMatch] = []

    def scan_codebase(self) -> Dict[str, List[PatternMatch]]:
        """
        Scan entire codebase for problematic patterns.

        Returns:
            Dict mapping pattern type to list of matches
        """
        results = {
            "os_getenv": [],
            "sys_path": [],
        }

        # Scan all Python files
        for py_file in self.root_dir.rglob("*.py"):
            # Skip certain directories
            if any(part in py_file.parts for part in ["venv", ".venv", "__pycache__", ".git"]):
                continue

            # Skip the env_loader itself (it's the source of truth)
            if "env_loader.py" in py_file.name:
                continue

            # Read file and scan for patterns
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, start=1):
                    # Check for os.getenv usage
                    if "os.getenv" in line and not line.strip().startswith("#"):
                        # Skip fallback functions we intentionally added
                        if "def get_optional_env_var" not in line:
                            match = PatternMatch(
                                file_path=str(py_file.relative_to(self.root_dir)),
                                line_number=line_num,
                                line_content=line.strip(),
                                pattern_type="os_getenv"
                            )
                            results["os_getenv"].append(match)

                    # Check for sys.path manipulation
                    if "sys.path.append" in line or "sys.path.insert" in line:
                        if not line.strip().startswith("#"):
                            match = PatternMatch(
                                file_path=str(py_file.relative_to(self.root_dir)),
                                line_number=line_num,
                                line_content=line.strip(),
                                pattern_type="sys_path"
                            )
                            results["sys_path"].append(match)

            except Exception as e:
                print(f"Warning: Failed to scan {py_file}: {e}", file=sys.stderr)

        self.matches = results["os_getenv"] + results["sys_path"]
        return results

    def generate_report(self, results: Dict[str, List[PatternMatch]]) -> str:
        """Generate a human-readable report of findings."""
        report_lines = []

        report_lines.append("=" * 80)
        report_lines.append("TASK-0075: Environment and Config Loading Pattern Detection")
        report_lines.append("=" * 80)
        report_lines.append("")

        # Report os.getenv usage
        os_getenv_matches = results["os_getenv"]
        report_lines.append(f"1. Direct os.getenv Usage: {len(os_getenv_matches)} occurrences")
        report_lines.append("-" * 80)

        if os_getenv_matches:
            # Group by directory for better organization
            by_dir = {}
            for match in os_getenv_matches:
                dir_path = str(Path(match.file_path).parent)
                if dir_path not in by_dir:
                    by_dir[dir_path] = []
                by_dir[dir_path].append(match)

            for dir_path in sorted(by_dir.keys()):
                report_lines.append(f"\n{dir_path}/")
                for match in by_dir[dir_path]:
                    file_name = Path(match.file_path).name
                    report_lines.append(f"  {file_name}:{match.line_number}")
                    report_lines.append(f"    → {match.line_content}")

        else:
            report_lines.append("  ✓ No direct os.getenv usage found!")

        report_lines.append("")
        report_lines.append("")

        # Report sys.path manipulation
        sys_path_matches = results["sys_path"]
        report_lines.append(f"2. sys.path Manipulation: {len(sys_path_matches)} occurrences")
        report_lines.append("-" * 80)

        if sys_path_matches:
            # Group by file type (tools vs tests vs other)
            tools_matches = [m for m in sys_path_matches if "/tools/" in m.file_path]
            test_matches = [m for m in sys_path_matches if "/tests/" in m.file_path or m.file_path.startswith("tests/")]
            other_matches = [m for m in sys_path_matches if m not in tools_matches and m not in test_matches]

            if tools_matches:
                report_lines.append(f"\nAgent Tools ({len(tools_matches)} files):")
                report_lines.append("  Pattern: sys.path.append for config/core imports")
                report_lines.append("  Recommendation: Use PYTHONPATH=. or package structure improvements")
                report_lines.append(f"  Example: {tools_matches[0].file_path}:{tools_matches[0].line_number}")

            if test_matches:
                report_lines.append(f"\nTest Files ({len(test_matches)} files):")
                report_lines.append("  Pattern: sys.path.insert for importing modules under test")
                report_lines.append("  Recommendation: Use pytest with proper PYTHONPATH configuration")
                report_lines.append(f"  Example: {test_matches[0].file_path}:{test_matches[0].line_number}")

            if other_matches:
                report_lines.append(f"\nOther Files ({len(other_matches)} files):")
                for match in other_matches[:5]:  # Show first 5
                    report_lines.append(f"  {match.file_path}:{match.line_number}")

        else:
            report_lines.append("  ✓ No sys.path manipulation found!")

        report_lines.append("")
        report_lines.append("")

        # Summary and recommendations
        report_lines.append("=" * 80)
        report_lines.append("SUMMARY & RECOMMENDATIONS")
        report_lines.append("=" * 80)
        report_lines.append("")

        total_os_getenv = len(os_getenv_matches)
        total_sys_path = len(sys_path_matches)

        report_lines.append(f"Total Issues: {total_os_getenv + total_sys_path}")
        report_lines.append(f"  - os.getenv usage: {total_os_getenv}")
        report_lines.append(f"  - sys.path manipulation: {total_sys_path}")
        report_lines.append("")

        if total_os_getenv > 0:
            report_lines.append("Priority 1: Fix os.getenv Usage")
            report_lines.append("  Estimated effort: 1-2 hours")
            report_lines.append("  Action: Replace with get_required_env_var() or get_optional_env_var()")
            report_lines.append("  Pattern:")
            report_lines.append("    Before: os.getenv('API_KEY')")
            report_lines.append("    After:  get_required_env_var('API_KEY', 'Description')")
            report_lines.append("")

        if total_sys_path > 0:
            report_lines.append("Priority 2: Address sys.path Manipulation")
            report_lines.append("  Estimated effort: 4-8 hours")
            report_lines.append("  Recommendation: Consider as separate task")
            report_lines.append("  Options:")
            report_lines.append("    1. Always use PYTHONPATH=. (documented in CLAUDE.md)")
            report_lines.append("    2. Improve package structure with proper __init__.py files")
            report_lines.append("    3. Use relative imports where appropriate")
            report_lines.append("")

        return "\n".join(report_lines)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Detect environment and config loading patterns")
    parser.add_argument("--fix-agent-tools", action="store_true", help="Attempt to fix agent tools automatically")
    parser.add_argument("--apply-fixes", action="store_true", help="Apply fixes (use with --fix-agent-tools)")
    args = parser.parse_args()

    # Determine root directory
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent  # autopiloot/

    print(f"Scanning codebase at: {root_dir}")
    print("")

    # Run detection
    detector = EnvironmentPatternDetector(str(root_dir))
    results = detector.scan_codebase()

    # Generate and print report
    report = detector.generate_report(results)
    print(report)

    # Save report to file
    report_file = root_dir / "planning" / "tasks" / "75-detection-report.txt"
    report_file.write_text(report)
    print(f"\nReport saved to: {report_file}")

    # Exit with status code indicating issues found
    total_issues = len(results["os_getenv"]) + len(results["sys_path"])
    if total_issues > 0:
        sys.exit(1)  # Issues found
    else:
        sys.exit(0)  # All clean


if __name__ == "__main__":
    main()
