import asyncio
import json
import uuid
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from incubrix.rendering.ffmpeg import FFmpegRenderer
from incubrix.engine.timeline import Timeline
from incubrix.storage.backend import storage
from incubrix.core.logging import logger

executor = ThreadPoolExecutor(max_workers=3)

class RenderJobService:
    @classmethod
    def start_render_job(cls, session_id: str) -> str:
        session = storage.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")

        job_id = str(uuid.uuid4())
        timeline_dict = json.loads(session["timeline_json"])
        timeline = Timeline(**timeline_dict)

        storage.create_render_job(job_id, session_id, session["asset_id"])

        # Run render in background thread
        asyncio.get_event_loop().run_in_executor(
            executor,
            cls._execute_render_job,
            session_id,
            job_id,
            timeline
        )

        return job_id

    @classmethod
    def _execute_render_job(cls, session_id: str, job_id: str, timeline: Timeline):
        logger.info(f"Starting render job {job_id} for session {session_id}")
        storage.update_render_job(job_id, status="RUNNING", progress=0.2)

        try:
            manifest = FFmpegRenderer.render_timeline(session_id, job_id, timeline)
            storage.update_render_job(
                job_id=job_id,
                status="COMPLETED",
                progress=1.0,
                output_path=manifest["output_path"],
                manifest=manifest
            )
            logger.info(f"Render job {job_id} completed successfully.")
        except Exception as e:
            logger.exception(f"Render job {job_id} failed: {e}")
            storage.update_render_job(
                job_id=job_id,
                status="FAILED",
                progress=0.0,
                error_message=str(e)
            )

    @classmethod
    def get_job_status(cls, job_id: str) -> Optional[Dict[str, Any]]:
        return storage.get_render_job(job_id)
