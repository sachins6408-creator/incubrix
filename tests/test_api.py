import pytest
from fastapi.testclient import TestClient
from incubrix.api.v1.app import app
from incubrix.storage.backend import storage

client = TestClient(app)

def test_health_and_ready():
    r1 = client.get("/health")
    assert r1.status_code == 200
    assert r1.json()["status"] == "UP"

    r2 = client.get("/ready")
    assert r2.status_code == 200
    assert r2.json()["checks"]["ffmpeg"] is True
    assert r2.json()["checks"]["ffprobe"] is True

def test_upload_and_stream(test_video_path):
    with open(test_video_path, "rb") as f:
        res = client.post("/api/v1/media/upload", files={"file": ("test.mp4", f, "video/mp4")})
    assert res.status_code == 200
    data = res.json()
    assert "asset_id" in data
    assert "sha256" in data
    assert data["duration"] == 10.0

    asset_id = data["asset_id"]

    # Stream video (200 full stream)
    stream_res = client.get(f"/api/v1/media/{asset_id}/stream")
    assert stream_res.status_code == 200
    assert stream_res.headers["content-type"] == "video/mp4"

    # Stream partial range (206 Partial Content)
    range_res = client.get(f"/api/v1/media/{asset_id}/stream", headers={"Range": "bytes=0-1023"})
    assert range_res.status_code == 206
    assert range_res.headers["content-length"] == "1024"
    assert "bytes 0-1023/" in range_res.headers["content-range"]

def test_session_lifecycle_and_instructions(test_video_path):
    with open(test_video_path, "rb") as f:
        upload_res = client.post("/api/v1/media/upload", files={"file": ("test.mp4", f, "video/mp4")})
    asset_id = upload_res.json()["asset_id"]

    # Create session bound to asset_id
    sess_res = client.post("/api/v1/sessions", json={"asset_id": asset_id})
    assert sess_res.status_code == 201
    sess_data = sess_res.json()
    session_id = sess_data["session_id"]
    assert sess_data["timeline"]["total_duration"] == 10.0

    # 1. Apply Valid Edit: Cut first 2s
    inst1 = client.post(f"/api/v1/sessions/{session_id}/instructions", json={"instruction": "Cut the first 2 seconds."})
    assert inst1.status_code == 200
    d1 = inst1.json()
    assert d1["status"] == "APPLIED"
    assert d1["timeline"]["total_duration"] == 8.0

    # 2. Ambiguous command on dance/video without transcript grounded occurrences -> REJECTED
    inst2 = client.post(f"/api/v1/sessions/{session_id}/instructions", json={"instruction": "Remove the pricing section."})
    assert inst2.status_code == 200
    d2 = inst2.json()
    assert d2["status"] == "REJECTED"
    assert d2["error_code"] == "UNGROUNDED_REFERENCE"

    # 3. Invalid command out of range -> REJECTED
    inst3 = client.post(f"/api/v1/sessions/{session_id}/instructions", json={"instruction": "Cut from 20 to 30 seconds."})
    assert inst3.status_code == 200
    d3 = inst3.json()
    assert d3["status"] == "REJECTED"
    assert d3["error_code"] == "INVALID_OPERATION"

    # 4. Undo and Redo endpoints
    undo_res = client.post(f"/api/v1/sessions/{session_id}/undo")
    assert undo_res.status_code == 200
    assert undo_res.json()["timeline"]["total_duration"] == 10.0

    redo_res = client.post(f"/api/v1/sessions/{session_id}/redo")
    assert redo_res.status_code == 200
    assert redo_res.json()["timeline"]["total_duration"] == 8.0
