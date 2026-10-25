import pytest
import os
from fastapi.testclient import TestClient
from incubrix.api.v1.app import app

client = TestClient(app)

def test_upload_valid_mp4(test_video_path):
    """Test upload of a standard valid .mp4 file."""
    with open(test_video_path, "rb") as f:
        res = client.post("/api/v1/media/upload", files={"file": ("sample_dance.mp4", f, "video/mp4")})
    assert res.status_code == 200
    data = res.json()
    assert "asset_id" in data
    assert data["filename"] == "sample_dance.mp4"
    assert data["duration"] > 0
    assert data["width"] is not None
    assert data["height"] is not None
    assert data["video_codec"] is not None
    assert "stream_url" in data

def test_upload_valid_video_without_extension(test_video_path):
    """
    Test upload of a valid video file whose filename has NO extension (e.g. 'dance').
    Ensures the backend verifies media content using FFprobe and does not reject it.
    """
    with open(test_video_path, "rb") as f:
        # Note the filename is 'dance' with no .mp4 extension
        res = client.post("/api/v1/media/upload", files={"file": ("dance", f, "application/octet-stream")})
    assert res.status_code == 200
    data = res.json()
    assert "asset_id" in data
    assert data["filename"] == "dance"
    assert data["duration"] == 10.0
    assert data["video_codec"] == "h264"
    assert "stream_url" in data

    # Verify that stream endpoint serves the asset successfully
    stream_res = client.get(data["stream_url"])
    assert stream_res.status_code == 200

def test_upload_unsupported_text_file(tmp_path):
    """Test that a plain text file without or with invalid extension is rejected as INVALID_MEDIA or INVALID_EXTENSION."""
    txt_file = tmp_path / "readme.txt"
    txt_file.write_text("This is an uncompressed text document, not a video.")
    with open(txt_file, "rb") as f:
        res = client.post("/api/v1/media/upload", files={"file": ("readme.txt", f, "text/plain")})
    assert res.status_code == 400
    err = res.json()["error"]
    assert err["code"] in ("INVALID_EXTENSION", "INVALID_MEDIA")

def test_upload_and_session_creation_timeline_segment_duration(test_video_path):
    """
    Regression test verifying that after upload, session creation initializes timeline
    segments containing valid numeric duration fields aligned with frontend expectations.
    """
    with open(test_video_path, "rb") as f:
        upload_res = client.post("/api/v1/media/upload", files={"file": ("test_session.mp4", f, "video/mp4")})
    assert upload_res.status_code == 200
    asset_id = upload_res.json()["asset_id"]

    # Create session
    sess_res = client.post("/api/v1/sessions", json={"asset_id": asset_id})
    assert sess_res.status_code == 201
    sess_data = sess_res.json()
    timeline = sess_data["timeline"]
    assert "segments" in timeline
    assert len(timeline["segments"]) > 0

    seg = timeline["segments"][0]
    # Check that segment duration is an explicit number and can be formatted with toFixed
    assert "duration" in seg
    assert isinstance(seg["duration"], (int, float))
    assert seg["duration"] > 0
    # Simulate frontend .toFixed(2) call
    formatted_duration = f"{seg['duration']:.2f}"
    assert float(formatted_duration) == round(seg["duration"], 2)

def test_upload_with_missing_optional_metadata(test_video_path, monkeypatch):
    """
    Regression test ensuring that when optional metadata fields (e.g. fps, bit_rate, audio)
    are None/missing from ffprobe, the upload still succeeds, does not invent fake values,
    and returns a clean schema handled safely.
    """
    from incubrix.media.probe import MediaProbe

    original_probe = MediaProbe.probe_file

    def mock_probe_file(file_path):
        info = original_probe(file_path)
        # Simulate video file with missing audio, fps, and bitrate metadata
        info["fps"] = None
        info["bit_rate"] = None
        info["audio_codec"] = None
        info["channels"] = None
        info["sample_rate"] = None
        info["has_audio"] = False
        return info

    monkeypatch.setattr(MediaProbe, "probe_file", mock_probe_file)

    with open(test_video_path, "rb") as f:
        res = client.post("/api/v1/media/upload", files={"file": ("video_no_audio.mp4", f, "video/mp4")})

    assert res.status_code == 200
    data = res.json()
    assert data["fps"] is None
    assert data["audio_codec"] is None
    assert data["duration"] == 10.0
    assert data["video_codec"] == "h264"
    assert "stream_url" in data

