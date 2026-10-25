import pytest
import os
import hashlib
from incubrix.engine.timeline import Timeline, Segment
from incubrix.engine.operations import TimelineOperations
from incubrix.media.probe import MediaProbe
from incubrix.storage.backend import storage

def test_source_immutability_and_hash_preservation(test_video_path):
    # Compute initial hash of source video
    with open(test_video_path, "rb") as f:
        orig_hash = hashlib.sha256(f.read()).hexdigest()

    # Simulate operations and edits referencing this path
    t = Timeline(
        asset_id="test_immutable",
        segments=[Segment(id="s1", asset_id="test_immutable", source_start=0.0, source_end=10.0, speed=1.0)]
    )
    t1 = TimelineOperations.cut_range(t, 0.0, 4.0)
    t2 = TimelineOperations.change_speed(t1, 1.5)

    # Re-verify source file on disk
    with open(test_video_path, "rb") as f:
        after_hash = hashlib.sha256(f.read()).hexdigest()

    assert orig_hash == after_hash, "Original source file bytes were mutated!"

def test_timeline_hash_determinism():
    seg_a = Segment(id="s1", asset_id="vid_1", source_start=0.0, source_end=10.0, speed=1.0)
    seg_b = Segment(id="s2", asset_id="vid_1", source_start=10.0, source_end=20.0, speed=1.0)

    t1 = Timeline(asset_id="vid_1", segments=[seg_a, seg_b])
    t2 = Timeline(asset_id="vid_1", segments=[seg_a.model_copy(), seg_b.model_copy()])

    assert t1.canonical_hash() == t2.canonical_hash()

def test_media_probe_properties(test_video_path):
    info = MediaProbe.probe_file(test_video_path)
    assert info["duration"] == 10.0
    assert info["width"] == 640
    assert info["height"] == 360
    assert info["video_codec"] == "h264"
    assert info["audio_codec"] == "aac"
    assert info["channels"] == 1
