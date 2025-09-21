#!/usr/bin/env python3
"""
Script to fix Drive Agent test files by removing problematic @patch decorators
and replacing them with proper context manager mocking.
"""

import os
import re
import sys

def fix_save_drive_ingestion_record_test():
    """Fix the save_drive_ingestion_record test file."""

    test_file = '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/tests/drive_tools/test_save_drive_ingestion_record.py'

    with open(test_file, 'r') as f:
        content = f.read()

    # Replace all @patch decorators for firestore.Client with proper context manager approach
    # First, remove all @patch decorators for firestore
    content = re.sub(r'    @patch\(\'save_drive_ingestion_record\.firestore\.Client\'\)\n', '', content)

    # Now fix each test method signature to remove the mock_client parameter
    test_methods = [
        'test_minimal_record_save',
        'test_success_rate_calculation',
        'test_error_categorization',
        'test_firestore_connection_error',
        'test_performance_metrics_calculation',
        'test_checkpoint_data_storage'
    ]

    for method in test_methods:
        # Change method signature
        old_signature = f'    def {method}(self, mock_client):'
        new_signature = f'    def {method}(self):'
        content = content.replace(old_signature, new_signature)

        # Add context manager with proper indentation
        method_start = content.find(new_signature)
        if method_start != -1:
            # Find the docstring end
            docstring_pattern = f'{new_signature}[\\s\\S]*?"""[\\s\\S]*?"""'
            match = re.search(docstring_pattern, content)
            if match:
                docstring_end = match.end()

                # Add the context manager code after the docstring
                context_manager = '''
        with patch('save_drive_ingestion_record.firestore') as mock_firestore:
            # Mock Firestore client and operations
            mock_client = MagicMock()
            mock_db = MagicMock()
            mock_doc_ref = MagicMock()
            mock_summary_ref = MagicMock()

            mock_firestore.Client = mock_client
            mock_firestore.SERVER_TIMESTAMP = MagicMock()
            mock_client.return_value = mock_db
            mock_db.collection.return_value.document.return_value = mock_doc_ref
            mock_db.collection.return_value = mock_summary_ref

'''

                # Find the next non-empty line after docstring
                rest_content = content[docstring_end:]
                lines = rest_content.split('\n')

                # Find first non-empty line that's not whitespace
                first_code_line_idx = 0
                for i, line in enumerate(lines):
                    if line.strip() and not line.startswith('        """'):
                        first_code_line_idx = i
                        break

                # Insert context manager and indent the rest of the method
                method_lines = []
                in_method = True
                indent_level = 0

                for i, line in enumerate(lines):
                    if i == first_code_line_idx:
                        method_lines.append(context_manager.rstrip())
                        indent_level = 12  # 3 levels of indentation

                    if i >= first_code_line_idx:
                        if line.strip() == '' or line.startswith('    def ') and i > first_code_line_idx:
                            in_method = False

                        if in_method:
                            if line.strip():
                                # Add extra indentation for lines inside the context manager
                                if line.startswith('        '):  # Originally 2-level indented
                                    method_lines.append('    ' + line)  # Make it 3-level
                                else:
                                    method_lines.append(line)
                            else:
                                method_lines.append(line)
                        else:
                            method_lines.append(line)
                    else:
                        method_lines.append(line)

                new_rest_content = '\n'.join(method_lines)
                content = content[:docstring_end] + new_rest_content

    # Special handling for test_firestore_connection_error which has different mocking pattern
    if 'test_firestore_connection_error' in content:
        # This test should mock the Client to raise an exception
        old_pattern = r'(def test_firestore_connection_error\(self\):.*?""".*?""")(.*?)(mock_client\.side_effect = Exception\("Firestore connection failed"\))'
        new_pattern = r'''\1
        with patch('save_drive_ingestion_record.firestore') as mock_firestore:
            mock_client = MagicMock()
            mock_firestore.Client = mock_client
            \3'''

        content = re.sub(old_pattern, new_pattern, content, flags=re.DOTALL)

    # Write back the fixed content
    with open(test_file, 'w') as f:
        f.write(content)

    print(f"Fixed {test_file}")

def fix_other_drive_tests():
    """Fix other Drive Agent test files that have similar issues."""

    drive_test_dir = '/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/tests/drive_tools/'

    # List of Drive test files that need fixing
    test_files = [
        'test_list_drive_changes.py',
        'test_list_tracked_targets_from_config.py',
        'test_resolve_folder_tree.py',
        'test_upsert_drive_docs_to_zep.py'
    ]

    for test_file in test_files:
        filepath = os.path.join(drive_test_dir, test_file)
        if os.path.exists(filepath):
            print(f"Processing {filepath}...")

            with open(filepath, 'r') as f:
                content = f.read()

            # Check if this file has the complex mock structure that needs fixing
            if 'patch.dict(\'sys.modules\'' in content:
                print(f"  File {test_file} uses complex mocking, checking for missing mocks...")

                # Add missing google module mock if needed
                if 'google.oauth2' in content and '\'google\': MagicMock()' not in content:
                    content = content.replace(
                        '\'google.oauth2\': mock_google_oauth2,',
                        '\'google\': MagicMock(),\n    \'google.oauth2\': mock_google_oauth2,'
                    )
                    print(f"  Added missing 'google' mock to {test_file}")

                # Add missing imports if needed
                if 'from unittest.mock import patch, MagicMock' not in content:
                    if 'from unittest.mock import' in content:
                        content = content.replace(
                            'from unittest.mock import',
                            'from unittest.mock import patch,'
                        )
                        content = content.replace(
                            'patch, MagicMock',
                            'patch, MagicMock'
                        )
                        if 'patch,' not in content:
                            content = content.replace(
                                'from unittest.mock import MagicMock',
                                'from unittest.mock import patch, MagicMock'
                            )
                        print(f"  Added missing 'patch' import to {test_file}")

            with open(filepath, 'w') as f:
                f.write(content)

            print(f"  Completed {test_file}")

if __name__ == '__main__':
    print("Fixing Drive Agent test files...")

    # Fix the main problematic test file
    fix_save_drive_ingestion_record_test()

    # Fix other Drive test files
    fix_other_drive_tests()

    print("\nAll Drive Agent test files have been processed!")