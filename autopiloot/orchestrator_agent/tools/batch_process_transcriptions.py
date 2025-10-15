"""
BatchProcessTranscriptions tool for parallel video transcription processing.
Processes multiple videos concurrently to maximize throughput.
"""

import os
import sys
import json
from typing import List, Dict, Any
from pydantic import Field
from agency_swarm.tools import BaseTool
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Add core and config directories to path
from google.cloud import firestore

load_dotenv()


class BatchProcessTranscriptions(BaseTool):
    """
    Process multiple video transcriptions in parallel for maximum throughput.

    This tool enables concurrent processing of multiple videos, dramatically reducing
    total processing time compared to sequential processing. Each video goes through:
    1. GetVideoAudioUrl (parallel)
    2. SubmitAssemblyAIJob (parallel)

    Benefits:
    - 3 videos in ~50s instead of ~150s (3x faster)
    - Automatic error handling per video
    - Progress tracking and partial results
    - Respects daily budget limits

    Example:
    - Sequential: 3 videos × 50s = 150s total
    - Parallel (3 workers): max(50s, 50s, 50s) = 50s total
    """

    video_ids: List[str] = Field(
        ...,
        description="List of video IDs to process in parallel (e.g., ['dQw4w9WgXcQ', 'mZxDw92UXmA'])"
    )

    max_workers: int = Field(
        default=3,
        description="Maximum number of concurrent workers (default: 3, recommended: 2-5)"
    )

    def run(self) -> str:
        """
        Process multiple videos in parallel.

        Returns:
            JSON string with:
            - total_videos: Number of videos processed
            - successful: Number of successful processings
            - failed: Number of failed processings
            - results: List of results per video
            - timings: Performance metrics
        """
        try:
            from transcriber_agent.tools.get_video_audio_url import GetVideoAudioUrl
            from transcriber_agent.tools.submit_assemblyai_job import SubmitAssemblyAIJob
        except ImportError as e:
            return json.dumps({
                "error": "import_error",
                "message": f"Failed to import transcriber tools: {str(e)}"
            })

        overall_start = time.time()
        results = []

        print(f"\n🚀 Starting parallel processing of {len(self.video_ids)} videos...")
        print(f"   Workers: {self.max_workers}")
        print(f"   Videos: {', '.join(self.video_ids)}\n")

        def process_single_video(video_id: str) -> Dict[str, Any]:
            """Process a single video through the transcription pipeline."""
            video_start = time.time()
            result = {
                "video_id": video_id,
                "success": False,
                "steps_completed": []
            }

            try:
                # Step 1: Get audio URL and upload to Firebase Storage
                print(f"[{video_id}] Getting audio URL...")
                audio_tool = GetVideoAudioUrl(
                    video_url=f"https://www.youtube.com/watch?v={video_id}"
                )
                audio_result = audio_tool.run()
                audio_data = json.loads(audio_result)

                if "error" in audio_data:
                    result["error"] = audio_data["error"]
                    result["error_message"] = audio_data.get("message", "Unknown error")
                    result["failed_at"] = "get_audio_url"
                    return result

                result["steps_completed"].append("get_audio_url")
                result["storage_path"] = audio_data.get("storage_path")
                result["audio_url"] = audio_data.get("signed_url")
                result["duration"] = audio_data.get("duration", 0)
                result["cached"] = audio_data.get("cached", False)

                # Step 2: Submit to AssemblyAI
                print(f"[{video_id}] Submitting to AssemblyAI...")
                submit_tool = SubmitAssemblyAIJob(
                    audio_url=audio_data["signed_url"],
                    storage_path=audio_data.get("storage_path"),
                    video_id=video_id,
                    duration_sec=audio_data.get("duration", 0)
                )
                submit_result = submit_tool.run()
                submit_data = json.loads(submit_result)

                if "error" in submit_data:
                    result["error"] = submit_data["error"]
                    result["error_message"] = submit_data.get("message", "Unknown error")
                    result["failed_at"] = "submit_assemblyai"
                    return result

                result["steps_completed"].append("submit_assemblyai")
                result["assemblyai_job_id"] = submit_data.get("job_id")
                result["estimated_cost_usd"] = submit_data.get("estimated_cost_usd", 0)
                result["success"] = True

                # Calculate timing
                result["processing_time"] = time.time() - video_start
                print(f"[{video_id}] ✅ Completed in {result['processing_time']:.1f}s")

                return result

            except Exception as e:
                result["error"] = "processing_exception"
                result["error_message"] = str(e)
                result["failed_at"] = result["steps_completed"][-1] if result["steps_completed"] else "unknown"
                result["processing_time"] = time.time() - video_start
                print(f"[{video_id}] ❌ Failed: {str(e)}")
                return result

        # Process videos in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_video = {
                executor.submit(process_single_video, video_id): video_id
                for video_id in self.video_ids
            }

            # Collect results as they complete
            for future in as_completed(future_to_video):
                video_id = future_to_video[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        "video_id": video_id,
                        "success": False,
                        "error": "future_exception",
                        "error_message": str(e),
                        "failed_at": "executor"
                    })

        # Calculate summary statistics
        total_time = time.time() - overall_start
        successful = sum(1 for r in results if r.get("success", False))
        failed = len(results) - successful
        total_cost = sum(r.get("estimated_cost_usd", 0) for r in results)
        cached_count = sum(1 for r in results if r.get("cached", False))

        # Calculate time savings
        sequential_time = sum(r.get("processing_time", 0) for r in results)
        time_saved = sequential_time - total_time
        speedup = sequential_time / total_time if total_time > 0 else 1

        print(f"\n{'=' * 60}")
        print(f"📊 Batch Processing Complete")
        print(f"{'=' * 60}")
        print(f"  Total videos: {len(results)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Cached: {cached_count}")
        print(f"  Total cost: ${total_cost:.4f}")
        print(f"\n⏱️  Performance:")
        print(f"  Parallel time: {total_time:.1f}s")
        print(f"  Sequential time: {sequential_time:.1f}s")
        print(f"  Time saved: {time_saved:.1f}s")
        print(f"  Speedup: {speedup:.1f}x")
        print(f"{'=' * 60}\n")

        return json.dumps({
            "total_videos": len(results),
            "successful": successful,
            "failed": failed,
            "cached": cached_count,
            "total_cost_usd": total_cost,
            "results": results,
            "timings": {
                "total_parallel_time": total_time,
                "total_sequential_time": sequential_time,
                "time_saved": time_saved,
                "speedup": speedup
            }
        }, indent=2)


if __name__ == "__main__":
    print("=" * 80)
    print("BatchProcessTranscriptions Tool Test")
    print("=" * 80)
    print("\nProcessing 3 videos in parallel...\n")

    tool = BatchProcessTranscriptions(
        video_ids=[
            "dQw4w9WgXcQ",  # Rick Astley - 3:33
            "mZxDw92UXmA",  # Dan Martell
        ],
        max_workers=2
    )

    try:
        result = tool.run()
        print("\nFinal Result:")
        print(result)

        # Parse and display summary
        data = json.loads(result)
        if "timings" in data:
            timings = data["timings"]
            print(f"\n🎯 Performance Summary:")
            print(f"   Sequential would take: {timings['total_sequential_time']:.1f}s")
            print(f"   Parallel took: {timings['total_parallel_time']:.1f}s")
            print(f"   Time saved: {timings['time_saved']:.1f}s ({timings['speedup']:.1f}x faster)")

    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("Test complete!")
    print("=" * 80)
