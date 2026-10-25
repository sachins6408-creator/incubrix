import json
import uuid
from typing import Dict, Any, List, Optional
from incubrix.engine.timeline import Timeline
from incubrix.engine.operations import TimelineOperations
from incubrix.engine.history import HistoryManager
from incubrix.nlp.parser import InstructionParser
from incubrix.nlp.schemas import InstructionResult, ClarificationPayload, OccurrenceChoice
from incubrix.storage.backend import storage
from incubrix.core.errors import InvalidOperationError, IncuBrixError
from incubrix.core.logging import logger

class InstructionResolver:
    """
    Executes the real instruction-processing pipeline for both typed commands and sample buttons.
    Returns strictly APPLIED, NEEDS_CLARIFICATION, or REJECTED.
    """

    @classmethod
    def resolve_instruction(cls, session_id: str, raw_instruction: str) -> InstructionResult:
        session = storage.get_session(session_id)
        if not session:
            return InstructionResult(
                status="REJECTED",
                message=f"Session '{session_id}' not found.",
                error_code="SESSION_NOT_FOUND"
            )

        current_timeline_dict = json.loads(session["timeline_json"])
        current_timeline = Timeline(**current_timeline_dict)
        initial_hash = current_timeline.canonical_hash()

        # Check if there is an active pending clarification
        pending_clarification = storage.get_clarification(session_id)
        parsed = InstructionParser.parse(raw_instruction)

        # 1. Handle clarification responses if pending
        if pending_clarification:
            if parsed["type"] in ("CLARIFICATION_SELECT", "CLARIFICATION_SELECT_ALL"):
                return cls._handle_clarification_choice(
                    session_id, current_timeline, pending_clarification, parsed, raw_instruction
                )
            else:
                # If user entered something completely unrelated, we could either clear it or re-clarify
                storage.clear_clarification(session_id)

        # 2. Dispatch parsed commands
        try:
            cmd_type = parsed["type"]

            # Undo
            if cmd_type == "UNDO":
                new_timeline, op = HistoryManager.undo(session_id)
                return InstructionResult(
                    status="APPLIED",
                    message="Undone last operation successfully.",
                    operation_type="UNDO",
                    timeline=new_timeline.canonical_dict(),
                    timeline_hash=new_timeline.canonical_hash()
                )

            # Redo
            if cmd_type == "REDO":
                new_timeline, op = HistoryManager.redo(session_id)
                return InstructionResult(
                    status="APPLIED",
                    message="Redone operation successfully.",
                    operation_type="REDO",
                    timeline=new_timeline.canonical_dict(),
                    timeline_hash=new_timeline.canonical_hash()
                )

            # Ambiguous references triggering clarification
            if cmd_type == "AMBIGUOUS_SECTION_REFERENCE":
                phrase = parsed["phrase"]
                asset = storage.get_asset(current_timeline.asset_id)
                transcript = asset.get("transcript") if asset else None

                # Search in transcript occurrences if available
                candidates: List[OccurrenceChoice] = []
                if transcript and isinstance(transcript, list):
                    for idx, entry in enumerate(transcript):
                        if phrase.lower() in entry.get("text", "").lower():
                            candidates.append(OccurrenceChoice(
                                occurrence_id=f"occ_{idx+1}",
                                index=idx+1,
                                label=f"Occurrence {idx+1} at {entry.get('start', 0)}s - '{entry.get('text', '')}'",
                                source_range=[entry.get("start", 0.0), entry.get("end", 0.0)],
                                context=entry.get("text", "")
                            ))

                # If no transcript or no grounded matches, do not fabricate occurrences
                if not candidates:
                    return InstructionResult(
                        status="REJECTED",
                        message=f"Cannot ground '{phrase}' in the video. No spoken transcript or defined section matching '{phrase}' was detected.",
                        error_code="UNGROUNDED_REFERENCE"
                    )

                if len(candidates) > 1:
                    clarification_id = str(uuid.uuid4())[:8]
                    clarification_payload = ClarificationPayload(
                        clarification_id=clarification_id,
                        intent_type="CUT_SECTION",
                        prompt=f"Multiple occurrences matching '{phrase}' were found. Please select which occurrence to remove:",
                        options=candidates,
                        pending_operation={"phrase": phrase, "type": "REMOVE_OCCURRENCES"}
                    )
                    storage.save_clarification(
                        session_id=session_id,
                        clarification_id=clarification_id,
                        intent_type="CUT_SECTION",
                        prompt=clarification_payload.prompt,
                        options=[c.model_dump() for c in candidates]
                    )
                    return InstructionResult(
                        status="NEEDS_CLARIFICATION",
                        message=clarification_payload.prompt,
                        clarification=clarification_payload
                    )
                else:
                    # Single unambiguous candidate
                    single = candidates[0]
                    new_timeline = TimelineOperations.cut_range(
                        current_timeline, single.source_range[0], single.source_range[1]
                    )
                    cls._commit_edit(
                        session_id=session_id,
                        operation_type="CUT_SECTION",
                        raw_instruction=raw_instruction,
                        payload={"phrase": phrase, "occurrence": single.model_dump()},
                        timeline_before=current_timeline,
                        timeline_after=new_timeline
                    )
                    return InstructionResult(
                        status="APPLIED",
                        message=f"Removed '{phrase}' at {single.source_range[0]}s - {single.source_range[1]}s.",
                        operation_type="CUT_SECTION",
                        timeline=new_timeline.canonical_dict(),
                        timeline_hash=new_timeline.canonical_hash()
                    )

            # Restorations
            if cmd_type == "RESTORE_SECTION":
                target = parsed["target"]
                asset = storage.get_asset(current_timeline.asset_id)
                orig_dur = asset["duration"] if asset else 30.0
                if "intro" in target or "beginning" in target:
                    new_timeline = TimelineOperations.restore_intro(current_timeline, orig_dur, 5.0)
                    cls._commit_edit(
                        session_id=session_id,
                        operation_type="RESTORE_INTRO",
                        raw_instruction=raw_instruction,
                        payload={"target": target},
                        timeline_before=current_timeline,
                        timeline_after=new_timeline
                    )
                    return InstructionResult(
                        status="APPLIED",
                        message="Restored intro (0-5s) to the beginning while preserving other edits.",
                        operation_type="RESTORE_INTRO",
                        timeline=new_timeline.canonical_dict(),
                        timeline_hash=new_timeline.canonical_hash()
                    )
                else:
                    return InstructionResult(
                        status="REJECTED",
                        message=f"Unsupported restoration target '{target}'. You can restore the intro, e.g., 'Restore the intro'.",
                        error_code="UNSUPPORTED_RESTORE_TARGET"
                    )

            # Cuts and removals
            new_timeline: Optional[Timeline] = None
            op_type = cmd_type

            if cmd_type == "CUT_RANGE":
                new_timeline = TimelineOperations.cut_range(current_timeline, parsed["start"], parsed["end"])
            elif cmd_type == "CUT_FROM_END":
                new_timeline = TimelineOperations.cut_from_end(current_timeline, parsed["duration"])
            elif cmd_type == "CHANGE_SPEED":
                new_timeline = TimelineOperations.change_speed(current_timeline, parsed["speed"])
            elif cmd_type == "CHANGE_SPEED_RANGE":
                new_timeline = TimelineOperations.change_speed_range(
                    current_timeline, parsed["start"], parsed["end"], parsed["speed"]
                )
            elif cmd_type == "MOVE_SEGMENT":
                new_timeline = TimelineOperations.move_segment(current_timeline, parsed["source"], parsed["destination"])
            elif cmd_type == "SWAP_SEGMENTS":
                new_timeline = TimelineOperations.swap_segments(current_timeline, parsed["index_a"], parsed["index_b"])
            elif cmd_type == "REVERSE_SEGMENTS":
                new_timeline = TimelineOperations.reverse_segments(current_timeline)
            elif cmd_type == "ADD_CAPTION":
                new_timeline = TimelineOperations.add_caption(
                    current_timeline, parsed["text"], parsed["start_time"], parsed["duration"]
                )
            elif cmd_type == "CHANGE_CAPTION_COLOR":
                new_timeline = TimelineOperations.change_caption_color(current_timeline, parsed["color"])
            elif cmd_type == "REMOVE_CAPTION":
                new_timeline = TimelineOperations.remove_captions(current_timeline)
            elif cmd_type == "RESTORE_OR_REMOVE_SECTION":
                if parsed["section"] == "intro":
                    # Remove intro (first 5 seconds)
                    new_timeline = TimelineOperations.cut_range(current_timeline, 0.0, 5.0)
                else:
                    return InstructionResult(
                        status="REJECTED",
                        message=f"Section '{parsed['section']}' cannot be removed directly.",
                        error_code="UNSUPPORTED_SECTION"
                    )
            else:
                return InstructionResult(
                    status="REJECTED",
                    message=(
                        f"Unsupported or unrecognized command: '{raw_instruction}'.\n"
                        "Supported examples:\n"
                        "• 'Cut the first 5 seconds'\n"
                        "• 'Remove the segment between 10 and 15 seconds'\n"
                        "• 'Speed up the whole video by 2x'\n"
                        "• 'Move the last segment to the beginning'\n"
                        "• 'Add a caption saying Dance Practice at the beginning'\n"
                        "• 'Undo the last edit'"
                    ),
                    error_code="UNSUPPORTED_INSTRUCTION"
                )

            # Strict status validation: Timeline MUST have changed
            if new_timeline.canonical_hash() == initial_hash:
                return InstructionResult(
                    status="REJECTED",
                    message="The operation produced no net change on the timeline.",
                    error_code="NO_OP"
                )

            # Commit edit to storage and history
            cls._commit_edit(
                session_id=session_id,
                operation_type=op_type,
                raw_instruction=raw_instruction,
                payload=parsed,
                timeline_before=current_timeline,
                timeline_after=new_timeline
            )

            return InstructionResult(
                status="APPLIED",
                message=f"Applied '{raw_instruction}' successfully.",
                operation_type=op_type,
                timeline=new_timeline.canonical_dict(),
                timeline_hash=new_timeline.canonical_hash()
            )

        except IncuBrixError as e:
            return InstructionResult(
                status="REJECTED",
                message=e.message,
                error_code=e.code
            )
        except Exception as e:
            logger.exception("Unexpected error resolving instruction")
            return InstructionResult(
                status="REJECTED",
                message=f"Failed to apply instruction: {str(e)}",
                error_code="INTERNAL_ERROR"
            )

    @classmethod
    def _handle_clarification_choice(cls, session_id: str, current_timeline: Timeline,
                                    pending: Dict[str, Any], parsed: Dict[str, Any],
                                    raw_instruction: str) -> InstructionResult:
        options = pending.get("options", [])
        if not options:
            storage.clear_clarification(session_id)
            return InstructionResult(status="REJECTED", message="Clarification had no available options.", error_code="INVALID_STATE")

        try:
            if parsed["type"] == "CLARIFICATION_SELECT_ALL":
                # Remove all candidate occurrences in reverse order so ranges stay valid
                sorted_opts = sorted(options, key=lambda x: x["source_range"][0], reverse=True)
                updated_timeline = current_timeline
                for opt in sorted_opts:
                    s_range = opt["source_range"]
                    updated_timeline = TimelineOperations.cut_range(updated_timeline, s_range[0], s_range[1])

                storage.clear_clarification(session_id)
                cls._commit_edit(
                    session_id=session_id,
                    operation_type="CLARIFICATION_RESOLVED_ALL",
                    raw_instruction=raw_instruction,
                    payload={"selected": "ALL", "count": len(options)},
                    timeline_before=current_timeline,
                    timeline_after=updated_timeline
                )
                return InstructionResult(
                    status="APPLIED",
                    message=f"Removed all {len(options)} occurrences.",
                    operation_type="CLARIFICATION_RESOLVED_ALL",
                    timeline=updated_timeline.canonical_dict(),
                    timeline_hash=updated_timeline.canonical_hash()
                )

            # Specific selection
            target_idx = parsed.get("target_index", 1)
            # Find candidate with matching index
            matched = next((opt for opt in options if opt.get("index") == target_idx), None)
            if not matched:
                return InstructionResult(
                    status="REJECTED",
                    message=f"Selected occurrence {target_idx} is not valid. Please choose between 1 and {len(options)}.",
                    error_code="INVALID_SELECTION"
                )

            s_range = matched["source_range"]
            updated_timeline = TimelineOperations.cut_range(current_timeline, s_range[0], s_range[1])
            storage.clear_clarification(session_id)
            cls._commit_edit(
                session_id=session_id,
                operation_type="CLARIFICATION_RESOLVED",
                raw_instruction=raw_instruction,
                payload={"selected": target_idx, "occurrence": matched},
                timeline_before=current_timeline,
                timeline_after=updated_timeline
            )
            return InstructionResult(
                status="APPLIED",
                message=f"Removed occurrence {target_idx} ({matched.get('label')}).",
                operation_type="CLARIFICATION_RESOLVED",
                timeline=updated_timeline.canonical_dict(),
                timeline_hash=updated_timeline.canonical_hash()
            )

        except Exception as e:
            return InstructionResult(
                status="REJECTED",
                message=f"Failed to resolve clarification choice: {str(e)}",
                error_code="CLARIFICATION_EXECUTION_ERROR"
            )

    @classmethod
    def _commit_edit(cls, session_id: str, operation_type: str, raw_instruction: str,
                     payload: Dict[str, Any], timeline_before: Timeline, timeline_after: Timeline):
        op_id = str(uuid.uuid4())[:8]
        # Save session timeline
        storage.save_session(session_id, timeline_after.asset_id, timeline_after.canonical_json())
        # Record history operation
        storage.record_operation(
            session_id=session_id,
            operation_id=op_id,
            operation_type=operation_type,
            raw_instruction=raw_instruction,
            payload=payload,
            timeline_before_json=timeline_before.canonical_json(),
            timeline_after_json=timeline_after.canonical_json()
        )
