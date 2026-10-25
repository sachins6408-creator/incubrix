import pytest
import uuid
from incubrix.engine.timeline import Timeline, Segment
from incubrix.engine.operations import TimelineOperations
from incubrix.engine.history import HistoryManager
from incubrix.storage.backend import storage
from incubrix.core.errors import InvalidOperationError

def test_atomic_undo_and_redo():
    session_id = f"test_session_{uuid.uuid4()}"
    asset_id = "test_asset"

    # 1. Initial Timeline
    seg = Segment(id="seg0", asset_id=asset_id, source_start=0.0, source_end=30.0, speed=1.0)
    t0 = Timeline(asset_id=asset_id, segments=[seg])
    storage.save_session(session_id, asset_id, t0.canonical_json())

    # 2. Apply Cut 1 (first 5 seconds)
    t1 = TimelineOperations.cut_range(t0, 0.0, 5.0)
    storage.save_session(session_id, asset_id, t1.canonical_json())
    storage.record_operation(
        session_id=session_id,
        operation_id="op1",
        operation_type="CUT_RANGE",
        raw_instruction="Cut first 5s",
        payload={"start": 0.0, "end": 5.0},
        timeline_before_json=t0.canonical_json(),
        timeline_after_json=t1.canonical_json()
    )
    assert t1.total_duration == 25.0

    # 3. Apply Speed change (2x)
    t2 = TimelineOperations.change_speed(t1, 2.0)
    storage.save_session(session_id, asset_id, t2.canonical_json())
    storage.record_operation(
        session_id=session_id,
        operation_id="op2",
        operation_type="CHANGE_SPEED",
        raw_instruction="Speed 2x",
        payload={"speed": 2.0},
        timeline_before_json=t1.canonical_json(),
        timeline_after_json=t2.canonical_json()
    )
    assert t2.total_duration == 12.5

    # 4. Undo op2 -> Should revert to t1
    reverted_t1, op = HistoryManager.undo(session_id)
    assert reverted_t1.total_duration == 25.0
    assert reverted_t1.canonical_hash() == t1.canonical_hash()

    # 5. Undo op1 -> Should revert to t0
    reverted_t0, op = HistoryManager.undo(session_id)
    assert reverted_t0.total_duration == 30.0
    assert reverted_t0.canonical_hash() == t0.canonical_hash()

    # 6. Redo op1 -> Should re-apply t1
    redone_t1, op = HistoryManager.redo(session_id)
    assert redone_t1.total_duration == 25.0
    assert redone_t1.canonical_hash() == t1.canonical_hash()

    # 7. Redo-stack invalidation: commit new edit t3
    t3 = TimelineOperations.cut_from_end(redone_t1, 5.0)
    storage.save_session(session_id, asset_id, t3.canonical_json())
    storage.record_operation(
        session_id=session_id,
        operation_id="op3",
        operation_type="CUT_FROM_END",
        raw_instruction="Cut last 5s",
        payload={"duration": 5.0},
        timeline_before_json=redone_t1.canonical_json(),
        timeline_after_json=t3.canonical_json()
    )

    # Now redo should fail because redo stack was invalidated
    with pytest.raises(InvalidOperationError):
        HistoryManager.redo(session_id)
