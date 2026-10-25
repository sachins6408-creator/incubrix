import os
from fastapi import APIRouter, status, Response
from incubrix.core.config import settings
from incubrix.media.probe import MediaProbe

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health_check():
    """
    Reports service availability.
    """
    return {
        "status": "UP",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "mode": settings.ENGINE_MODE
    }

@router.get("/ready")
async def readiness_check(response: Response):
    """
    Verifies required dependencies: storage paths, database, and FFmpeg/FFprobe binaries.
    """
    checks = {
        "uploads_dir": settings.UPLOADS_DIR.exists() and os.access(settings.UPLOADS_DIR, os.W_OK),
        "renders_dir": settings.RENDERS_DIR.exists() and os.access(settings.RENDERS_DIR, os.W_OK),
        "database": settings.DB_PATH.exists(),
        "ffmpeg": False,
        "ffprobe": False,
    }

    try:
        MediaProbe.get_ffmpeg_path()
        checks["ffmpeg"] = True
    except Exception:
        pass

    try:
        MediaProbe.get_ffprobe_path()
        checks["ffprobe"] = True
    except Exception:
        pass

    all_ready = all(checks.values())
    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "READY" if all_ready else "NOT_READY",
        "checks": checks
    }
