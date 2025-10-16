"""
SaveChannelMapping tool for persisting YouTube handle → channel_id mappings to Firestore.
Implements TASK-0071: Idempotent storage of channel metadata for downstream reference.
"""

import os
import sys
import json
from typing import Optional
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field, field_validator
from google.cloud import firestore

# Add core and config directories to path
from config.env_loader import get_required_env_var
from core.firestore_client import get_firestore_client
from core.time_utils import now, to_iso8601_z



class SaveChannelMapping(BaseTool):
    """
    Save YouTube channel handle → channel_id mapping to Firestore with idempotent upsert semantics.

    Stores channel metadata in `channels` collection with document ID = channel_id.
    Maintains historical handles list and supports handle normalization.

    Firestore Schema:
    - Collection: channels
    - Document ID: {channel_id}
    - Fields:
      * channel_id: str
      * canonical_handle: str (normalized with @ prefix)
      * handles: List[str] (unique set of all known handles)
      * title: Optional[str]
      * custom_url: Optional[str]
      * thumbnails: Optional[Dict] (parsed from thumbnails_json)
      * last_resolved_at: str (ISO 8601 with Z)
      * created_at: SERVER_TIMESTAMP
      * updated_at: SERVER_TIMESTAMP
    """

    handle: str = Field(
        ...,
        description="YouTube channel handle (e.g., '@AlexHormozi' or 'AlexHormozi')"
    )

    channel_id: str = Field(
        ...,
        description="YouTube channel ID (e.g., 'UCfV36TX5AejfAGIbtwTc7Zw')"
    )

    title: Optional[str] = Field(
        default=None,
        description="Channel title/name (optional)"
    )

    custom_url: Optional[str] = Field(
        default=None,
        description="Channel custom URL (optional)"
    )

    thumbnails_json: Optional[str] = Field(
        default=None,
        description="JSON-encoded thumbnails map (optional)"
    )

    @field_validator('handle')
    @classmethod
    def validate_handle(cls, v: str) -> str:
        """Ensure handle is not empty."""
        if not v or not v.strip():
            raise ValueError("Handle cannot be empty")
        return v.strip()

    @field_validator('channel_id')
    @classmethod
    def validate_channel_id(cls, v: str) -> str:
        """Ensure channel_id is not empty."""
        if not v or not v.strip():
            raise ValueError("Channel ID cannot be empty")
        return v.strip()

    def run(self) -> str:
        """
        Save channel mapping to Firestore with idempotent upsert.

        Process:
        1. Normalize handle to canonical format (@ prefix, case-insensitive matching)
        2. Initialize Firestore client
        3. Upsert to channels/{channel_id}:
           - Create with created_at if new
           - Merge handles list (set semantics)
           - Update updated_at timestamp
        4. Return JSON string with ok, channel_id, canonical_handle

        Returns:
            JSON string: {"ok": true, "channel_id": "...", "canonical_handle": "@..."}
                        or {"error": "...", "message": "..."}
        """
        try:
            # Step 1: Normalize handle
            canonical_handle = self._normalize_handle(self.handle)

            # Step 2: Parse thumbnails if provided
            thumbnails = None
            if self.thumbnails_json:
                try:
                    thumbnails = json.loads(self.thumbnails_json)
                except json.JSONDecodeError as e:
                    return json.dumps({
                        "error": "invalid_thumbnails_json",
                        "message": f"Failed to parse thumbnails_json: {str(e)}"
                    })

            # Step 3: Initialize Firestore
            db = get_firestore_client()

            # Step 4: Upsert channel mapping
            doc_ref = db.collection('channels').document(self.channel_id)

            # Get current document to check if it exists
            doc = doc_ref.get()
            current_time = to_iso8601_z(now())

            if doc.exists:
                # Update existing document
                existing_data = doc.to_dict()
                existing_handles = existing_data.get('handles', [])

                # Merge handles (set semantics, case-insensitive)
                updated_handles = self._merge_handles(existing_handles, canonical_handle)

                update_data = {
                    'canonical_handle': canonical_handle,
                    'handles': updated_handles,
                    'last_resolved_at': current_time,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }

                # Update optional fields if provided
                if self.title is not None:
                    update_data['title'] = self.title
                if self.custom_url is not None:
                    update_data['custom_url'] = self.custom_url
                if thumbnails is not None:
                    update_data['thumbnails'] = thumbnails

                doc_ref.update(update_data)

            else:
                # Create new document
                create_data = {
                    'channel_id': self.channel_id,
                    'canonical_handle': canonical_handle,
                    'handles': [canonical_handle],
                    'last_resolved_at': current_time,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                }

                # Add optional fields if provided
                if self.title is not None:
                    create_data['title'] = self.title
                if self.custom_url is not None:
                    create_data['custom_url'] = self.custom_url
                if thumbnails is not None:
                    create_data['thumbnails'] = thumbnails

                doc_ref.set(create_data)

            # Step 5: Return success
            return json.dumps({
                "ok": True,
                "channel_id": self.channel_id,
                "canonical_handle": canonical_handle
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "save_failed",
                "message": f"Failed to save channel mapping: {str(e)}"
            })

    def _normalize_handle(self, handle: str) -> str:
        """
        Normalize handle to canonical format.

        Rules:
        - Add @ prefix if missing
        - Preserve original case for display
        - Used for case-insensitive matching in _merge_handles

        Args:
            handle: Raw handle input

        Returns:
            Normalized handle with @ prefix
        """
        handle = handle.strip()
        if not handle.startswith('@'):
            handle = f"@{handle}"
        return handle

    def _merge_handles(self, existing_handles: list, new_handle: str) -> list:
        """
        Merge new handle into existing handles list with case-insensitive uniqueness.

        Args:
            existing_handles: Current list of handles
            new_handle: New handle to add

        Returns:
            Updated list of unique handles (case-insensitive)
        """
        # Create case-insensitive set for comparison
        lowercase_handles = {h.lower() for h in existing_handles}

        # Add new handle if not already present (case-insensitive)
        if new_handle.lower() not in lowercase_handles:
            existing_handles.append(new_handle)

        return existing_handles


