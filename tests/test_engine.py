import pytest
from incubrix.engine.timeline import Timeline, Segment
from incubrix.engine.operations import TimelineOperations
from incubrix.core.errors import InvalidOperationError

def create_sample_timeline(duration: float = 30.0) -> Timeline:
    seg = Segment(
        id="seg1",
        asset_id="asset_123",
        source_start=0.0,
        source_end=duration,
        speed=1.0,
        label="Full"
    )
    return Timeline(asset_id="asset_123", segments=[seg])

def test_timeline_canonical_hash():
    t1 = create_sample_timeline(30.0)
    t2 = create_sample_timeline(30.0)
    assert t1.canonical_hash() == t2.canonical_hash()

def test_cut_first_5_seconds():
    t = create_sample_timeline(30.0)
    res = TimelineOperations.cut_range(t, 0.0, 5.0)
    assert len(res.segments) == 1
    assert res.total_duration == 25.0
    assert res.segments[0].source_start == 5.0
    assert res.segments[0].source_end == 30.0

def test_cut_middle_seconds():
    t = create_sample_timeline(30.0)
    res = TimelineOperations.cut_range(t, 10.0, 15.0)
    assert len(res.segments) == 2
    assert res.total_duration == 25.0
    assert res.segments[0].source_start == 0.0
    assert res.segments[0].source_end == 10.0
    assert res.segments[1].source_start == 15.0
    assert res.segments[1].source_end == 30.0

def test_cut_from_end():
    t = create_sample_timeline(30.0)
    res = TimelineOperations.cut_from_end(t, 3.0)
    assert res.total_duration == 27.0
    assert res.segments[0].source_end == 27.0

def test_invalid_cuts():
    t = create_sample_timeline(30.0)
    with pytest.raises(InvalidOperationError):
        TimelineOperations.cut_range(t, -2.0, 5.0)
    with pytest.raises(InvalidOperationError):
        TimelineOperations.cut_range(t, 15.0, 10.0)
    with pytest.raises(InvalidOperationError):
        TimelineOperations.cut_range(t, 0.0, 30.0)  # Empty timeline forbidden

def test_change_speed():
    t = create_sample_timeline(30.0)
    res = TimelineOperations.change_speed(t, 2.0)
    assert res.total_duration == 15.0
    assert res.segments[0].speed == 2.0

def test_reordering():
    t = create_sample_timeline(30.0)
    t_split = TimelineOperations.cut_range(t, 10.0, 15.0)
    assert len(t_split.segments) == 2
    swapped = TimelineOperations.swap_segments(t_split, 0, 1)
    assert swapped.segments[0].source_start == 15.0
    assert swapped.segments[1].source_start == 0.0

def test_caption_operations():
    t = create_sample_timeline(30.0)
    t_cap = TimelineOperations.add_caption(t, "Dance Practice", 0.0, 4.0)
    assert len(t_cap.segments[0].captions) == 1
    assert t_cap.segments[0].captions[0].text == "Dance Practice"

    t_color = TimelineOperations.change_caption_color(t_cap, "red")
    assert t_color.segments[0].captions[0].color == "red"

    t_rem = TimelineOperations.remove_captions(t_color)
    assert len(t_rem.segments[0].captions) == 0

def test_restore_intro():
    t = create_sample_timeline(30.0)
    t_cut = TimelineOperations.cut_range(t, 0.0, 5.0)
    assert t_cut.segments[0].source_start == 5.0

    t_rest = TimelineOperations.restore_intro(t_cut, 30.0, 5.0)
    assert len(t_rest.segments) == 2
    assert t_rest.segments[0].source_start == 0.0
    assert t_rest.segments[0].source_end == 5.0
    assert t_rest.segments[1].source_start == 5.0
