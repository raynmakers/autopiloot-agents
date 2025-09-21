#!/usr/bin/env python3
"""
Script to fix datetime.utcnow() deprecation warnings across the codebase.
Replaces datetime.utcnow() with datetime.now(timezone.utc) and adds timezone import.
"""

import os
import re

def fix_datetime_in_file(filepath):
    """Fix datetime.utcnow() deprecation in a single file."""

    with open(filepath, 'r') as f:
        content = f.read()

    original_content = content

    # Check if file contains datetime.utcnow()
    if 'datetime.utcnow()' not in content:
        return False

    print(f"Fixing {filepath}...")

    # Add timezone import if it's not already there
    if 'from datetime import' in content and 'timezone' not in content:
        # Find the datetime import line and add timezone
        import_pattern = r'from datetime import ([^,\n]+(?:, [^,\n]+)*)'
        match = re.search(import_pattern, content)
        if match:
            current_imports = match.group(1)
            if 'timezone' not in current_imports:
                new_imports = current_imports + ', timezone'
                content = content.replace(match.group(0), f'from datetime import {new_imports}')
        else:
            # Check for plain datetime import
            if 'import datetime' in content and 'from datetime import' not in content:
                # This case doesn't need timezone import as we'll use datetime.timezone.utc
                pass

    # Replace datetime.utcnow() patterns

    # Pattern 1: datetime.utcnow().isoformat() + "Z"
    content = re.sub(
        r'datetime\.utcnow\(\)\.isoformat\(\) \+ "Z"',
        'datetime.now(timezone.utc).isoformat()',
        content
    )

    # Pattern 2: datetime.utcnow().isoformat()
    content = re.sub(
        r'datetime\.utcnow\(\)\.isoformat\(\)',
        'datetime.now(timezone.utc).isoformat()',
        content
    )

    # Pattern 3: datetime.utcnow()
    content = re.sub(
        r'datetime\.utcnow\(\)',
        'datetime.now(timezone.utc)',
        content
    )

    # Write back the fixed content
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  Fixed datetime deprecations in {filepath}")
        return True
    else:
        print(f"  No changes needed in {filepath}")
        return False

def main():
    """Main function to fix datetime deprecations."""

    # Files to fix
    files_to_fix = [
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/linkedin_agent/tools/save_ingestion_record.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/linkedin_agent/tools/upsert_to_zep_group.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/linkedin_agent/tools/deduplicate_entities.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/linkedin_agent/tools/normalize_linkedin_content.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/linkedin_agent/tools/get_user_comment_activity.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/linkedin_agent/tools/get_post_reactions.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/linkedin_agent/tools/get_post_comments.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/linkedin_agent/tools/get_user_posts.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/transcriber_agent/tools/store_transcript_to_drive.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/summarizer_agent/tools/store_short_summary_to_drive.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/services/firebase/functions/scheduler.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/strategy_agent/tools/cluster_topics_embeddings.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/strategy_agent/tools/save_strategy_artifacts.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/strategy_agent/tools/generate_content_briefs.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/strategy_agent/tools/synthesize_strategy_playbook.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/strategy_agent/tools/mine_trigger_phrases.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/strategy_agent/tools/classify_post_types.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/strategy_agent/tools/extract_keywords_and_phrases.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/strategy_agent/tools/compute_engagement_signals.py',
        '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/strategy_agent/tools/fetch_corpus_from_zep.py'
    ]

    fixed_count = 0

    for filepath in files_to_fix:
        if os.path.exists(filepath):
            if fix_datetime_in_file(filepath):
                fixed_count += 1
        else:
            print(f"File not found: {filepath}")

    print(f"\nCompleted! Fixed {fixed_count} files.")

if __name__ == '__main__':
    main()