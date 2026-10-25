import uuid
import copy
from typing import List, Tuple, Optional
from incubrix.engine.timeline import Timeline, Segment, Caption, AudioEffect
from incubrix.core.errors import InvalidOperationError

class TimelineOperations:
    """
    Pure, deterministic mutations on Timeline models.
    Every operation validates bounds and returns a new updated Timeline instance.
    """

    @classmethod
    def cut_range(cls, timeline: Timeline, cut_start: float, cut_end: float) -> Timeline:
        """
        Cuts out the interval [cut_start, cut_end] in timeline output coordinates.
        Splits segments that intersect the cut interval and eliminates the cut portion.
        """
        if cut_start < 0:
            raise InvalidOperationError(f"Cut start time {cut_start} cannot be negative.")
        if cut_start >= cut_end:
            raise InvalidOperationError(f"Cut start time {cut_start} must be strictly less than cut end time {cut_end}.")
        if cut_start >= timeline.total_duration:
            raise InvalidOperationError(f"Cut start time {cut_start} is beyond the total duration {timeline.total_duration}.")

        new_segments: List[Segment] = []
        current_time = 0.0

        for seg in timeline.segments:
            seg_dur = seg.duration
            seg_start = current_time
            seg_end = current_time + seg_dur

            # Case 1: Segment is completely before cut range
            if seg_end <= cut_start:
                new_segments.append(seg.model_copy(deep=True))
            # Case 2: Segment is completely after cut range
            elif seg_start >= cut_end:
                new_segments.append(seg.model_copy(deep=True))
            # Case 3: Cut intersects or covers this segment
            else:
                # Part before the cut
                if seg_start < cut_start:
                    keep_dur = cut_start - seg_start
                    keep_source_dur = keep_dur * seg.speed
                    pre_seg = seg.model_copy(deep=True)
                    pre_seg.id = str(uuid.uuid4())[:8]
                    pre_seg.source_end = pre_seg.source_start + keep_source_dur
                    new_segments.append(pre_seg)

                # Part after the cut
                if seg_end > cut_end:
                    skip_dur = cut_end - seg_start
                    skip_source_dur = skip_dur * seg.speed
                    post_seg = seg.model_copy(deep=True)
                    post_seg.id = str(uuid.uuid4())[:8]
                    post_seg.source_start = seg.source_start + skip_source_dur
                    new_segments.append(post_seg)

            current_time = seg_end

        if not new_segments:
            raise InvalidOperationError("The cut operation would result in an empty timeline, which is not permitted.")

        return Timeline(asset_id=timeline.asset_id, segments=new_segments)

    @classmethod
    def cut_from_end(cls, timeline: Timeline, duration: float) -> Timeline:
        if duration <= 0:
            raise InvalidOperationError(f"Cut duration {duration} must be positive.")
        if duration >= timeline.total_duration:
            raise InvalidOperationError(f"Cannot cut {duration}s from end of a {timeline.total_duration}s video.")
        cut_start = timeline.total_duration - duration
        return cls.cut_range(timeline, cut_start, timeline.total_duration)

    @classmethod
    def change_speed(cls, timeline: Timeline, speed: float) -> Timeline:
        if speed <= 0 or speed > 10.0:
            raise InvalidOperationError(f"Speed factor {speed} is invalid. Supported range: 0.1x to 10.0x.")
        new_segments = []
        for s in timeline.segments:
            seg = s.model_copy(deep=True)
            seg.speed = round(seg.speed * speed, 4)
            new_segments.append(seg)
        return Timeline(asset_id=timeline.asset_id, segments=new_segments)

    @classmethod
    def change_speed_range(cls, timeline: Timeline, start_time: float, end_time: float, speed: float) -> Timeline:
        if speed <= 0 or speed > 10.0:
            raise InvalidOperationError(f"Speed factor {speed} is invalid. Supported range: 0.1x to 10.0x.")
        if start_time < 0 or start_time >= end_time or start_time >= timeline.total_duration:
            raise InvalidOperationError(f"Invalid time range [{start_time}, {end_time}].")

        new_segments: List[Segment] = []
        current_time = 0.0

        for seg in timeline.segments:
            seg_dur = seg.duration
            seg_start = current_time
            seg_end = current_time + seg_dur

            # Completely before or after
            if seg_end <= start_time or seg_start >= end_time:
                new_segments.append(seg.model_copy(deep=True))
            else:
                # Overlaps range
                # Split prefix if seg_start < start_time
                curr_s_start = seg.source_start
                if seg_start < start_time:
                    pre_dur = start_time - seg_start
                    pre_s_dur = pre_dur * seg.speed
                    pre_seg = seg.model_copy(deep=True)
                    pre_seg.id = str(uuid.uuid4())[:8]
                    pre_seg.source_end = curr_s_start + pre_s_dur
                    new_segments.append(pre_seg)
                    curr_s_start += pre_s_dur

                # Middle portion (speed adjusted)
                mid_t_start = max(seg_start, start_time)
                mid_t_end = min(seg_end, end_time)
                mid_dur = mid_t_end - mid_t_start
                mid_s_dur = mid_dur * seg.speed
                mid_seg = seg.model_copy(deep=True)
                mid_seg.id = str(uuid.uuid4())[:8]
                mid_seg.source_start = curr_s_start
                mid_seg.source_end = curr_s_start + mid_s_dur
                mid_seg.speed = round(seg.speed * speed, 4)
                new_segments.append(mid_seg)
                curr_s_start += mid_s_dur

                # Post portion if seg_end > end_time
                if seg_end > end_time:
                    post_seg = seg.model_copy(deep=True)
                    post_seg.id = str(uuid.uuid4())[:8]
                    post_seg.source_start = curr_s_start
                    post_seg.source_end = seg.source_end
                    new_segments.append(post_seg)

            current_time = seg_end

        return Timeline(asset_id=timeline.asset_id, segments=new_segments)

    @classmethod
    def move_segment(cls, timeline: Timeline, source: str, destination: str) -> Timeline:
        if len(timeline.segments) < 2:
            raise InvalidOperationError("Timeline needs at least two segments to reorder.")
        segs = [s.model_copy(deep=True) for s in timeline.segments]
        if source == "last" and destination == "first":
            target = segs.pop()
            segs.insert(0, target)
        else:
            raise InvalidOperationError(f"Unsupported move operation from '{source}' to '{destination}'.")
        return Timeline(asset_id=timeline.asset_id, segments=segs)

    @classmethod
    def swap_segments(cls, timeline: Timeline, idx_a: int, idx_b: int) -> Timeline:
        if len(timeline.segments) < 2:
            raise InvalidOperationError("Timeline needs at least two segments to swap.")
        if idx_a >= len(timeline.segments) or idx_b >= len(timeline.segments):
            raise InvalidOperationError(f"Segment indices ({idx_a}, {idx_b}) are out of range for {len(timeline.segments)} segments.")
        segs = [s.model_copy(deep=True) for s in timeline.segments]
        segs[idx_a], segs[idx_b] = segs[idx_b], segs[idx_a]
        return Timeline(asset_id=timeline.asset_id, segments=segs)

    @classmethod
    def reverse_segments(cls, timeline: Timeline) -> Timeline:
        if len(timeline.segments) < 2:
            raise InvalidOperationError("Timeline needs at least two segments to reverse.")
        segs = [s.model_copy(deep=True) for s in reversed(timeline.segments)]
        return Timeline(asset_id=timeline.asset_id, segments=segs)

    @classmethod
    def add_caption(cls, timeline: Timeline, text: str, start_time: float, duration: float = 4.0, color: str = "#ffffff") -> Timeline:
        if not timeline.segments:
            raise InvalidOperationError("Cannot add caption to an empty timeline.")
        if start_time < 0:
            start_time = max(0.0, timeline.total_duration - duration)
        end_time = min(timeline.total_duration, start_time + duration)

        new_segments = [s.model_copy(deep=True) for s in timeline.segments]
        caption_id = str(uuid.uuid4())[:8]
        new_caption = Caption(
            id=caption_id,
            text=text,
            start_time=start_time,
            end_time=end_time,
            color=color,
        )

        # Attach caption to segments that overlap with [start_time, end_time]
        cur_t = 0.0
        for seg in new_segments:
            seg_start = cur_t
            seg_end = cur_t + seg.duration
            if not (seg_end <= start_time or seg_start >= end_time):
                seg.captions.append(new_caption)
            cur_t = seg_end

        return Timeline(asset_id=timeline.asset_id, segments=new_segments)

    @classmethod
    def change_caption_color(cls, timeline: Timeline, color: str) -> Timeline:
        found = False
        new_segments = [s.model_copy(deep=True) for s in timeline.segments]
        for seg in new_segments:
            for cap in seg.captions:
                cap.color = color
                found = True
        if not found:
            raise InvalidOperationError("No captions found in timeline to change color.")
        return Timeline(asset_id=timeline.asset_id, segments=new_segments)

    @classmethod
    def remove_captions(cls, timeline: Timeline) -> Timeline:
        new_segments = [s.model_copy(deep=True) for s in timeline.segments]
        found = False
        for seg in new_segments:
            if seg.captions:
                found = True
                seg.captions.clear()
        if not found:
            raise InvalidOperationError("No captions to remove.")
        return Timeline(asset_id=timeline.asset_id, segments=new_segments)

    @classmethod
    def restore_intro(cls, timeline: Timeline, original_duration: float, intro_seconds: float = 5.0) -> Timeline:
        """
        Restores the intro region [0, intro_seconds] of the original asset at the beginning of the timeline,
        while preserving all existing subsequent segments and edits.
        """
        # Check if the intro is already present
        if timeline.segments and timeline.segments[0].source_start == 0.0:
            raise InvalidOperationError("The intro region [0s] is already present at the beginning of the timeline.")
        
        intro_seg = Segment(
            id=str(uuid.uuid4())[:8],
            asset_id=timeline.asset_id,
            source_start=0.0,
            source_end=min(original_duration, intro_seconds),
            speed=1.0,
            label="Restored Intro"
        )
        new_segments = [intro_seg] + [s.model_copy(deep=True) for s in timeline.segments]
        return Timeline(asset_id=timeline.asset_id, segments=new_segments)
