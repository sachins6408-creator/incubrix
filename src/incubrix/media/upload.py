import hashlib
import os
import uuid
import aiofiles
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import UploadFile
from incubrix.core.config import settings
from incubrix.core.errors import IncuBrixError
from incubrix.media.probe import MediaProbe
from incubrix.storage.backend import storage
from incubrix.core.logging import logger

class MediaUploader:
    @classmethod
    def _deduce_extension(cls, raw_ext: str, format_name: str) -> str:
        raw_ext = raw_ext.lower().strip()
        if raw_ext and raw_ext.startswith("."):
            return raw_ext

        fmt_lower = format_name.lower()
        if "mp4" in fmt_lower or "mov" in fmt_lower:
            return ".mp4"
        elif "matroska" in fmt_lower or "mkv" in fmt_lower:
            return ".mkv"
        elif "webm" in fmt_lower:
            return ".webm"
        elif "avi" in fmt_lower:
            return ".avi"
        elif "flv" in fmt_lower:
            return ".flv"
        elif "mpeg" in fmt_lower or "mpg" in fmt_lower:
            return ".mpg"
        elif "wmv" in fmt_lower or "asf" in fmt_lower:
            return ".wmv"
        elif "ogg" in fmt_lower or "ogv" in fmt_lower:
            return ".ogv"
        
        # Default fallback if valid container
        return ".mp4"

    @classmethod
    async def save_upload(cls, upload_file: UploadFile) -> Dict[str, Any]:
        raw_filename = upload_file.filename or "uploaded_video"
        raw_ext = Path(raw_filename).suffix.lower()

        # Stream upload directly to a staging file and validate media content with FFprobe
        asset_id = str(uuid.uuid4())
        staging_filename = f"staging_{asset_id}"
        staging_path = settings.UPLOADS_DIR / staging_filename

        hasher = hashlib.sha256()
        total_size = 0

        try:
            async with aiofiles.open(staging_path, "wb") as f:
                while chunk := await upload_file.read(1024 * 1024):
                    total_size += len(chunk)
                    if total_size > settings.MAX_UPLOAD_SIZE_BYTES:
                        await f.close()
                        if staging_path.exists():
                            staging_path.unlink()
                        raise IncuBrixError("FILE_TOO_LARGE", f"Uploaded file exceeds limit of {settings.MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB.")
                    hasher.update(chunk)
                    await f.write(chunk)

            sha256_hash = hasher.hexdigest()

            # Probe media with FFprobe to validate actual media content
            try:
                probe_info = MediaProbe.probe_file(staging_path)
            except Exception as e:
                if staging_path.exists():
                    staging_path.unlink()
                raise IncuBrixError("INVALID_MEDIA", f"Uploaded file is not a valid or supported media file: {str(e)}")

            # Ensure the probed file contains at least one video stream
            if not probe_info.get("has_video"):
                if staging_path.exists():
                    staging_path.unlink()
                raise IncuBrixError("INVALID_MEDIA", "Uploaded media does not contain a valid video stream.")

            # Determine canonical extension based on raw filename or probed container format
            canonical_ext = cls._deduce_extension(raw_ext, probe_info.get("format_name", ""))

            dest_filename = f"{asset_id}{canonical_ext}"
            dest_path = settings.UPLOADS_DIR / dest_filename
            staging_path.rename(dest_path)

        except Exception:
            if staging_path.exists():
                staging_path.unlink()
            raise

        filename = raw_filename if raw_filename else f"video{canonical_ext}"

        asset_record = {
            "asset_id": asset_id,
            "filename": filename,
            "file_path": str(dest_path),
            "sha256": sha256_hash,
            "size_bytes": total_size,
            "duration": probe_info["duration"],
            "width": probe_info["width"],
            "height": probe_info["height"],
            "fps": probe_info["fps"],
            "video_codec": probe_info["video_codec"],
            "audio_codec": probe_info["audio_codec"],
            "channels": probe_info["channels"],
            "sample_rate": probe_info["sample_rate"],
            "metadata": probe_info,
            "transcript": None,
        }

        storage.save_asset(asset_record)
        logger.info(f"Saved asset {asset_id} ({filename}) with sha256 {sha256_hash}")

        return {
            "asset_id": asset_id,
            "filename": filename,
            "sha256": sha256_hash,
            "size_bytes": total_size,
            "duration": probe_info["duration"],
            "width": probe_info["width"],
            "height": probe_info["height"],
            "fps": probe_info["fps"],
            "video_codec": probe_info["video_codec"],
            "audio_codec": probe_info["audio_codec"],
            "stream_url": f"/api/v1/media/{asset_id}/stream",
            "metadata": probe_info,
            "transcript": None,
        }
