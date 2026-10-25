import json
from typing import Optional, Dict, Any, Tuple
from incubrix.engine.timeline import Timeline
from incubrix.storage.backend import storage
from incubrix.core.errors import InvalidOperationError

class HistoryManager:
    """
    Manages atomic Undo and Redo operations, and invalidation of the redo stack on new edits.
    """

    @classmethod
    def undo(cls, session_id: str) -> Tuple[Timeline, Dict[str, Any]]:
        op = storage.get_last_applied_operation(session_id)
        if not op:
            raise InvalidOperationError("No operations available to undo.")

        # Revert timeline to timeline_before
        timeline_before_dict = json.loads(op["timeline_before_json"])
        reverted_timeline = Timeline(**timeline_before_dict)

        # Mark operation as undone
        storage.mark_operation_undone(op["id"])

        # Persist reverted timeline in session
        storage.save_session(session_id, reverted_timeline.asset_id, reverted_timeline.canonical_json())

        return reverted_timeline, op

    @classmethod
    def redo(cls, session_id: str) -> Tuple[Timeline, Dict[str, Any]]:
        op = storage.get_last_undone_operation(session_id)
        if not op:
            raise InvalidOperationError("No operations available to redo.")

        # Re-apply timeline after
        timeline_after_dict = json.loads(op["timeline_after_json"])
        redone_timeline = Timeline(**timeline_after_dict)

        # Mark operation as active/redone
        storage.mark_operation_redone(op["id"])

        # Persist redone timeline in session
        storage.save_session(session_id, redone_timeline.asset_id, redone_timeline.canonical_json())

        return redone_timeline, op
