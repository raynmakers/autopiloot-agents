#!/usr/bin/env python3
"""
Batch refactor to replace _initialize_firestore() with centralized client.

Simple, focused script that:
1. Adds import for get_firestore_client
2. Replaces db = self._initialize_firestore() with db = get_firestore_client()
3. Removes the _initialize_firestore method entirely
"""

import re
from pathlib import Path

# Files to update
FILES = [
    "linkedin_agent/tools/get_user_comment_activity.py",
    "linkedin_agent/tools/get_post_reactions.py",
    "linkedin_agent/tools/get_post_comments.py",
    "linkedin_agent/tools/get_user_posts.py",
    "scraper_agent/tools/mark_sheet_rows_processed.py",
    "scraper_agent/tools/enqueue_transcription.py",
    "scraper_agent/tools/save_channel_mapping.py",
    "observability_agent/tools/llm_observability_metrics.py",
    "observability_agent/tools/monitor_quota_state.py",
    "observability_agent/tools/monitor_dlq_trends.py",
    "observability_agent/tools/stuck_job_scanner.py",
    "observability_agent/tools/alert_engine.py",
    "observability_agent/tools/report_daily_summary.py",
    "orchestrator_agent/tools/dispatch_summarizer.py",
    "orchestrator_agent/tools/handle_dlq.py",
    "orchestrator_agent/tools/orchestrate_rag_ingestion.py",
    "orchestrator_agent/tools/dispatch_transcriber.py",
    "orchestrator_agent/tools/dispatch_scraper.py",
    "orchestrator_agent/tools/query_dlq.py",
    "strategy_agent/tools/save_strategy_artifacts.py",
    "transcriber_agent/tools/save_transcript_record.py",
    "transcriber_agent/tools/submit_assemblyai_job.py",
]

root = Path(__file__).parent.parent

for file_path in FILES:
    full_path = root / file_path

    if not full_path.exists():
        print(f"⚠️  File not found: {file_path}")
        continue

    print(f"Processing: {file_path}")

    with open(full_path, 'r') as f:
        content = f.read()

    original_content = content

    # Step 1: Add import if not present
    if 'from firestore_client import get_firestore_client' not in content:
        # Find the audit_logger or env_loader import line and add after it
        pattern = r'(from (?:audit_logger|env_loader|loader) import [^\n]+\n)'
        match = re.search(pattern, content)
        if match:
            insert_pos = match.end()
            content = content[:insert_pos] + 'from firestore_client import get_firestore_client\n' + content[insert_pos:]
            print(f"  ✅ Added import")

    # Step 2: Replace the call
    content = re.sub(
        r'db = self\._initialize_firestore(_client)?\(\)',
        'db = get_firestore_client()',
        content
    )
    if 'db = get_firestore_client()' in content and 'self._initialize_firestore' not in content:
        print(f"  ✅ Replaced initialization call")

    # Step 3: Remove the method entirely
    # Match the method from def to the next def or class or end
    method_pattern = r'\n    def _initialize_firestore(_client)?\(self\):.*?(?=\n    def |\n\nclass |\n\nif __name__|\Z)'
    content = re.sub(method_pattern, '', content, flags=re.DOTALL)

    if '_initialize_firestore' not in content:
        print(f"  ✅ Removed _initialize_firestore method")

    # Write back only if changes were made
    if content != original_content:
        with open(full_path, 'w') as f:
            f.write(content)
        print(f"  ✅ File updated\n")
    else:
        print(f"  ⚠️  No changes made\n")

print("\n✅ Batch refactoring complete!")
print("Next: Run tests to verify no regressions")
