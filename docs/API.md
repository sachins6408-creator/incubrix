# IncuBrix API Reference (v1)

Base URL: `http://localhost:8000/api/v1`

Interactive Documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI Specification: `http://localhost:8000/api/v1/openapi.json`

---

## 1. System Health & Readiness

### `GET /health`
Returns basic service availability and mode.

**Response `200 OK`**:
```json
{
  "status": "UP",
  "service": "IncuBrix",
  "version": "1.0.0",
  "mode": "Local deterministic instruction engine"
}
```

### `GET /ready`
Verifies writeable storage paths, database, and valid FFmpeg/FFprobe binaries.

**Response `200 OK`**:
```json
{
  "status": "READY",
  "checks": {
    "uploads_dir": true,
    "renders_dir": true,
    "database": true,
    "ffmpeg": true,
    "ffprobe": true
  }
}
```

---

## 2. Media Upload & Streaming

### `POST /api/v1/media/upload`
Uploads a video file (multipart/form-data). Validates container with FFprobe and calculates SHA-256 hash.

**Response `200 OK`**:
```json
{
  "asset_id": "a9d7010f-2f88-4209-8bdf-b59cfc81a702",
  "filename": "dance.mp4",
  "sha256": "3cb49a43a0889c25bb...",
  "size_bytes": 63589848,
  "duration": 30.03,
  "width": 888,
  "height": 496,
  "fps": 59.88,
  "video_codec": "hevc",
  "audio_codec": "aac",
  "stream_url": "/api/v1/media/a9d7010f-2f88-4209-8bdf-b59cfc81a702/stream"
}
```

### `GET /api/v1/media/{asset_id}/stream`
Streams the original source video with HTTP 206 partial content / byte-range support.

---

## 3. Editing Sessions

### `POST /api/v1/sessions`
Initializes a deterministic editing session bound to `asset_id`.

**Request**:
```json
{ "asset_id": "a9d7010f-2f88-4209-8bdf-b59cfc81a702" }
```

**Response `201 Created`**:
```json
{
  "session_id": "97e6be95-4632-414d-961b-9fb23d70f1a6",
  "asset_id": "a9d7010f-2f88-4209-8bdf-b59cfc81a702",
  "timeline": {
    "asset_id": "a9d7010f-2f88-4209-8bdf-b59cfc81a702",
    "total_duration": 30.03,
    "segments": [...]
  },
  "timeline_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

### `POST /api/v1/sessions/{session_id}/instructions`
Unified endpoint for natural-language instructions (typed by user or via sample buttons).

**Outcomes**:
- `APPLIED`: Timeline was validated and changed.
- `NEEDS_CLARIFICATION`: Multiple references detected; returns candidates with occurrence IDs.
- `REJECTED`: Invalid, unsupported, or out-of-range instruction.

**Example Request**:
```json
{ "instruction": "Cut the first 5 seconds." }
```

### `POST /api/v1/sessions/{session_id}/undo`
Reverts exactly one successful edit.

### `POST /api/v1/sessions/{session_id}/redo`
Reapplies an undone edit (invalidated when a new edit is committed).

---

## 4. FFmpeg Rendering Pipeline

### `POST /api/v1/sessions/{session_id}/render`
Triggers an asynchronous FFmpeg rendering job.

**Response `202 Accepted`**:
```json
{
  "job_id": "8c42b03f-6f9a-412f-93d2-a720e74f801a",
  "session_id": "97e6be95-4632-414d-961b-9fb23d70f1a6",
  "status": "QUEUED",
  "poll_url": "/api/v1/jobs/8c42b03f-6f9a-412f-93d2-a720e74f801a"
}
```

### `GET /api/v1/jobs/{job_id}`
Returns job status (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`), progress, and audit manifest.

### `GET /api/v1/jobs/{job_id}/download`
Downloads the completed rendered MP4 video file.
