import pytest
from incubrix.engine.timeline import Timeline, Segment
from incubrix.engine.operations import TimelineOperations
from incubrix.core.errors import InvalidOperationError

def create_base_timeline(duration: float = 30.0) -> Timeline:
    return Timeline(
        asset_id="test_asset",
        segments=[Segment(id="seg0", asset_id="test_asset", source_start=0.0, source_end=duration, speed=1.0)]
    )

def test_reject_negative_start():
    t = create_base_timeline()
    with pytest.raises(InvalidOperationError):
        TimelineOperations.cut_range(t, -5.0, 5.0)

def test_reject_start_greater_than_end():
    t = create_base_timeline()
    with pytest.raises(InvalidOperationError):
        TimelineOperations.cut_range(t, 10.0, 5.0)

def test_reject_equal_start_end():
    t = create_base_timeline()
    with pytest.raises(InvalidOperationError):
        TimelineOperations.cut_range(t, 5.0, 5.0)

def test_reject_out_of_range_cut():
    t = create_base_timeline(20.0)
    with pytest.raises(InvalidOperationError):
        TimelineOperations.cut_range(t, 25.0, 30.0)

def test_reject_invalid_speed_factors():
    t = create_base_timeline()
    with pytest.raises(InvalidOperationError):
        TimelineOperations.change_speed(t, 0.0)
    with pytest.raises(InvalidOperationError):
        TimelineOperations.change_speed(t, -1.5)
    with pytest.raises(InvalidOperationError):
        TimelineOperations.change_speed(t, 25.0)  # > 10.0 limit

def test_reject_empty_timeline_creation():
    t = create_base_timeline(30.0)
    with pytest.raises(InvalidOperationError):
        TimelineOperations.cut_range(t, 0.0, 30.0)

def test_multi_cut_preserves_unrelated_regions():
    t = create_base_timeline(30.0)
    # Cut 0 to 5
    t1 = TimelineOperations.cut_range(t, 0.0, 5.0)
    # Cut 10 to 15 in remaining timeline (corresponds to original 15 to 20)
    t2 = TimelineOperations.cut_range(t1, 10.0, 15.0)
    assert len(t2.segments) == 2
    assert t2.total_duration == 20.0
    assert t2.segments[0].source_start == 5.0
    assert t2.segments[0].source_end == 15.0
    assert t2.segments[1].source_start == 20.0
    assert t2.segments[1].source_end == 30.0

def test_speed_range_preserves_duration_math():
    t = create_base_timeline(30.0)
    # Speed up 0 to 10s by 2x -> takes 5s output time. Remaining 20s takes 20s output time. Total 25s
    t_speed = TimelineOperations.change_speed_range(t, 0.0, 10.0, 2.0)
    assert round(t_speed.total_duration, 2) == 25.0
    assert t_speed.segments[0].speed == 2.0
    assert t_speed.segments[1].speed == 1.0

def test_reorder_reversal_duration_invariance():
    t = create_base_timeline(30.0)
    t_split = TimelineOperations.cut_range(t, 10.0, 12.0)
    d_before = t_split.total_duration
    t_rev = TimelineOperations.reverse_segments(t_split)
    assert t_rev.total_duration == d_before
    assert t_rev.segments[0].source_start == 12.0
    assert t_rev.segments[1].source_start == 0.0

def test_restore_intro_idempotency_check():
    t = create_base_timeline(30.0)
    # Intro is already at 0.0
    with pytest.raises(InvalidOperationError):
        TimelineOperations.restore_intro(t, 30.0, 5.0)
