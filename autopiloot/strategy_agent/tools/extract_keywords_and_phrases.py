"""
ExtractKeywordsAndPhrases tool for identifying salient terms and phrases correlated with engagement.
Uses NLP techniques to extract keywords, keyphrases, and entities from content with engagement correlation.
"""

import json
import re
import math
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import Counter, defaultdict
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field


class ExtractKeywordsAndPhrases(BaseTool):
    """
    Extracts keywords, keyphrases, and entities from content items with engagement correlation analysis.

    Uses TF-IDF, n-gram analysis, and engagement correlation to identify the most impactful
    content elements for strategy development.
    """

    items: List[Dict[str, Any]] = Field(
        ...,
        description="List of content items with text and engagement scores"
    )

    top_n: int = Field(
        50,
        description="Number of top keywords/phrases to return (default: 50)"
    )

    min_text_length: int = Field(
        20,
        description="Minimum text length to process (default: 20 characters)"
    )

    language: str = Field(
        "en",
        description="Language for text processing (default: 'en' for English)"
    )

    include_entities: bool = Field(
        True,
        description="Whether to extract named entities (people, organizations, etc.)"
    )

    def run(self) -> str:
        """
        Extracts keywords, phrases, and entities correlated with engagement.

        Returns:
            str: JSON string containing extracted keywords, phrases, and entities
                 Format: {
                     "keywords": [
                         {
                             "term": "business",
                             "frequency": 25,
                             "tf_idf_score": 0.85,
                             "engagement_correlation": 0.72,
                             "avg_engagement": 0.68,
                             "documents": 15
                         }
                     ],
                     "phrases": [
                         {
                             "phrase": "business strategy",
                             "frequency": 12,
                             "engagement_correlation": 0.81,
                             "avg_engagement": 0.75,
                             "length": 2,
                             "documents": 8
                         }
                     ],
                     "entities": [
                         {
                             "entity": "OpenAI",
                             "type": "organization",
                             "frequency": 8,
                             "engagement_correlation": 0.65,
                             "avg_engagement": 0.70
                         }
                     ],
                     "analysis_metadata": {
                         "total_items": 100,
                         "processed_items": 95,
                         "total_words": 15000,
                         "unique_words": 2500,
                         "language": "en",
                         "processing_method": "tf_idf_yake"
                     }
                 }
        """
        try:
            if not self.items:
                return json.dumps({
                    "error": "no_items",
                    "message": "No items provided for keyword extraction"
                })

            # Validate and filter items
            valid_items = self._validate_items(self.items)

            if not valid_items:
                return json.dumps({
                    "error": "no_valid_items",
                    "message": "No items contain sufficient text for analysis"
                })

            # Extract and preprocess text content
            text_data = self._extract_text_data(valid_items)

            # Extract keywords using TF-IDF
            keywords = self._extract_keywords_tfidf(text_data)

            # Extract keyphrases using n-gram analysis
            phrases = self._extract_keyphrases_ngram(text_data)

            # Extract entities if requested
            entities = []
            if self.include_entities:
                entities = self._extract_entities(text_data)

            # Correlate with engagement scores
            keywords_with_engagement = self._correlate_with_engagement(keywords, text_data, "keywords")
            phrases_with_engagement = self._correlate_with_engagement(phrases, text_data, "phrases")
            entities_with_engagement = self._correlate_with_engagement(entities, text_data, "entities")

            # Sort and limit results
            top_keywords = sorted(keywords_with_engagement,
                                key=lambda x: x.get("engagement_correlation", 0), reverse=True)[:self.top_n]
            top_phrases = sorted(phrases_with_engagement,
                               key=lambda x: x.get("engagement_correlation", 0), reverse=True)[:self.top_n]
            top_entities = sorted(entities_with_engagement,
                                key=lambda x: x.get("engagement_correlation", 0), reverse=True)[:self.top_n]

            # Calculate analysis metadata
            analysis_metadata = self._calculate_metadata(valid_items, text_data)

            # Prepare response
            result = {
                "keywords": top_keywords,
                "phrases": top_phrases,
                "entities": top_entities,
                "analysis_metadata": analysis_metadata
            }

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "keyword_extraction_failed",
                "message": str(e),
                "item_count": len(self.items) if self.items else 0,
                "top_n": self.top_n
            }
            return json.dumps(error_result)

    def _validate_items(self, items: List[Dict]) -> List[Dict]:
        """
        Validate and filter items for text processing.

        Args:
            items: Input items

        Returns:
            List[Dict]: Valid items with sufficient text content
        """
        valid_items = []

        for item in items:
            # Extract text content
            text = item.get("content", "") or item.get("text", "")

            if not text or len(text.strip()) < self.min_text_length:
                continue

            # Check for basic language characteristics (simple English check)
            if self.language == "en" and not self._is_likely_english(text):
                continue

            # Add processed item
            processed_item = item.copy()
            processed_item["processed_text"] = self._clean_text(text)
            valid_items.append(processed_item)

        return valid_items

    def _is_likely_english(self, text: str) -> bool:
        """Simple heuristic to check if text is likely English."""
        # Check for common English words
        common_words = {"the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        words = text.lower().split()
        english_word_count = sum(1 for word in words if word in common_words)
        return (english_word_count / max(len(words), 1)) > 0.05

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text for processing.

        Args:
            text: Raw text

        Returns:
            str: Cleaned text
        """
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)

        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove very short words and numbers only
        words = text.split()
        cleaned_words = [word for word in words if len(word) > 2 and not word.isdigit()]

        return ' '.join(cleaned_words)

    def _extract_text_data(self, items: List[Dict]) -> List[Dict]:
        """
        Extract and structure text data for analysis.

        Args:
            items: Valid items

        Returns:
            List[Dict]: Text data with metadata
        """
        text_data = []

        for item in items:
            text_item = {
                "id": item.get("id", ""),
                "text": item["processed_text"],
                "words": item["processed_text"].lower().split(),
                "engagement_score": item.get("engagement_score", 0.0),
                "word_count": len(item["processed_text"].split())
            }
            text_data.append(text_item)

        return text_data

    def _extract_keywords_tfidf(self, text_data: List[Dict]) -> List[Dict]:
        """
        Extract keywords using TF-IDF analysis.

        Args:
            text_data: Structured text data

        Returns:
            List[Dict]: Keywords with TF-IDF scores
        """
        # Calculate document frequency for each word
        word_doc_freq = Counter()
        all_words = set()

        for item in text_data:
            unique_words = set(item["words"])
            for word in unique_words:
                word_doc_freq[word] += 1
            all_words.update(unique_words)

        total_docs = len(text_data)
        keywords = []

        # Calculate TF-IDF for each word
        for word in all_words:
            if len(word) < 3 or word in self._get_stopwords():
                continue

            # Calculate total frequency
            total_freq = sum(item["words"].count(word) for item in text_data)

            # Calculate TF-IDF
            idf = math.log(total_docs / word_doc_freq[word])
            tf_idf = (total_freq / sum(len(item["words"]) for item in text_data)) * idf

            keywords.append({
                "term": word,
                "frequency": total_freq,
                "tf_idf_score": round(tf_idf, 4),
                "documents": word_doc_freq[word],
                "document_frequency": round(word_doc_freq[word] / total_docs, 3)
            })

        return keywords

    def _extract_keyphrases_ngram(self, text_data: List[Dict]) -> List[Dict]:
        """
        Extract keyphrases using n-gram analysis.

        Args:
            text_data: Structured text data

        Returns:
            List[Dict]: Keyphrases with frequency and scores
        """
        phrases = []
        phrase_freq = Counter()
        phrase_docs = Counter()

        # Extract 2-grams and 3-grams
        for item in text_data:
            words = item["words"]
            item_phrases = set()

            # 2-grams
            for i in range(len(words) - 1):
                phrase = f"{words[i]} {words[i+1]}"
                if self._is_valid_phrase(phrase):
                    phrase_freq[phrase] += 1
                    item_phrases.add(phrase)

            # 3-grams
            for i in range(len(words) - 2):
                phrase = f"{words[i]} {words[i+1]} {words[i+2]}"
                if self._is_valid_phrase(phrase):
                    phrase_freq[phrase] += 1
                    item_phrases.add(phrase)

            # Count documents containing each phrase
            for phrase in item_phrases:
                phrase_docs[phrase] += 1

        # Create phrase objects
        for phrase, freq in phrase_freq.items():
            if freq >= 2:  # Minimum frequency threshold
                phrases.append({
                    "phrase": phrase,
                    "frequency": freq,
                    "documents": phrase_docs[phrase],
                    "length": len(phrase.split()),
                    "document_frequency": round(phrase_docs[phrase] / len(text_data), 3)
                })

        return phrases

    def _is_valid_phrase(self, phrase: str) -> bool:
        """Check if phrase is valid for extraction."""
        words = phrase.split()

        # Skip if contains stopwords only
        if all(word in self._get_stopwords() for word in words):
            return False

        # Skip if all words are very short
        if all(len(word) < 3 for word in words):
            return False

        return True

    def _extract_entities(self, text_data: List[Dict]) -> List[Dict]:
        """
        Extract named entities using simple heuristics.

        Args:
            text_data: Structured text data

        Returns:
            List[Dict]: Entities with types and frequencies
        """
        entities = []
        entity_freq = Counter()
        entity_docs = Counter()

        # Simple entity extraction patterns
        for item in text_data:
            text = item["text"]
            item_entities = set()

            # Capitalized words (potential proper nouns)
            capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', text)
            for word in capitalized_words:
                if len(word) > 3 and word not in self._get_common_capitals():
                    entity_freq[word] += 1
                    item_entities.add(word)

            # Common business terms/companies
            business_patterns = [
                r'\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*\s+(?:Inc|LLC|Corp|Ltd|Company|Co)\b',
                r'\b(?:CEO|CTO|CFO|VP|Director)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
            ]

            for pattern in business_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    entity_freq[match] += 1
                    item_entities.add(match)

            # Count documents containing each entity
            for entity in item_entities:
                entity_docs[entity] += 1

        # Create entity objects
        for entity, freq in entity_freq.items():
            if freq >= 2:  # Minimum frequency threshold
                entity_type = self._classify_entity_type(entity)
                entities.append({
                    "entity": entity,
                    "type": entity_type,
                    "frequency": freq,
                    "documents": entity_docs[entity],
                    "document_frequency": round(entity_docs[entity] / len(text_data), 3)
                })

        return entities

    def _classify_entity_type(self, entity: str) -> str:
        """Simple entity type classification."""
        entity_lower = entity.lower()

        if any(term in entity_lower for term in ["inc", "llc", "corp", "ltd", "company", "co"]):
            return "organization"
        elif any(term in entity_lower for term in ["ceo", "cto", "cfo", "vp", "director"]):
            return "person"
        elif entity[0].isupper() and len(entity.split()) == 1:
            return "brand"
        else:
            return "unknown"

    def _get_common_capitals(self) -> Set[str]:
        """Get set of common capitalized words that aren't entities."""
        return {
            "The", "This", "That", "These", "Those", "And", "But", "Or", "So", "If", "When",
            "Where", "Why", "How", "What", "Who", "Which", "Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday", "Sunday", "January", "February", "March",
            "April", "May", "June", "July", "August", "September", "October", "November", "December"
        }

    def _correlate_with_engagement(self, terms: List[Dict], text_data: List[Dict], term_type: str) -> List[Dict]:
        """
        Correlate terms with engagement scores.

        Args:
            terms: List of terms (keywords, phrases, or entities)
            text_data: Text data with engagement scores
            term_type: Type of terms being processed

        Returns:
            List[Dict]: Terms with engagement correlation
        """
        for term_data in terms:
            if term_type == "keywords":
                term = term_data["term"]
            elif term_type == "phrases":
                term = term_data["phrase"]
            else:  # entities
                term = term_data["entity"]

            # Find items containing this term
            containing_items = []
            not_containing_items = []

            for item in text_data:
                if term.lower() in item["text"].lower():
                    containing_items.append(item["engagement_score"])
                else:
                    not_containing_items.append(item["engagement_score"])

            # Calculate engagement statistics
            if containing_items:
                avg_engagement = sum(containing_items) / len(containing_items)

                # Calculate correlation (simplified)
                if not_containing_items:
                    avg_engagement_without = sum(not_containing_items) / len(not_containing_items)
                    correlation = avg_engagement - avg_engagement_without
                else:
                    correlation = avg_engagement

                term_data["avg_engagement"] = round(avg_engagement, 4)
                term_data["engagement_correlation"] = round(correlation, 4)
                term_data["engagement_boost"] = round(correlation, 4)
            else:
                term_data["avg_engagement"] = 0.0
                term_data["engagement_correlation"] = 0.0
                term_data["engagement_boost"] = 0.0

        return terms

    def _calculate_metadata(self, valid_items: List[Dict], text_data: List[Dict]) -> Dict[str, Any]:
        """
        Calculate analysis metadata.

        Args:
            valid_items: Valid processed items
            text_data: Structured text data

        Returns:
            Dict: Analysis metadata
        """
        total_words = sum(item["word_count"] for item in text_data)
        all_words = set()
        for item in text_data:
            all_words.update(item["words"])

        return {
            "total_items": len(self.items),
            "processed_items": len(valid_items),
            "total_words": total_words,
            "unique_words": len(all_words),
            "avg_words_per_item": round(total_words / max(len(text_data), 1), 2),
            "language": self.language,
            "min_text_length": self.min_text_length,
            "processing_method": "tf_idf_ngram",
            "processed_at": datetime.now(timezone.utc).isoformat()
        }

    def _get_stopwords(self) -> Set[str]:
        """Get set of common English stopwords."""
        return {
            "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he",
            "in", "is", "it", "its", "of", "on", "that", "the", "to", "was", "will", "with",
            "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for",
            "not", "on", "with", "he", "as", "you", "do", "at", "this", "but", "his", "by",
            "from", "they", "we", "say", "her", "she", "or", "an", "will", "my", "one", "all",
            "would", "there", "their", "what", "so", "up", "out", "if", "about", "who", "get",
            "which", "go", "me", "when", "make", "can", "like", "time", "no", "just", "him",
            "know", "take", "people", "into", "year", "your", "good", "some", "could", "them",
            "see", "other", "than", "then", "now", "look", "only", "come", "its", "over",
            "think", "also", "back", "after", "use", "two", "how", "our", "work", "first",
            "well", "way", "even", "new", "want", "because", "any", "these", "give", "day",
            "most", "us"
        }


if __name__ == "__main__":
    # Test the tool
    test_items = [
        {
            "id": "post_1",
            "content": "Building a successful business requires focus on customer value and operational efficiency. The key to growth is understanding your market.",
            "engagement_score": 0.85
        },
        {
            "id": "post_2",
            "content": "Business strategy should always start with customer needs. Focus on solving real problems and the revenue will follow.",
            "engagement_score": 0.72
        },
        {
            "id": "post_3",
            "content": "Marketing automation tools like HubSpot and Salesforce can significantly improve your sales funnel conversion rates.",
            "engagement_score": 0.63
        },
        {
            "id": "post_4",
            "content": "Leadership is about inspiring others to achieve their best work. Great leaders focus on empowerment and growth.",
            "engagement_score": 0.45
        }
    ]

    tool = ExtractKeywordsAndPhrases(
        items=test_items,
        top_n=20,
        min_text_length=10,
        include_entities=True
    )

    print("Testing ExtractKeywordsAndPhrases tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))