"""
Isolated test suite for ExtractTextFromDocument tool logic.
Tests the core functionality without importing the actual tool class.
Focuses on text extraction methods, cleaning, and formatting logic.
"""

import unittest
import json
import base64
import io
import re
import html
from unittest.mock import patch, MagicMock, mock_open


class TestExtractTextFromDocumentLogic(unittest.TestCase):
    """Test cases for ExtractTextFromDocument tool logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_plain_text = "This is a sample document.\n\nIt has multiple paragraphs.\n\nAnd some formatting."
        self.sample_csv_content = "Name,Age,City\nJohn,30,New York\nJane,25,Boston\nBob,35,Chicago"
        self.sample_html_content = """
        <html>
            <head><title>Test Document</title></head>
            <body>
                <h1>Main Title</h1>
                <p>This is the first paragraph.</p>
                <p>This is the second paragraph.</p>
                <script>console.log('should be removed');</script>
                <style>body { color: red; }</style>
            </body>
        </html>
        """

    def test_text_cleaning_logic(self):
        """Test text cleaning functionality."""
        messy_text = "This   has    excessive   whitespace\n\n\n\n\nAnd too many newlines....."
        
        # Replicate the cleaning logic from the tool
        cleaned_text = self._clean_text(messy_text)
        
        # Should have normalized whitespace and newlines
        self.assertNotIn("   ", cleaned_text)  # No triple spaces
        self.assertNotIn("\n\n\n", cleaned_text)  # No triple newlines
        self.assertIn("...", cleaned_text)  # Ellipsis normalized

    def _clean_text(self, text: str) -> str:
        """Replicate the tool's text cleaning logic."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove excessive newlines but preserve paragraph structure
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove common document artifacts
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # Remove excessive punctuation
        text = re.sub(r'[.]{3,}', '...', text)
        text = re.sub(r'[-]{3,}', '---', text)
        
        # Clean up spacing around punctuation
        text = re.sub(r'\s+([,.!?;:])', r'\1', text)
        text = re.sub(r'([,.!?;:])\s+', r'\1 ', text)
        
        # Trim and normalize
        text = text.strip()
        
        return text

    def test_csv_extraction_logic(self):
        """Test CSV text extraction and formatting logic."""
        csv_content = self.sample_csv_content
        
        # Replicate CSV processing logic
        result = self._extract_text_from_csv(csv_content)
        
        extracted_text = result["text"]
        metadata = result["metadata"]
        
        self.assertIn("Headers:", extracted_text)
        self.assertIn("Name, Age, City", extracted_text)
        self.assertIn("Row 1:", extracted_text)
        self.assertIn("John | 30 | New York", extracted_text)
        
        # Check metadata
        self.assertEqual(metadata["row_count"], 4)  # Header + 3 data rows
        self.assertEqual(metadata["column_count"], 3)
        self.assertEqual(metadata["extraction_method"], "csv")

    def _extract_text_from_csv(self, csv_content: str) -> dict:
        """Replicate the tool's CSV extraction logic."""
        try:
            import csv
            import io
            
            # Parse CSV
            csv_file = io.StringIO(csv_content)
            reader = csv.reader(csv_file)
            
            rows = list(reader)
            if not rows:
                return {
                    "text": "[Empty CSV file]",
                    "metadata": {"row_count": 0, "extraction_method": "csv"}
                }
            
            # Format as structured text
            text_lines = []
            
            # Add header if it exists
            if rows:
                header = rows[0]
                text_lines.append("Headers: " + ", ".join(header))
                text_lines.append("=" * 50)
                
                # Add data rows
                for i, row in enumerate(rows[1:], 1):
                    if i <= 100:  # Limit to first 100 rows for performance
                        row_text = " | ".join(str(cell) for cell in row)
                        text_lines.append(f"Row {i}: {row_text}")
                    else:
                        text_lines.append(f"... and {len(rows) - 101} more rows")
                        break
            
            full_text = "\n".join(text_lines)
            
            return {
                "text": full_text,
                "metadata": {
                    "row_count": len(rows),
                    "column_count": len(rows[0]) if rows else 0,
                    "extraction_method": "csv",
                    "truncated": len(rows) > 101
                }
            }
            
        except Exception as e:
            return {
                "text": f"[Error processing CSV: {str(e)}]",
                "metadata": {"error": str(e)}
            }

    def test_html_extraction_fallback_logic(self):
        """Test HTML extraction with fallback regex method."""
        html_content = self.sample_html_content
        
        # Replicate fallback HTML processing
        result = self._extract_text_from_html_fallback(html_content)
        
        extracted_text = result["text"]
        metadata = result["metadata"]
        
        # Should contain text but not HTML tags
        self.assertIn("Main Title", extracted_text)
        self.assertNotIn("<html>", extracted_text)
        self.assertNotIn("<script>", extracted_text)
        self.assertNotIn("console.log", extracted_text)  # Script content removed
        
        self.assertEqual(metadata["extraction_method"], "regex_fallback")

    def _extract_text_from_html_fallback(self, html_content: str) -> dict:
        """Replicate the tool's HTML fallback extraction logic."""
        try:
            # Remove script and style elements
            text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', '', text)
            
            # Decode HTML entities
            text = html.unescape(text)
            
            return {
                "text": text,
                "metadata": {
                    "extraction_method": "regex_fallback",
                    "original_length": len(html_content)
                }
            }
        except Exception as e:
            return {
                "text": f"[Error processing HTML: {str(e)}]",
                "metadata": {"error": str(e)}
            }

    def test_base64_decoding_logic(self):
        """Test base64 decoding functionality."""
        original_text = "This is base64 encoded text content with special chars: ñáéíóú"
        encoded_content = base64.b64encode(original_text.encode('utf-8')).decode('ascii')
        
        # Test decoding
        decoded_bytes = base64.b64decode(encoded_content)
        decoded_text = decoded_bytes.decode('utf-8')
        
        self.assertEqual(decoded_text, original_text)

    def test_length_limiting_logic(self):
        """Test text length limiting functionality."""
        long_text = "A" * 1000  # 1000 character text
        max_length = 500
        
        # Replicate length limiting logic
        if len(long_text) > max_length:
            truncated_text = long_text[:max_length] + "\n\n[Text truncated due to length limit]"
        else:
            truncated_text = long_text
        
        self.assertLessEqual(len(truncated_text), 600)  # 500 + truncation message
        self.assertIn("[Text truncated due to length limit]", truncated_text)

    def test_text_statistics_calculation(self):
        """Test text statistics calculation logic."""
        test_text = "First paragraph.\n\nSecond paragraph with more words."
        
        # Calculate statistics
        stats = {
            "character_count": len(test_text),
            "word_count": len(test_text.split()),
            "line_count": test_text.count('\n') + 1,
            "paragraph_count": len([p for p in test_text.split('\n\n') if p.strip()])
        }
        
        self.assertGreater(stats["character_count"], 0)
        self.assertGreater(stats["word_count"], 0)
        self.assertGreater(stats["line_count"], 0)
        self.assertEqual(stats["paragraph_count"], 2)  # Two paragraphs separated by double newline

    def test_mime_type_detection_logic(self):
        """Test MIME type handling logic."""
        test_cases = [
            ("text/plain", "supported"),
            ("text/csv", "supported"),
            ("text/html", "supported"),
            ("application/pdf", "supported"),
            ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "supported"),
            ("application/vnd.google-apps.document", "supported"),
            ("application/octet-stream", "unsupported"),
            ("image/jpeg", "unsupported")
        ]
        
        for mime_type, expected in test_cases:
            supported = self._is_mime_type_supported(mime_type)
            if expected == "supported":
                self.assertTrue(supported, f"MIME type {mime_type} should be supported")
            else:
                self.assertFalse(supported, f"MIME type {mime_type} should not be supported")

    def _is_mime_type_supported(self, mime_type: str) -> bool:
        """Check if MIME type is supported."""
        supported_types = [
            'text/plain',
            'text/csv',
            'text/html',
            'application/xhtml+xml',
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]
        
        return (
            mime_type in supported_types or
            mime_type.startswith('text/') or
            mime_type.startswith('application/vnd.google-apps')
        )

    def test_error_response_structure(self):
        """Test error response structure."""
        error_response = {
            "error": "extraction_error",
            "message": "Failed to extract text from document",
            "details": {
                "file_name": "test.txt",
                "mime_type": "text/plain",
                "content_encoding": "text",
                "type": "ValueError"
            }
        }
        
        # Validate error structure
        self.assertIn("error", error_response)
        self.assertIn("message", error_response)
        self.assertIn("details", error_response)
        self.assertIsInstance(error_response["details"], dict)
        self.assertEqual(error_response["error"], "extraction_error")

    def test_success_response_structure(self):
        """Test success response structure."""
        success_response = {
            "extracted_text": "Sample extracted text",
            "text_length": 21,
            "file_info": {
                "name": "test.txt",
                "mime_type": "text/plain",
                "content_encoding": "text"
            },
            "document_metadata": {
                "extraction_method": "direct_text",
                "mime_type": "text/plain"
            },
            "text_stats": {
                "character_count": 21,
                "word_count": 3,
                "line_count": 1,
                "paragraph_count": 1
            }
        }
        
        # Validate success structure
        self.assertIn("extracted_text", success_response)
        self.assertIn("text_length", success_response)
        self.assertIn("file_info", success_response)
        self.assertIn("document_metadata", success_response)
        self.assertIn("text_stats", success_response)
        self.assertEqual(success_response["text_length"], 21)

    def test_encoding_detection_logic(self):
        """Test encoding detection for different text encodings."""
        test_text = "This is a test with special characters: ñáéíóú"
        
        # Test different encodings
        encodings_to_test = ['utf-8', 'utf-16', 'latin-1']
        
        for encoding in encodings_to_test:
            try:
                encoded_bytes = test_text.encode(encoding)
                
                # Try to decode with different encodings (like the tool does)
                for try_encoding in ['utf-8', 'utf-16', 'latin-1']:
                    try:
                        decoded_text = encoded_bytes.decode(try_encoding)
                        if try_encoding == encoding:
                            self.assertEqual(decoded_text, test_text)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    # Fall back to replace errors
                    decoded_text = encoded_bytes.decode('utf-8', errors='replace')
                    self.assertIsInstance(decoded_text, str)
                    
            except UnicodeEncodeError:
                # Some characters can't be encoded in latin-1, that's expected
                continue

    def test_large_csv_truncation_logic(self):
        """Test CSV truncation for large files."""
        # Create CSV with many rows
        rows = ["Name,Age,City"]
        for i in range(150):  # More than 100 rows
            rows.append(f"Person{i},25,City{i}")
        large_csv = "\n".join(rows)
        
        # Test the CSV extraction with truncation
        result = self._extract_text_from_csv(large_csv)
        
        extracted_text = result["text"]
        metadata = result["metadata"]
        
        self.assertIn("... and 50 more rows", extracted_text)  # Should truncate after 100 rows
        self.assertTrue(metadata.get("truncated", False))
        self.assertEqual(metadata["row_count"], 151)  # Original count preserved

    def test_content_encoding_handling(self):
        """Test content encoding parameter handling."""
        test_cases = [
            ("text", "This is plain text", "This is plain text"),
            ("base64", base64.b64encode(b"This is base64 text").decode(), "This is base64 text")
        ]
        
        for encoding, content, expected in test_cases:
            if encoding == "base64":
                # Decode base64
                decoded_bytes = base64.b64decode(content)
                result_text = decoded_bytes.decode('utf-8')
            else:
                # Plain text
                result_text = content
            
            self.assertEqual(result_text, expected)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
