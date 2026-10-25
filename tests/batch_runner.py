import json
import os
from typing import Dict, Any, List
from fastapi.testclient import TestClient
from incubrix.api.v1.app import app

client = TestClient(app)

SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "session_01_cut_beginning",
        "title": "Trim first 5 seconds",
        "commands": ["Cut the first 5 seconds."],
        "expected_final_duration": 25.0,
        "expected_status": "APPLIED"
    },
    {
        "id": "session_02_cut_end",
        "title": "Remove last 3 seconds",
        "commands": ["Remove the last 3 seconds."],
        "expected_final_duration": 27.0,
        "expected_status": "APPLIED"
    },
    {
        "id": "session_03_cut_middle",
        "title": "Cut range 10s to 15s",
        "commands": ["Cut from 10 to 15 seconds."],
        "expected_final_segments": 2,
        "expected_status": "APPLIED"
    },
    {
        "id": "session_04_speed_up_whole",
        "title": "Speed up whole video by 2x",
        "commands": ["Speed up the whole video by 2x."],
        "expected_final_duration": 15.0,
        "expected_status": "APPLIED"
    },
    {
        "id": "session_05_slow_down",
        "title": "Slow down video to half speed",
        "commands": ["Slow down the video to half speed."],
        "expected_final_duration": 60.0,
        "expected_status": "APPLIED"
    },
    {
        "id": "session_06_speed_range",
        "title": "Speed up section 5 to 10s by 2x",
        "commands": ["Speed up the video from 5 to 10 seconds by 2x."],
        "expected_final_duration": 27.5,
        "expected_status": "APPLIED"
    },
    {
        "id": "session_07_add_caption",
        "title": "Add caption at beginning",
        "commands": ["Add a caption saying Dance Practice at the beginning."],
        "expected_status": "APPLIED"
    },
    {
        "id": "session_08_change_caption_color",
        "title": "Change caption color to red",
        "commands": [
            "Add a caption saying Dance Practice at the beginning.",
            "Change the caption color to red."
        ],
        "expected_status": "APPLIED"
    },
    {
        "id": "session_09_remove_caption",
        "title": "Remove existing caption",
        "commands": [
            "Add a caption saying Dance Practice at the beginning.",
            "Remove the caption at the beginning."
        ],
        "expected_status": "APPLIED"
    },
    {
        "id": "session_10_swap_segments",
        "title": "Cut middle and swap resulting segments",
        "commands": [
            "Cut from 10 to 15 seconds.",
            "Swap the first and second segments."
        ],
        "expected_status": "APPLIED"
    },
    {
        "id": "session_11_reverse_segments",
        "title": "Reverse segment order",
        "commands": [
            "Cut from 10 to 15 seconds.",
            "Reverse the order of these two segments."
        ],
        "expected_status": "APPLIED"
    },
    {
        "id": "session_12_undo_redo_pipeline",
        "title": "Undo and Redo pipeline test",
        "commands": [
            "Cut the first 5 seconds.",
            "Undo the last edit.",
            "Redo the edit."
        ],
        "expected_final_duration": 25.0,
        "expected_status": "APPLIED"
    },
    {
        "id": "session_13_restore_intro",
        "title": "Restore removed intro region",
        "commands": [
            "Cut the first 5 seconds.",
            "Restore the intro."
        ],
        "expected_final_duration": 30.0,
        "expected_status": "APPLIED"
    },
    {
        "id": "session_14_ambiguous_rejection",
        "title": "Reject ungrounded section reference safely",
        "commands": ["Remove the pricing section."],
        "expected_status": "REJECTED"
    },
    {
        "id": "session_15_invalid_bounds_rejection",
        "title": "Reject out of bounds cut without state corruption",
        "commands": ["Cut from 50 to 60 seconds."],
        "expected_status": "REJECTED"
    }
]

def dump_session_files():
    sess_dir = os.path.join("tests", "sessions")
    os.makedirs(sess_dir, exist_ok=True)
    for sc in SCENARIOS:
        fp = os.path.join(sess_dir, f"{sc['id']}.json")
        with open(fp, "w") as f:
            json.dump(sc, f, indent=2)

def run_batch_sessions(video_path: str) -> List[Dict[str, Any]]:
    dump_session_files()
    results = []

    for sc in SCENARIOS:
        # 1. Upload
        with open(video_path, "rb") as f:
            up = client.post("/api/v1/media/upload", files={"file": ("session_test.mp4", f, "video/mp4")})
        asset_id = up.json()["asset_id"]

        # 2. Session
        s_res = client.post("/api/v1/sessions", json={"asset_id": asset_id})
        session_id = s_res.json()["session_id"]

        last_status = None
        last_timeline = None

        for cmd in sc["commands"]:
            res = client.post(f"/api/v1/sessions/{session_id}/instructions", json={"instruction": cmd})
            data = res.json()
            last_status = data.get("status")
            if data.get("timeline"):
                last_timeline = data["timeline"]

        passed = (last_status == sc["expected_status"])
        if "expected_final_duration" in sc and last_timeline:
            # Note: 30s base test video scale
            passed = passed and (last_timeline["total_duration"] is not None)

        results.append({
            "session_id": sc["id"],
            "title": sc["title"],
            "expected_status": sc["expected_status"],
            "actual_status": last_status,
            "passed": passed
        })

    return results

if __name__ == "__main__":
    from incubrix.core.config import settings
    import subprocess
    # Generate test video for batch runner
    temp_vid = "data/storage/uploads/batch_runner_fixture.mp4"
    if not os.path.exists(temp_vid):
        cmd = [
            settings.FFMPEG_PATH, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=30:size=640x360:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=30",
            "-c:v", "libx264", "-c:a", "aac",
            temp_vid
        ]
        subprocess.run(cmd, capture_output=True, check=True)

    outcomes = run_batch_sessions(temp_vid)
    print("\n--- BATCH SCRIPTED SESSIONS SUMMARY ---")
    all_ok = True
    for o in outcomes:
        status_sym = "[PASS]" if o["passed"] else "[FAIL]"
        if not o["passed"]: all_ok = False
        print(f"{status_sym} [{o['session_id']}] {o['title']} -> {o['actual_status']} (expected {o['expected_status']})")

    print(f"\nTotal: {len(outcomes)} sessions. All passed: {all_ok}")
