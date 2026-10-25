import uuid
import json
from typing import Dict, Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, status, HTTPException
from incubrix.storage.backend import storage
from incubrix.engine.timeline import Timeline, Segment
from incubrix.engine.history import HistoryManager
from incubrix.engine.resolver import InstructionResolver
from incubrix.rendering.jobs import RenderJobService
from incubrix.core.errors import SessionNotFoundError, AssetNotFoundError

router = APIRouter(prefix="/sessions", tags=["Sessions"])

class CreateSessionRequest(BaseModel):
    asset_id: str

class InstructionRequest(BaseModel):
    instruction: str

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(req: CreateSessionRequest):
    """
    Creates an editing session strictly bound to a real uploaded asset_id.
    Initializes a full timeline spanning [0, asset.duration].
    """
    asset = storage.get_asset(req.asset_id)
    if not asset:
        raise AssetNotFoundError(req.asset_id)

    session_id = str(uuid.uuid4())
    initial_segment = Segment(
        id=str(uuid.uuid4())[:8],
        asset_id=req.asset_id,
        source_start=0.0,
        source_end=asset["duration"],
        speed=1.0,
        label="Original"
    )
    initial_timeline = Timeline(asset_id=req.asset_id, segments=[initial_segment])
    storage.save_session(session_id, req.asset_id, initial_timeline.canonical_json())

    return {
        "session_id": session_id,
        "asset_id": req.asset_id,
        "timeline": initial_timeline.canonical_dict(),
        "timeline_hash": initial_timeline.canonical_hash(),
        "created_at": asset.get("created_at")
    }

@router.get("/{session_id}")
async def get_session(session_id: str):
    session = storage.get_session(session_id)
    if not session:
        raise SessionNotFoundError(session_id)
    timeline_dict = json.loads(session["timeline_json"])
    timeline = Timeline(**timeline_dict)
    asset = storage.get_asset(session["asset_id"])

    return {
        "session_id": session_id,
        "asset_id": session["asset_id"],
        "asset": asset,
        "timeline": timeline.canonical_dict(),
        "timeline_hash": timeline.canonical_hash(),
        "updated_at": session.get("updated_at")
    }

@router.get("/{session_id}/timeline")
async def get_session_timeline(session_id: str):
    session = storage.get_session(session_id)
    if not session:
        raise SessionNotFoundError(session_id)
    timeline_dict = json.loads(session["timeline_json"])
    timeline = Timeline(**timeline_dict)
    return {
        "timeline": timeline.canonical_dict(),
        "timeline_hash": timeline.canonical_hash()
    }

@router.post("/{session_id}/instructions")
async def apply_instruction(session_id: str, req: InstructionRequest):
    """
    Unified entry point for both manually typed natural-language instructions and sample prompt buttons.
    Returns strictly APPLIED, NEEDS_CLARIFICATION, or REJECTED.
    """
    return InstructionResolver.resolve_instruction(session_id, req.instruction)

@router.post("/{session_id}/undo")
async def undo_edit(session_id: str):
    """
    Reverts exactly one successful edit.
    """
    session = storage.get_session(session_id)
    if not session:
        raise SessionNotFoundError(session_id)
    reverted_timeline, op = HistoryManager.undo(session_id)
    return {
        "status": "APPLIED",
        "message": "Undone last operation.",
        "timeline": reverted_timeline.canonical_dict(),
        "timeline_hash": reverted_timeline.canonical_hash(),
        "operation": op
    }

@router.post("/{session_id}/redo")
async def redo_edit(session_id: str):
    """
    Reapplies an undone operation.
    """
    session = storage.get_session(session_id)
    if not session:
        raise SessionNotFoundError(session_id)
    redone_timeline, op = HistoryManager.redo(session_id)
    return {
        "status": "APPLIED",
        "message": "Redone operation.",
        "timeline": redone_timeline.canonical_dict(),
        "timeline_hash": redone_timeline.canonical_hash(),
        "operation": op
    }

@router.post("/{session_id}/render", status_code=status.HTTP_202_ACCEPTED)
async def trigger_render(session_id: str):
    """
    Triggers an asynchronous FFmpeg render job for the current session timeline.
    Returns 202 Accepted with a job_id.
    """
    session = storage.get_session(session_id)
    if not session:
        raise SessionNotFoundError(session_id)

    job_id = RenderJobService.start_render_job(session_id)
    return {
        "job_id": job_id,
        "session_id": session_id,
        "status": "QUEUED",
        "poll_url": f"/api/v1/jobs/{job_id}"
    }

@router.get("/{session_id}/history")
async def get_history(session_id: str):
    session = storage.get_session(session_id)
    if not session:
        raise SessionNotFoundError(session_id)
    return storage.get_operations_history(session_id)
