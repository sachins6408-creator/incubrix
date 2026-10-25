from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class RenderManifest(BaseModel):
    manifest_version: str = "1.0"
    job_id: str
    session_id: str
    input_asset_id: str
    input_sha256: str
    timeline_hash: str
    ffmpeg_command: List[str]
    output_path: str
    output_sha256: str
    output_duration: float
    output_width: Optional[int] = None
    output_height: Optional[int] = None
    output_fps: Optional[float] = None
    output_video_codec: Optional[str] = None
    output_audio_codec: Optional[str] = None
    status: str
    created_at: str
    completed_at: str
