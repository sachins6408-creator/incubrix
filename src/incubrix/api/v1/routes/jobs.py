from pathlib import Path
from fastapi import APIRouter, status
from fastapi.responses import FileResponse
from incubrix.rendering.jobs import RenderJobService
from incubrix.core.errors import JobNotFoundError, IncuBrixError

router = APIRouter(prefix="/jobs", tags=["Render Jobs"])

@router.get("/{job_id}")
async def get_job_status(job_id: str):
    """
    Returns the status (QUEUED, RUNNING, COMPLETED, FAILED), progress, and render manifest of a job.
    """
    job = RenderJobService.get_job_status(job_id)
    if not job:
        raise JobNotFoundError(job_id)

    res = {
        "job_id": job["job_id"],
        "session_id": job["session_id"],
        "status": job["status"],
        "progress": job["progress"],
        "error_message": job["error_message"],
        "manifest": job["manifest"],
    }
    if job["status"] == "COMPLETED" and job.get("output_path"):
        res["download_url"] = f"/api/v1/jobs/{job_id}/download"
        res["stream_url"] = f"/api/v1/jobs/{job_id}/stream"

    return res

@router.get("/{job_id}/download")
async def download_rendered_video(job_id: str):
    """
    Provides downloadable output only after a render job completes successfully.
    """
    job = RenderJobService.get_job_status(job_id)
    if not job:
        raise JobNotFoundError(job_id)

    if job["status"] != "COMPLETED" or not job.get("output_path"):
        raise IncuBrixError("JOB_NOT_READY", "Render output is not ready for download.", status_code=status.HTTP_400_BAD_REQUEST)

    file_path = Path(job["output_path"])
    if not file_path.exists():
        raise IncuBrixError("OUTPUT_FILE_MISSING", "Rendered video file was not found on disk.", status_code=status.HTTP_404_NOT_FOUND)

    filename = file_path.name
    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/{job_id}/stream")
async def stream_rendered_video(job_id: str):
    """
    Streams the completed rendered video for in-browser playback.
    """
    job = RenderJobService.get_job_status(job_id)
    if not job:
        raise JobNotFoundError(job_id)

    if job["status"] != "COMPLETED" or not job.get("output_path"):
        raise IncuBrixError("JOB_NOT_READY", "Render output is not ready for playback.", status_code=status.HTTP_400_BAD_REQUEST)

    file_path = Path(job["output_path"])
    if not file_path.exists():
        raise IncuBrixError("OUTPUT_FILE_MISSING", "Rendered video file was not found on disk.", status_code=status.HTTP_404_NOT_FOUND)

    return FileResponse(
        path=file_path,
        media_type="video/mp4"
    )
