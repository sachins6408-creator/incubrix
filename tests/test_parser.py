import pytest
from incubrix.nlp.parser import InstructionParser

def test_parse_cuts():
    p1 = InstructionParser.parse("Cut the first 5 seconds.")
    assert p1["type"] == "CUT_RANGE"
    assert p1["start"] == 0.0
    assert p1["end"] == 5.0

    p2 = InstructionParser.parse("Remove the first five seconds")
    assert p2["type"] == "CUT_RANGE"
    assert p2["start"] == 0.0
    assert p2["end"] == 5.0

    p3 = InstructionParser.parse("Trim the beginning by 5 seconds")
    assert p3["type"] == "CUT_RANGE"
    assert p3["start"] == 0.0
    assert p3["end"] == 5.0

    p4 = InstructionParser.parse("Cut from 10 to 15 seconds")
    assert p4["type"] == "CUT_RANGE"
    assert p4["start"] == 10.0
    assert p4["end"] == 15.0

    p5 = InstructionParser.parse("Remove the segment between 10 and 15 seconds")
    assert p5["type"] == "CUT_RANGE"
    assert p5["start"] == 10.0
    assert p5["end"] == 15.0

    p6 = InstructionParser.parse("Remove the last 3 seconds")
    assert p6["type"] == "CUT_FROM_END"
    assert p6["duration"] == 3.0

def test_parse_speed():
    p1 = InstructionParser.parse("Speed up the whole video by 2x")
    assert p1["type"] == "CHANGE_SPEED"
    assert p1["speed"] == 2.0

    p2 = InstructionParser.parse("Slow down the video to half speed")
    assert p2["type"] == "CHANGE_SPEED"
    assert p2["speed"] == 0.5

    p3 = InstructionParser.parse("Set playback speed to 1.5x")
    assert p3["type"] == "CHANGE_SPEED"
    assert p3["speed"] == 1.5

    p4 = InstructionParser.parse("Speed up the video from 5 to 10 seconds by 2x")
    assert p4["type"] == "CHANGE_SPEED_RANGE"
    assert p4["start"] == 5.0
    assert p4["end"] == 10.0
    assert p4["speed"] == 2.0

def test_parse_reordering():
    p1 = InstructionParser.parse("Move the last segment to the beginning")
    assert p1["type"] == "MOVE_SEGMENT"

    p2 = InstructionParser.parse("Swap the first and second segments")
    assert p2["type"] == "SWAP_SEGMENTS"

    p3 = InstructionParser.parse("Reverse the order of these two segments")
    assert p3["type"] == "REVERSE_SEGMENTS"

def test_parse_captions():
    p1 = InstructionParser.parse("Add a caption saying Dance Practice at the beginning")
    assert p1["type"] == "ADD_CAPTION"
    assert p1["text"] == "Dance Practice"
    assert p1["start_time"] == 0.0

    p2 = InstructionParser.parse("Add the caption Welcome at 3 seconds")
    assert p2["type"] == "ADD_CAPTION"
    assert p2["text"] == "Welcome"
    assert p2["start_time"] == 3.0

    p3 = InstructionParser.parse("Change the caption color to red")
    assert p3["type"] == "CHANGE_CAPTION_COLOR"
    assert p3["color"] == "red"

    p4 = InstructionParser.parse("Remove the caption at the beginning")
    assert p4["type"] == "REMOVE_CAPTION"

def test_parse_clarification_and_restoration():
    p1 = InstructionParser.parse("Remove the third occurrence")
    assert p1["type"] == "CLARIFICATION_SELECT"
    assert p1["target_index"] == 3

    p2 = InstructionParser.parse("Remove occurrence 1")
    assert p2["type"] == "CLARIFICATION_SELECT"
    assert p2["target_index"] == 1

    p3 = InstructionParser.parse("Remove all occurrences")
    assert p3["type"] == "CLARIFICATION_SELECT_ALL"

    p4 = InstructionParser.parse("Restore the intro")
    assert p4["type"] == "RESTORE_SECTION"
    assert p4["target"] == "intro"

def test_parse_unsupported():
    p1 = InstructionParser.parse("Fly to the moon with this video")
    assert p1["type"] == "UNSUPPORTED"