if __name__ == "__main__":
    print("=" * 80)
    print("SaveChannelMapping Tool Test")
    print("=" * 80)

    # Test 1: Create new channel mapping - Rick Astley
    print("\nTEST 1: Rick Astley - Never Gonna Give You Up")
    print("-" * 80)

    tool1 = SaveChannelMapping(
        handle="RickAstleyYT",  # Without @ prefix
        channel_id="UCuAXFkgsw1L7xaCfnd5JJOw",
        title="Rick Astley",
        custom_url="@RickAstleyYT"
    )

    try:
        result = tool1.run()
        print("Result:")
        print(result)

        data = json.loads(result)
        if data.get("ok"):
            print(f"\n✅ Success: Saved channel {data['channel_id']}")
            print(f"   Canonical handle: {data['canonical_handle']}")
        else:
            print(f"\n❌ Error: {data.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    # Test 2: Create channel mapping - Dan Martell
    print("\n" + "=" * 80)
    print("TEST 2: Dan Martell - How to 10x Your Business")
    print("-" * 80)

    tool2 = SaveChannelMapping(
        handle="@DanMartell",  # With @ prefix
        channel_id="UCFCu47CJXdhPEX5CmYAdvQg",
        title="Dan Martell"
    )

    try:
        result = tool2.run()
        print("Result:")
        print(result)

        data = json.loads(result)
        if data.get("ok"):
            print(f"\n✅ Success: Saved channel {data['channel_id']}")
            print(f"   Canonical handle: {data['canonical_handle']}")
        else:
            print(f"\n❌ Error: {data.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")

    # Test 3: Error handling - invalid JSON
    print("\n" + "=" * 80)
    print("TEST 3: Invalid thumbnails JSON")
    print("-" * 80)

    tool3 = SaveChannelMapping(
        handle="@TestChannel",
        channel_id="UC_TEST_123",
        thumbnails_json="{invalid json"
    )

    try:
        result = tool3.run()
        print("Result:")
        print(result)

        data = json.loads(result)
        if "error" in data:
            print(f"\n✅ Expected error caught: {data['error']}")
            print(f"   Message: {data['message']}")
    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")

    print("\n" + "=" * 80)
    print("Testing complete!")
    print("=" * 80)
