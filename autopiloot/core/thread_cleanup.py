"""
Thread Cleanup Utility for Agency Swarm v1.2.0 Conversation Persistence

Provides utilities for cleaning up old conversation threads from Firestore
to prevent unbounded growth and manage storage costs.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from google.cloud import firestore

logger = logging.getLogger(__name__)


def cleanup_old_threads(retention_days: int = 30, collection: str = "agency_threads") -> int:
    """
    Delete conversation threads older than retention_days from Firestore.

    This utility prevents unbounded thread growth by removing old conversations
    that are no longer needed for workflow resumption.

    Args:
        retention_days: Delete threads not updated in this many days (default: 30)
        collection: Firestore collection name (default: "agency_threads")

    Returns:
        int: Number of threads deleted

    Example:
        >>> # Delete threads older than 30 days
        >>> deleted_count = cleanup_old_threads(retention_days=30)
        >>> print(f"Deleted {deleted_count} old threads")
    """
    try:
        db = firestore.Client()
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        logger.info(f"Cleaning up threads in '{collection}' older than {retention_days} days (before {cutoff_date.isoformat()})")

        # Query for old threads
        old_threads_query = db.collection(collection).where(
            'updated_at', '<', cutoff_date
        )

        deleted_count = 0
        batch = db.batch()
        batch_size = 0
        max_batch_size = 500  # Firestore batch limit

        for doc in old_threads_query.stream():
            batch.delete(doc.reference)
            batch_size += 1
            deleted_count += 1

            # Commit batch when reaching limit
            if batch_size >= max_batch_size:
                batch.commit()
                logger.debug(f"Committed batch of {batch_size} deletions")
                batch = db.batch()
                batch_size = 0

        # Commit remaining deletions
        if batch_size > 0:
            batch.commit()
            logger.debug(f"Committed final batch of {batch_size} deletions")

        logger.info(f"Successfully deleted {deleted_count} old threads from '{collection}'")
        return deleted_count

    except Exception as e:
        logger.error(f"Failed to cleanup old threads: {e}")
        raise


def get_thread_stats(collection: str = "agency_threads") -> dict:
    """
    Get statistics about conversation threads in Firestore.

    Provides insight into thread storage usage and age distribution.

    Args:
        collection: Firestore collection name (default: "agency_threads")

    Returns:
        dict: Statistics including total_threads, oldest_thread_age_days, newest_thread_age_days

    Example:
        >>> stats = get_thread_stats()
        >>> print(f"Total threads: {stats['total_threads']}")
        >>> print(f"Oldest thread: {stats['oldest_thread_age_days']} days old")
    """
    try:
        db = firestore.Client()
        now = datetime.now(timezone.utc)

        threads = list(db.collection(collection).stream())
        total_threads = len(threads)

        if total_threads == 0:
            return {
                "total_threads": 0,
                "oldest_thread_age_days": None,
                "newest_thread_age_days": None
            }

        # Calculate thread ages
        ages = []
        for doc in threads:
            doc_data = doc.to_dict()
            updated_at = doc_data.get('updated_at')
            if updated_at:
                age_days = (now - updated_at).days
                ages.append(age_days)

        oldest_age = max(ages) if ages else None
        newest_age = min(ages) if ages else None

        stats = {
            "total_threads": total_threads,
            "oldest_thread_age_days": oldest_age,
            "newest_thread_age_days": newest_age
        }

        logger.info(f"Thread stats for '{collection}': {stats}")
        return stats

    except Exception as e:
        logger.error(f"Failed to get thread stats: {e}")
        raise


if __name__ == "__main__":
    # Test the cleanup utility
    print("Thread Cleanup Utility Test")
    print("-" * 50)

    # Get current stats
    print("\nCurrent thread statistics:")
    stats = get_thread_stats()
    print(f"  Total threads: {stats['total_threads']}")
    print(f"  Oldest thread age: {stats['oldest_thread_age_days']} days")
    print(f"  Newest thread age: {stats['newest_thread_age_days']} days")

    # Clean up old threads (dry run with very high retention to avoid deleting anything in test)
    print("\nTesting cleanup (retention: 365 days - threads older than 1 year):")
    deleted = cleanup_old_threads(retention_days=365)
    print(f"  Deleted {deleted} threads older than 365 days")

    # Get updated stats
    print("\nUpdated thread statistics:")
    stats_after = get_thread_stats()
    print(f"  Total threads: {stats_after['total_threads']}")
    print(f"  Oldest thread age: {stats_after['oldest_thread_age_days']} days")
