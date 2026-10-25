import subprocess
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
from incubrix.core.config import settings
from incubrix.core.errors import FFmpegDependencyError, IncuBrixError
from incubrix.core.logging import logger

class MediaProbe:
    @classmethod
    def get_ffprobe_path(cls) -> str:
        path = settings.FFPROBE_PATH
        if os.path.exists(path):
            return path
        # Try finding in PATH
        import shutil
        which = shutil.which("ffprobe")
        if which:
            return which
        raise FFmpegDependencyError("FFprobe executable was not found. Please ensure ffprobe is installed.")

    @classmethod
    def get_ffmpeg_path(cls) -> str:
        path = settings.FFMPEG_PATH
        if os.path.exists(path):
            return path
        import shutil
        which = shutil.which("ffmpeg")
        if which:
            return which
        raise FFmpegDependencyError("FFmpeg executable was not found. Please ensure ffmpeg is installed.")

    @classmethod
    def probe_file(cls, file_path: Path) -> Dict[str, Any]:
        ffprobe = cls.get_ffprobe_path()
        if not os.path.exists(file_path):
            raise IncuBrixError("FILE_NOT_FOUND", f"File '{file_path}' does not exist.")

        cmd = [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,duration,channels,sample_rate",
            "-of", "json",
            str(file_path)
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFprobe failed on {file_path}: {e.stderr}")
            raise IncuBrixError("PROBE_FAILED", f"FFprobe failed to inspect media file: {e.stderr}")
        except Exception as e:
            logger.error(f"FFprobe execution error: {e}")
            raise IncuBrixError("PROBE_ERROR", f"Error executing ffprobe: {str(e)}")

        streams = data.get("streams", [])
        fmt = data.get("format", {})

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        # Parse FPS
        fps = None
        if video_stream and "r_frame_rate" in video_stream:
            r_fps = video_stream["r_frame_rate"]
            try:
                if "/" in r_fps:
                    num, den = r_fps.split("/")
                    fps = round(float(num) / float(den), 2) if float(den) != 0 else None
                else:
                    fps = float(r_fps)
            except Exception:
                fps = None

        # Parse Duration
        duration = 0.0
        if "duration" in fmt:
            try:
                duration = float(fmt["duration"])
            except Exception:
                pass
        if duration == 0.0 and video_stream and "duration" in video_stream:
            try:
                duration = float(video_stream["duration"])
            except Exception:
                pass

        format_name = fmt.get("format_name", "")

        return {
            "duration": round(duration, 4),
            "size_bytes": int(fmt.get("size", os.path.getsize(file_path))),
            "bit_rate": int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else None,
            "format_name": format_name,
            "has_video": video_stream is not None,
            "has_audio": audio_stream is not None,
            "width": int(video_stream.get("width")) if video_stream and "width" in video_stream else None,
            "height": int(video_stream.get("height")) if video_stream and "height" in video_stream else None,
            "fps": fps,
            "video_codec": video_stream.get("codec_name") if video_stream else None,
            "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
            "channels": int(audio_stream.get("channels")) if audio_stream and "channels" in audio_stream else None,
            "sample_rate": int(audio_stream.get("sample_rate")) if audio_stream and "sample_rate" in audio_stream else None,
            "raw_streams": streams,
            "raw_format": fmt,
        }
