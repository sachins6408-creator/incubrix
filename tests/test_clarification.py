import pytest
import uuid
from incubrix.engine.timeline import Timeline, Segment
from incubrix.engine.operations import TimelineOperations
from incubrix.engine.resolver import InstructionResolver
from incubrix.storage.backend import storage

@pytest.fixture
def session_with_transcript():
    asset_id = f"asset_{uuid.uuid4()}"
    session_id = f"session_{uuid.uuid4()}"

    # Sample video with grounded transcript occurrences
    transcript_data = [
        {"start": 3.0, "end": 5.0, "text": "let us discuss the pricing section for plan A"},
        {"start": 12.0, "end": 14.5, "text": "and here is another pricing section overview"},
        {"start": 20.0, "end": 22.0, "text": "finally our enterprise pricing section"}
    ]

    asset_record = {
        "asset_id": asset_id,
        "filename": "demo_video.mp4",
        "file_path": "data/storage/uploads/demo.mp4",
        "sha256": "abcdef1234567890",
        "size_bytes": 1000000,
        "duration": 25.0,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "video_codec": "h264",
        "audio_codec": "aac",
        "channels": 2,
        "sample_rate": 44100,
        "metadata": {},
        "transcript": transcript_data
    }
    storage.save_asset(asset_record)

    seg = Segment(id="seg0", asset_id=asset_id, source_start=0.0, source_end=25.0, speed=1.0)
    t = Timeline(asset_id=asset_id, segments=[seg])
    storage.save_session(session_id, asset_id, t.canonical_json())

    return session_id, asset_id

def test_clarification_creation_on_ambiguous_phrase(session_with_transcript):
    session_id, asset_id = session_with_transcript
    res = InstructionResolver.resolve_instruction(session_id, "Remove the pricing section.")
    assert res.status == "NEEDS_CLARIFICATION"
    assert res.clarification is not None
    assert len(res.clarification.options) == 3
    assert res.clarification.options[0].index == 1
    assert res.clarification.options[1].index == 2
    assert res.clarification.options[2].index == 3

def test_clarification_resolve_specific_occurrence(session_with_transcript):
    session_id, asset_id = session_with_transcript
    # 1. Ambiguous command creates clarification
    r1 = InstructionResolver.resolve_instruction(session_id, "Remove the pricing section.")
    assert r1.status == "NEEDS_CLARIFICATION"

    # 2. Select third occurrence
    r2 = InstructionResolver.resolve_instruction(session_id, "Remove the third occurrence.")
    assert r2.status == "APPLIED"
    assert "occurrence 3" in r2.message.lower()

    # Verify clarification is cleared
    assert storage.get_clarification(session_id) is None

def test_clarification_resolve_all_occurrences(session_with_transcript):
    session_id, asset_id = session_with_transcript
    r1 = InstructionResolver.resolve_instruction(session_id, "Remove the pricing section.")
    assert r1.status == "NEEDS_CLARIFICATION"

    r2 = InstructionResolver.resolve_instruction(session_id, "Remove all occurrences.")
    assert r2.status == "APPLIED"
    assert "3 occurrences" in r2.message

def test_clarification_invalid_selection(session_with_transcript):
    session_id, asset_id = session_with_transcript
    InstructionResolver.resolve_instruction(session_id, "Remove the pricing section.")

    # Select non-existent occurrence 9
    r = InstructionResolver.resolve_instruction(session_id, "Remove occurrence 9.")
    assert r.status == "REJECTED"
    assert r.error_code == "INVALID_SELECTION"
