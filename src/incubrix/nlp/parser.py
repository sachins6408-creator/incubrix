import re
from typing import Optional, Dict, Any, List

WORD_TO_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "half": 0.5, "double": 2.0, "triple": 3.0
}

def parse_number_or_word(val: str) -> Optional[float]:
    val = val.strip().lower()
    if val in WORD_TO_NUM:
        return float(WORD_TO_NUM[val])
    try:
        return float(val)
    except ValueError:
        return None

def normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

class InstructionParser:
    """
    Deterministic grammar and validated structured extraction for natural-language video editing instructions.
    """

    @classmethod
    def parse(cls, raw_instruction: str) -> Dict[str, Any]:
        text = normalize_text(raw_instruction)
        lower = text.lower().rstrip(".!?,")

        # 0. Clarification follow-up selections
        # e.g., "remove occurrence 1", "remove the third occurrence", "choose option 2", "remove all occurrences", "all"
        all_match = re.search(r'\b(remove\s+all|all\s+occurrences|all|choose\s+all)\b', lower)
        if all_match:
            return {"type": "CLARIFICATION_SELECT_ALL", "raw": text}

        occ_match = re.search(r'\b(?:choose|select|remove|delete|pick)?\s*(?:the\s+)?(\d+|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+(?:occurrence|option|choice|candidate)\b', lower)
        if occ_match:
            idx = parse_number_or_word(occ_match.group(1))
            return {"type": "CLARIFICATION_SELECT", "target_index": int(idx) if idx else 1, "raw": text}

        occ_direct = re.search(r'\b(?:occurrence|option)\s*#?\s*(\d+)\b', lower)
        if occ_direct:
            return {"type": "CLARIFICATION_SELECT", "target_index": int(occ_direct.group(1)), "raw": text}

        # 1. Cuts and Removals
        # 1a: "Cut the first 5 seconds" / "Remove the first five seconds" / "Trim the beginning by 5 seconds"
        m = re.match(r'^(?:cut|remove|trim|delete)(?:\s+the)?\s+(?:first|initial|beginning)\s+(\d+(?:\.\d+)?|[a-zA-Z]+)\s*(?:s|sec|secs|seconds)?$', lower)
        if m:
            val = parse_number_or_word(m.group(1))
            if val is not None:
                return {"type": "CUT_RANGE", "start": 0.0, "end": val, "raw": text}

        # 1b: "Trim the beginning by 5 seconds" / "Trim 5 seconds from the beginning"
        m = re.match(r'^(?:trim|cut)(?:\s+the)?\s+beginning\s+by\s+(\d+(?:\.\d+)?|[a-zA-Z]+)\s*(?:s|sec|secs|seconds)?$', lower)
        if m:
            val = parse_number_or_word(m.group(1))
            if val is not None:
                return {"type": "CUT_RANGE", "start": 0.0, "end": val, "raw": text}

        # 1c: "Remove the last 3 seconds" / "Trim the end by 3 seconds"
        m = re.match(r'^(?:cut|remove|trim|delete)(?:\s+the)?\s+(?:last|ending|end)\s+(\d+(?:\.\d+)?|[a-zA-Z]+)\s*(?:s|sec|secs|seconds)?$', lower)
        if m:
            val = parse_number_or_word(m.group(1))
            if val is not None:
                return {"type": "CUT_FROM_END", "duration": val, "raw": text}

        # 1d: "Cut from 10 to 15 seconds" / "Remove the segment between 10 and 15 seconds"
        m = re.match(r'^(?:cut|remove|delete|trim)(?:\s+the)?(?:\s+segment)?\s+(?:from|between)\s+(\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds)?\s*(?:to|and)\s*(\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds)?$', lower)
        if m:
            start_val = float(m.group(1))
            end_val = float(m.group(2))
            return {"type": "CUT_RANGE", "start": start_val, "end": end_val, "raw": text}

        # 2. Speed Changes
        # 2a: "Speed up the whole video by 2x" / "Speed up video by 1.5x" / "Set playback speed to 1.5x"
        m = re.match(r'^(?:speed\s+up|accelerate)(?:\s+the)?(?:\s+whole)?(?:\s+video)?\s+by\s+(\d+(?:\.\d+)?|[a-zA-Z]+)(?:x)?$', lower)
        if m:
            val = parse_number_or_word(m.group(1))
            if val:
                return {"type": "CHANGE_SPEED", "speed": val, "scope": "all", "raw": text}

        m = re.match(r'^set\s+(?:playback\s+)?speed\s+to\s+(\d+(?:\.\d+)?|[a-zA-Z]+)(?:x)?$', lower)
        if m:
            val = parse_number_or_word(m.group(1))
            if val:
                return {"type": "CHANGE_SPEED", "speed": val, "scope": "all", "raw": text}

        # 2b: "Slow down the video to half speed" / "Slow down by 2x" / "Slow down the whole video by 0.5x"
        m = re.match(r'^(?:slow\s+down)(?:\s+the)?(?:\s+whole)?(?:\s+video)?\s+(?:to|by)\s+(?:half\s+speed|0\.5(?:x)?|half)$', lower)
        if m:
            return {"type": "CHANGE_SPEED", "speed": 0.5, "scope": "all", "raw": text}

        # 2c: "Speed up the video from 5 to 10 seconds by 2x"
        m = re.match(r'^(?:speed\s+up|slow\s+down)(?:\s+the)?(?:\s+video)?\s+(?:from|between)\s+(\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds)?\s*(?:to|and)\s*(\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds)?\s+by\s+(\d+(?:\.\d+)?|[a-zA-Z]+)(?:x)?$', lower)
        if m:
            start_val = float(m.group(1))
            end_val = float(m.group(2))
            val = parse_number_or_word(m.group(3)) or 1.0
            if "slow" in lower:
                val = 1.0 / val if val != 0 else 0.5
            return {"type": "CHANGE_SPEED_RANGE", "start": start_val, "end": end_val, "speed": val, "raw": text}

        # 3. Reordering Segments
        # 3a: "Move the last segment to the beginning"
        if re.search(r'\bmove\s+(?:the\s+)?last\s+segment\s+to\s+(?:the\s+)?(?:beginning|start)\b', lower):
            return {"type": "MOVE_SEGMENT", "source": "last", "destination": "first", "raw": text}

        # 3b: "Swap the first and second segments"
        if re.search(r'\bswap\s+(?:the\s+)?first\s+and\s+second\s+segments?\b', lower) or re.search(r'\bswap\s+(?:the\s+)?(?:segment\s+1|segments\s+1)\s+and\s+(?:segment\s+2|2)\b', lower):
            return {"type": "SWAP_SEGMENTS", "index_a": 0, "index_b": 1, "raw": text}

        # 3c: "Reverse the order of these two segments" / "Reverse segments"
        if re.search(r'\breverse\s+(?:the\s+order\s+of\s+)?(?:these\s+two\s+|all\s+)?segments?\b', lower):
            return {"type": "REVERSE_SEGMENTS", "raw": text}

        # 4. Captions
        # 4a: "Add a caption saying Dance Practice at the beginning" / "Add the caption Welcome at 3 seconds"
        m = re.search(r'add\s+(?:a|the)?\s*caption\s*(?:saying|reading|text)?\s*[\'"]?([^\'"]+?)[\'"]?\s+at\s+(?:the\s+)?(beginning|start|end|\d+(?:\.\d+)?\s*(?:s|sec|secs|seconds)?)', text, re.IGNORECASE)
        if m:
            cap_text = m.group(1).strip()
            loc_str = m.group(2).strip().lower()
            if loc_str in ("beginning", "start"):
                t_start = 0.0
            elif loc_str == "end":
                t_start = -1.0 # signal to anchor to timeline end
            else:
                num_m = re.match(r'(\d+(?:\.\d+)?)', loc_str)
                t_start = float(num_m.group(1)) if num_m else 0.0
            return {"type": "ADD_CAPTION", "text": cap_text, "start_time": t_start, "duration": 4.0, "raw": text}

        # 4b: "Change the caption color to red"
        m = re.search(r'change\s+(?:the\s+)?caption\s+color\s+to\s+([a-zA-Z#0-9]+)', lower)
        if m:
            return {"type": "CHANGE_CAPTION_COLOR", "color": m.group(1), "raw": text}

        # 4c: "Remove the caption at the beginning" / "Remove caption"
        if re.search(r'remove\s+(?:the\s+)?captions?\b', lower):
            return {"type": "REMOVE_CAPTION", "target": "all", "raw": text}

        # 5. Undo / Redo / History
        if lower in ("undo", "undo the last edit", "undo edit", "revert"):
            return {"type": "UNDO", "raw": text}
        if lower in ("redo", "redo the edit", "redo last edit"):
            return {"type": "REDO", "raw": text}

        # 6. Content / Ambiguous / Transcript references
        # "Remove the pricing section" / "Delete the introduction" / "Remove that part"
        m = re.match(r'^(?:remove|delete|cut)(?:\s+the)?\s+([a-zA-Z\s]+?)(?:\s+section|\s+part)?$', lower)
        if m:
            target_phrase = m.group(1).strip()
            if target_phrase in ("intro", "introduction"):
                return {"type": "RESTORE_OR_REMOVE_SECTION", "action": "remove", "section": "intro", "raw": text}
            if target_phrase in ("outro", "conclusion"):
                return {"type": "RESTORE_OR_REMOVE_SECTION", "action": "remove", "section": "outro", "raw": text}
            return {"type": "AMBIGUOUS_SECTION_REFERENCE", "phrase": target_phrase, "raw": text}

        # 7. Restoration
        # "Restore the intro" / "Restore the first 5 seconds"
        m = re.match(r'^restore(?:\s+the)?\s+([a-zA-Z0-9\s]+?)$', lower)
        if m:
            rest_target = m.group(1).strip()
            return {"type": "RESTORE_SECTION", "target": rest_target, "raw": text}

        # Unknown / Unsupported
        return {"type": "UNSUPPORTED", "raw": text}
