"""
StoreShortInZep tool for storing video summaries in Zep v3 using Threads API.
Enables semantic search and retrieval with user-based organization by channel.

Zep v3 Architecture:
- Users: Represent YouTube channels (e.g., user_id = "danmartell")
- Threads: Represent individual videos (e.g., thread_id = "summary_VIDEO_ID")
- Messages: Contain the actual summary content with metadata
- Context: Zep automatically builds knowledge graph from thread messages
"""

import os
import sys
import json
from typing import List, Optional, Dict
from datetime import datetime, timezone
from pydantic import Field
from agency_swarm.tools import BaseTool

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, load_environment


class StoreShortInZep(BaseTool):
    """
    Store summary content in Zep v3 for semantic search and retrieval.

    Uses Zep v3 Threads API with users representing channels and threads representing videos.
    Zep automatically builds a knowledge graph from the stored content for enhanced discovery.
    """

    video_id: str = Field(
        ...,
        description="YouTube video ID for Zep thread reference"
    )
    bullets: List[str] = Field(
        ...,
        description="List of actionable insights to store in Zep"
    )
    key_concepts: List[str] = Field(
        ...,
        description="List of key concepts to store in Zep"
    )
    concept_explanations: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Detailed explanations for each concept (array of {concept, explanation} objects)"
    )
    channel_handle: Optional[str] = Field(
        default=None,
        description="YouTube channel handle (e.g., '@DanMartell') for user-based organization in Zep"
    )
    title: Optional[str] = Field(
        default=None,
        description="Video title for metadata"
    )

    def run(self) -> str:
        """
        Store summary content in Zep v3 using Threads API.

        Process:
        1. Extract user_id from channel_handle (e.g., "@DanMartell" -> "danmartell")
        2. Create or verify user exists in Zep
        3. Create thread for this video summary
        4. Add summary content as messages to the thread
        5. Zep automatically builds knowledge graph from content

        Returns:
            JSON string with thread_id, user_id, and storage confirmation
        """
        try:
            # Load environment and configuration
            load_environment()

            # Get Zep configuration
            zep_api_key = get_required_env_var("ZEP_API_KEY", "Zep API key for GraphRAG")
            zep_base_url = os.getenv("ZEP_BASE_URL", "https://api.getzep.com")

            # Extract user_id from channel_handle
            user_id = self._extract_user_id(self.channel_handle)
            thread_id = f"summary_{self.video_id}"

            # Initialize HTTP client
            zep_client = self._initialize_http_client(zep_api_key, zep_base_url)

            print(f"📤 Storing summary in Zep v3...")
            print(f"   User ID: {user_id}")
            print(f"   Thread ID: {thread_id}")

            # Step 1: Ensure user exists
            user_result = self._ensure_user_exists(zep_client, zep_base_url, user_id, self.channel_handle)
            if not user_result.get("success"):
                return json.dumps({
                    "error": "zep_user_creation_failed",
                    "message": f"Failed to create/verify user: {user_result.get('error', 'Unknown error')}",
                    "video_id": self.video_id
                }, indent=2)

            # Step 2: Create thread for this video
            thread_result = self._create_thread(zep_client, zep_base_url, thread_id, user_id)
            if not thread_result.get("success"):
                return json.dumps({
                    "error": "zep_thread_creation_failed",
                    "message": f"Failed to create thread: {thread_result.get('error', 'Unknown error')}",
                    "video_id": self.video_id
                }, indent=2)

            # Step 3: Add summary content as messages
            content = self._format_content()
            message_result = self._add_messages(zep_client, zep_base_url, thread_id, content)
            if not message_result.get("success"):
                return json.dumps({
                    "error": "zep_message_addition_failed",
                    "message": f"Failed to add messages: {message_result.get('error', 'Unknown error')}",
                    "video_id": self.video_id,
                    "thread_id": thread_id
                }, indent=2)

            print(f"   ✅ Summary stored successfully!")
            print(f"   Message UUIDs: {message_result.get('message_uuids', [])}")

            return json.dumps({
                "thread_id": thread_id,
                "user_id": user_id,
                "message_uuids": message_result.get("message_uuids", []),
                "stored_bullets": len(self.bullets),
                "stored_concepts": len(self.key_concepts),
                "channel_handle": self.channel_handle,
                "status": "stored",
                "message": f"Summary stored in Zep v3 for user '{user_id}', thread '{thread_id}'"
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "storage_failed",
                "message": f"Failed to store summary in Zep: {str(e)}",
                "video_id": self.video_id
            })

    def _extract_user_id(self, channel_handle: Optional[str]) -> str:
        """
        Extract user_id from channel_handle.

        Examples:
            "@DanMartell" -> "danmartell"
            "@AlexHormozi" -> "alexhormozi"
            None -> "unknown_channel"
        """
        if not channel_handle:
            return "unknown_channel"

        # Remove @ prefix and convert to lowercase
        user_id = channel_handle.lstrip('@').lower()
        return user_id

    def _initialize_http_client(self, api_key: str, base_url: str):
        """Initialize HTTP client for Zep v3 API."""
        import httpx

        client = httpx.Client(
            headers={
                "Authorization": f"Api-Key {api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        return client

    def _ensure_user_exists(self, client, base_url: str, user_id: str, channel_handle: Optional[str]) -> dict:
        """
        Ensure user exists in Zep. Create if not exists.

        Args:
            client: HTTP client
            base_url: Zep base URL
            user_id: Zep user ID (lowercase channel name)
            channel_handle: Original channel handle for metadata

        Returns:
            dict: {"success": bool, "user_uuid": str, "error": str}
        """
        try:
            # Try to create user (409 if already exists is OK)
            user_data = {
                "user_id": user_id,
                "metadata": {
                    "channel_handle": channel_handle,
                    "source": "youtube"
                }
            }

            response = client.post(f"{base_url}/api/v2/users", json=user_data)

            if response.status_code in [200, 201]:
                result = response.json()
                return {
                    "success": True,
                    "user_uuid": result.get("uuid"),
                    "status": "created"
                }
            elif response.status_code in [400, 409]:
                # User already exists - check error message
                error_text = response.text.lower()
                if "already exists" in error_text or "user_id: " + user_id in error_text:
                    return {
                        "success": True,
                        "status": "already_exists"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text[:200]}"
                    }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _create_thread(self, client, base_url: str, thread_id: str, user_id: str) -> dict:
        """
        Create thread in Zep for this video summary.

        Args:
            client: HTTP client
            base_url: Zep base URL
            thread_id: Thread ID (e.g., "summary_VIDEO_ID")
            user_id: User ID (channel name)

        Returns:
            dict: {"success": bool, "thread_uuid": str, "error": str}
        """
        try:
            thread_data = {
                "thread_id": thread_id,
                "user_id": user_id,
                "metadata": {
                    "video_id": self.video_id,
                    "title": self.title,
                    "channel_handle": self.channel_handle,
                    "source": "youtube",
                    "type": "summary"
                }
            }

            response = client.post(f"{base_url}/api/v2/threads", json=thread_data)

            if response.status_code in [200, 201]:
                result = response.json()
                return {
                    "success": True,
                    "thread_uuid": result.get("uuid"),
                    "status": "created"
                }
            elif response.status_code in [400, 409]:
                # Thread already exists - check error message
                error_text = response.text.lower()
                if "already exists" in error_text or "thread_id: " + thread_id in error_text:
                    return {
                        "success": True,
                        "status": "already_exists"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text[:200]}"
                    }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _add_messages(self, client, base_url: str, thread_id: str, content: str) -> dict:
        """
        Add summary content as messages to the thread.

        Args:
            client: HTTP client
            base_url: Zep base URL
            thread_id: Thread ID
            content: Formatted summary content

        Returns:
            dict: {"success": bool, "message_uuids": List[str], "error": str}
        """
        try:
            message_data = {
                "messages": [
                    {
                        "role": "assistant",
                        "content": content,
                        "metadata": {
                            "type": "summary",
                            "bullets_count": len(self.bullets),
                            "concepts_count": len(self.key_concepts),
                            "video_id": self.video_id,
                            "stored_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                ]
            }

            response = client.post(
                f"{base_url}/api/v2/threads/{thread_id}/messages",
                json=message_data
            )

            if response.status_code in [200, 201]:
                result = response.json()
                return {
                    "success": True,
                    "message_uuids": result.get("message_uuids", [])
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _format_content(self) -> str:
        """
        Format bullets and key concepts into searchable content.

        Returns:
            str: Formatted content for Zep storage
        """
        sections = []

        # Add title if available
        if self.title:
            sections.append(f"# {self.title}\n")

        # Add bullets
        if self.bullets:
            sections.append("## Actionable Insights\n")
            for i, bullet in enumerate(self.bullets, 1):
                sections.append(f"{i}. {bullet}")
            sections.append("")

        # Add key concepts
        if self.key_concepts:
            sections.append("## Key Concepts\n")
            sections.append(", ".join(self.key_concepts))
            sections.append("")

        # Add concept explanations with HOW/WHEN/WHY
        if self.concept_explanations:
            sections.append("## Concept Explanations\n")
            for i, explanation in enumerate(self.concept_explanations, 1):
                concept_name = explanation.get("concept", f"Concept {i}")
                concept_explanation = explanation.get("explanation", "")
                sections.append(f"### {concept_name}")
                sections.append(f"{concept_explanation}\n")

        return "\n".join(sections)


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST: Store Dan Martell summary in Zep v3 with Threads API")
    print("="*80)

    try:
        # Test with Dan Martell business content
        tool_dan = StoreShortInZep(
            video_id="mZxDw92UXmA",
            title="How to 10x Your Business - Dan Martell",
            bullets=[
                "Focus on hiring A-players who can scale with your business, not just fill immediate gaps",
                "Use the 'Buyback Principle': calculate your hourly rate and systematically buy back your time by delegating tasks below that rate",
                "Implement the 1-3-1 framework: 1 priority for the year, 3 priorities for the quarter, 1 priority for the week",
                "Build systems and processes before you think you need them - document everything as you go",
                "Track your time in 15-minute increments for one week to identify where you're wasting energy on low-value tasks"
            ],
            key_concepts=[
                "Buyback Principle",
                "A-Player Hiring Framework",
                "1-3-1 Priority System",
                "Time Audit Methodology",
                "Systems Documentation",
                "Energy Management"
            ],
            concept_explanations=[
                {
                    "concept": "Buyback Principle",
                    "explanation": "HOW: Calculate your effective hourly rate (annual income ÷ 2000 hours). Identify tasks taking your time below this rate. Hire or delegate those tasks. WHEN: Use when you're overwhelmed, working 60+ hours/week, or stuck doing tasks worth less than your hourly rate. Most effective for entrepreneurs earning $100k+ who are still doing $20/hr tasks. WHY: Frees your time for high-leverage activities (strategy, sales, partnerships) that only you can do. Creates compound growth by focusing energy on revenue-generating work."
                },
                {
                    "concept": "1-3-1 Priority System",
                    "explanation": "HOW: Define 1 major goal for the year, break it into 3 quarterly priorities, then focus on 1 weekly priority that moves the needle. Review and adjust quarterly. WHEN: Use during strategic planning, when feeling scattered, or when team lacks focus. Essential for fast-growing companies with multiple opportunities. WHY: Prevents shiny object syndrome and ensures alignment across organization. Forces brutal prioritization, saying no to good ideas to focus on great ones."
                },
                {
                    "concept": "A-Player Hiring Framework",
                    "explanation": "HOW: Define role outcomes (not tasks), hire for trajectory (can they 10x with you?), use scorecards with clear metrics, conduct structured interviews testing problem-solving. WHEN: Use when scaling beyond 10 employees, entering new markets, or replacing underperformers. Critical during growth phases (Series A onwards). WHY: A-players attract other A-players, creating performance culture. They solve problems independently, require less management, and scale with the business rather than becoming bottlenecks."
                }
            ],
            channel_handle="@DanMartell"
        )
    except Exception as e:
        print(f"❌ Error creating tool instance: {str(e)}")
        traceback.print_exc()
        import sys
        sys.exit(1)

    try:
        result = tool_dan.run()
        print("✅ Test completed:")
        print(result)

        data = json.loads(result)
        if "error" in data:
            print(f"\n❌ Error: {data['message']}")
        else:
            print(f"\n📊 Storage Summary:")
            print(f"   Thread ID: {data['thread_id']}")
            print(f"   User ID: {data['user_id']}")
            print(f"   Channel Handle: {data['channel_handle']}")
            print(f"   Message UUIDs: {data['message_uuids']}")
            print(f"   Bullets Stored: {data['stored_bullets']}")
            print(f"   Concepts Stored: {data['stored_concepts']}")
            print(f"\n💡 {data['message']}")
            print(f"\n🔍 Zep v3 Architecture:")
            print(f"   - Users represent YouTube channels (user_id: {data['user_id']})")
            print(f"   - Threads represent individual videos (thread_id: {data['thread_id']})")
            print(f"   - Messages contain summary content with automatic knowledge graph building")
            print(f"   - Search and retrieve via Zep's context API")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("Testing complete! Summary stored in Zep v3 with Threads API.")
    print("="*80)
