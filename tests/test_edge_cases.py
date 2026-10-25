import pytest
import os
from fastapi.testclient import TestClient
from incubrix.api.v1.app import app

client = TestClient(app)

def test_stream_404_missing_asset():
    res = client.get("/api/v1/media/non_existent_asset_id/stream")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "ASSET_NOT_FOUND"

def test_session_404_missing_session():
    res = client.get("/api/v1/sessions/non_existent_session_id")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "SESSION_NOT_FOUND"

def test_job_404_missing_job():
    res = client.get("/api/v1/jobs/non_existent_job_id")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "JOB_NOT_FOUND"

def test_create_session_with_invalid_asset():
    res = client.post("/api/v1/sessions", json={"asset_id": "fake_asset_12345"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "ASSET_NOT_FOUND"

def test_upload_invalid_file_extension(tmp_path):
    text_file = tmp_path / "fake.txt"
    text_file.write_text("not a video")
    with open(text_file, "rb") as f:
        res = client.post("/api/v1/media/upload", files={"file": ("fake.txt", f, "text/plain")})
    assert res.status_code == 400
    assert res.json()["error"]["code"] in ("INVALID_MEDIA", "INVALID_EXTENSION")
