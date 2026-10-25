from fastapi import APIRouter, UploadFile, File, Request, Response
from incubrix.media.upload import MediaUploader
from incubrix.media.streaming import MediaStreamer
from incubrix.storage.backend import storage
from incubrix.core.errors import AssetNotFoundError

router = APIRouter(prefix="/media", tags=["Media"])

@router.post("/upload")
async def upload_media(file: UploadFile = File(...)):
    """
    Accepts multipart upload of video files (MP4, MOV, etc.),
    validates format with ffprobe, calculates SHA-256 hash, and saves asset record.
    """
    return await MediaUploader.save_upload(file)

@router.get("/{asset_id}/stream")
async def stream_media(asset_id: str, request: Request):
    """
    Streams the uploaded original video with HTTP byte-range requests support (206 Partial Content).
    """
    return MediaStreamer.stream_video(asset_id, request)

@router.get("/{asset_id}")
async def get_asset_info(asset_id: str):
    """
    Returns asset metadata, duration, dimensions, codecs, and hash.
    """
    asset = storage.get_asset(asset_id)
    if not asset:
        raise AssetNotFoundError(asset_id)
    return asset

@router.get("")
async def list_assets():
    """
    Lists all saved media assets.
    """
    return storage.list_assets()
