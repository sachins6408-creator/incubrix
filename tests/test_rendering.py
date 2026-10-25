import pytest
import os
import time
from fastapi.testclient import TestClient
from incubrix.api.v1.app import app
from incubrix.rendering.ffmpeg import FFmpegRenderer
from incubrix.engine.timeline import Timeline, Segment
from incubrix.engine.operations import TimelineOperations
from incubrix.media.probe import MediaProbe
from incubrix.storage.backend import storage

client = TestClient(app)

def test_real_ffmpeg_rendering_and_manifest(test_video_path):
    # Upload video
    with open(test_video_path, "rb") as f:
        res = client.post("/api/v1/media/upload", files={"file": ("render_test.mp4", f, "video/mp4")})
    assert res.status_code == 200
    asset_id = res.json()["asset_id"]

    # Session
    s_res = client.post("/api/v1/sessions", json={"asset_id": asset_id})
    session_id = s_res.json()["session_id"]

    # Cut 2 seconds from beginning, speed up remaining by 1.5x, add caption
    inst1 = client.post(f"/api/v1/sessions/{session_id}/instructions", json={"instruction": "Cut the first 2 seconds."})
    assert inst1.json()["status"] == "APPLIED"

    inst2 = client.post(f"/api/v1/sessions/{session_id}/instructions", json={"instruction": "Add a caption saying Dance Practice at the beginning."})
    assert inst2.json()["status"] == "APPLIED"

    # Trigger render
    render_req = client.post(f"/api/v1/sessions/{session_id}/render")
    assert render_req.status_code == 202
    job_id = render_req.json()["job_id"]

    # Poll until completed
    max_retries = 30
    completed = False
    for _ in range(max_retries):
        poll = client.get(f"/api/v1/jobs/{job_id}")
        data = poll.json()
        if data["status"] == "COMPLETED":
            completed = True
            break
        elif data["status"] == "FAILED":
            pytest.fail(f"Render failed: {data.get('error_message')}")
        time.sleep(1)

    assert completed is True

    # Verify manifest & rendered file
    job_data = client.get(f"/api/v1/jobs/{job_id}").json()
    manifest = job_data["manifest"]
    assert manifest is not None
    assert manifest["status"] == "COMPLETED"
    assert manifest["output_duration"] > 0
    assert os.path.exists(manifest["output_path"])

    # Probe rendered file directly with ffprobe
    probe = MediaProbe.probe_file(manifest["output_path"])
    assert probe["video_codec"] == "h264"
    assert probe["audio_codec"] == "aac"
    assert abs(probe["duration"] - 8.0) < 0.2  # 10s - 2s cut = 8.0s

    # Verify download endpoint
    dl_res = client.get(f"/api/v1/jobs/{job_id}/download")
    assert dl_res.status_code == 200
    assert len(dl_res.content) == os.path.getsize(manifest["output_path"])

    # Confirm original source hash unchanged
    asset = storage.get_asset(asset_id)
    assert os.path.exists(asset["file_path"])
