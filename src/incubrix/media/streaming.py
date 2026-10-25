import os
from typing import Generator
from pathlib import Path
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from incubrix.core.errors import AssetNotFoundError
from incubrix.storage.backend import storage

CHUNK_SIZE = 1024 * 1024  # 1MB

def range_streamer(file_path: Path, start: int, end: int) -> Generator[bytes, None, None]:
    with open(file_path, "rb") as video:
        video.seek(start)
        bytes_to_read = (end - start) + 1
        while bytes_to_read > 0:
            read_size = min(CHUNK_SIZE, bytes_to_read)
            data = video.read(read_size)
            if not data:
                break
            bytes_to_read -= len(data)
            yield data

class MediaStreamer:
    @classmethod
    def stream_video(cls, asset_id: str, request: Request) -> Response:
        asset = storage.get_asset(asset_id)
        if not asset:
            raise AssetNotFoundError(asset_id)

        file_path = Path(asset["file_path"])
        if not file_path.exists():
            raise AssetNotFoundError(asset_id)

        file_size = file_path.stat().st_size
        range_header = request.headers.get("range")

        # Determine media type
        ext = file_path.suffix.lower()
        media_type = "video/mp4"
        if ext == ".mov":
            media_type = "video/quicktime"
        elif ext == ".webm":
            media_type = "video/webm"
        elif ext == ".mkv":
            media_type = "video/x-matroska"
        elif ext == ".avi":
            media_type = "video/x-msvideo"
        elif ext == ".flv":
            media_type = "video/x-flv"
        elif ext == ".wmv":
            media_type = "video/x-ms-wmv"
        elif ext in (".mpg", ".mpeg"):
            media_type = "video/mpeg"
        elif ext in (".ogv", ".ogg"):
            media_type = "video/ogg"

        if range_header:
            range_val = range_header.replace("bytes=", "")
            parts = range_val.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1

            if start >= file_size:
                return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

            end = min(end, file_size - 1)
            content_length = (end - start) + 1

            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": media_type,
            }

            return StreamingResponse(
                range_streamer(file_path, start, end),
                status_code=206,
                headers=headers,
                media_type=media_type
            )
        else:
            headers = {
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Type": media_type,
            }
            return StreamingResponse(
                range_streamer(file_path, 0, file_size - 1),
                status_code=200,
                headers=headers,
                media_type=media_type
            )
