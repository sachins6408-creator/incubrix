from typing import Any, Optional
from fastapi import HTTPException, status

class IncuBrixError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Any] = None, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code

    def to_dict(self):
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }

class AssetNotFoundError(IncuBrixError):
    def __init__(self, asset_id: str):
        super().__init__(
            code="ASSET_NOT_FOUND",
            message=f"Media asset '{asset_id}' was not found.",
            details={"asset_id": asset_id},
            status_code=status.HTTP_404_NOT_FOUND,
        )

class SessionNotFoundError(IncuBrixError):
    def __init__(self, session_id: str):
        super().__init__(
            code="SESSION_NOT_FOUND",
            message=f"Editing session '{session_id}' was not found.",
            details={"session_id": session_id},
            status_code=status.HTTP_404_NOT_FOUND,
        )

class JobNotFoundError(IncuBrixError):
    def __init__(self, job_id: str):
        super().__init__(
            code="JOB_NOT_FOUND",
            message=f"Render job '{job_id}' was not found.",
            details={"job_id": job_id},
            status_code=status.HTTP_404_NOT_FOUND,
        )

class InvalidOperationError(IncuBrixError):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            code="INVALID_OPERATION",
            message=message,
            details=details,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

class FFmpegDependencyError(IncuBrixError):
    def __init__(self, message: str = "FFmpeg/FFprobe binaries are missing or nonfunctional."):
        super().__init__(
            code="FFMPEG_UNAVAILABLE",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
