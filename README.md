# IncuBrix — Prompt-Based Video Editing Engine

IncuBrix is a production-grade, functional video editing engine that translates natural-language editing instructions into deterministic timeline operations and executes real FFmpeg renders with complete manifests and source media immutability.

---

## Key Highlights

- **Local Deterministic Instruction Engine**: Real natural-language parsing for cuts, trims, speed adjustments (overall and range-bounded), segment reordering/swapping, captions, and history operations without requiring external API keys.
- **Strict Instruction Outcomes**: Every instruction strictly returns `APPLIED`, `NEEDS_CLARIFICATION`, or `REJECTED`. Never returns `APPLIED` if the timeline was not actually mutated.
- **Source Byte Immutability**: All edits are non-destructive, content-anchored timeline mutations. The original media file SHA-256 hash is preserved byte-for-byte.
- **Persistent Clarification Engine**: Disambiguates multiple content occurrences with stable IDs and handles follow-up choices (`Remove occurrence 1`, `Remove the second occurrence`, `Remove all occurrences`).
- **Atomic History Management**: Reversible `undo` and `redo` with strict redo-stack invalidation upon new edits, plus selective region restoration (`Restore the intro`).
- **Real FFmpeg Rendering**: Translates canonical timeline segments into `filter_complex` graphs, preserving audio/video synchronization, and produces verifiable render manifests with output hashes and duration validation.
- **Modern Dark UI**: Features video preview with HTTP 206 byte-range streaming, segment blocks, unified prompt inputs, interactive clarification chips, and real-time FFmpeg render progress.

---

## Architecture

```
incubrix/
├── src/incubrix/
│   ├── api/v1/             # FastAPI application and route definitions
│   │   ├── routes/         # media, sessions, jobs, health
│   │   └── app.py
│   ├── core/               # Configuration, error hierarchy, structured JSON logging
│   ├── media/              # FFprobe media probe, streaming (206 partials), upload
│   ├── nlp/                # Deterministic grammar parser, schemas, clarification logic
│   ├── engine/             # Canonical Timeline, Segment models, Operations, History
│   ├── rendering/          # FFmpeg command generator, async jobs, render manifests
│   └── storage/            # Persistent SQLite database & local storage backend
├── static/                 # Production dark-themed web interface (HTML/CSS/JS)
├── tests/                  # Pytest test suite (42 unit/integration tests)
│   ├── sessions/           # 15 reproducible scripted session JSON scenarios
│   └── batch_runner.py     # Automated batch runner for all scripted sessions
├── docs/                   # OpenAPI specification and canonical timeline JSON schema
├── pyproject.toml          # Python build and package specifications
├── Dockerfile              # Container definition with FFmpeg
└── docker-compose.yml      # Multi-container orchestration
```

---

## Getting Started

### 1. Requirements
- Python 3.11+
- FFmpeg and FFprobe (automatically configured in `bin/` or installed system-wide)

### 2. Installation
```powershell
# Clone or navigate to the directory
cd d:\incubrix

# Install dependencies in editable mode
pip install -e .
```

### 3. Running the Server
```powershell
$env:PYTHONPATH="src"
uvicorn incubrix.api.v1.app:app --host 127.0.0.1 --port 8000
```
Open your browser at `http://localhost:8000/`.

---

## Running the Automated Test Suite

### Full Pytest Suite (42 tests):
```powershell
pytest -v
```

### Batch Scripted Session Runner (15 scenarios):
```powershell
$env:PYTHONPATH="src"
python tests/batch_runner.py
```

---

## Demonstration Workflow (with `D:\dance`)

1. **Upload `D:\dance`**:
   - Local SHA-256 hash: `602f3ca0899ad6206a99b4d6b65f1a09cd6b480ec3ad95bb3badd1732e37467a`
   - Upload via web UI or API (`POST /api/v1/media/upload`).
2. **Preview**:
   - Native HTML5 video player streams original file via HTTP 206 Partial Content.
3. **Natural-Language Editing**:
   - Enter `Cut the first 5 seconds.` -> Returns `APPLIED`, output duration updates to 25.03s.
   - Enter `Set playback speed to 1.5x.` -> Returns `APPLIED`, timeline duration updates to 16.69s.
   - Enter `Add a caption saying Dance Practice at the beginning.` -> Returns `APPLIED`.
   - Click **Undo** -> Reverts speed operation back to 25.03s.
   - Click **Redo** -> Restores speed operation back to 16.69s.
4. **Clarification Handling**:
   - Enter `Remove the pricing section.` -> Returns `REJECTED: Cannot ground 'pricing' in the video. No spoken transcript or defined section matching 'pricing' was detected.` (Never fabricates content).
5. **Real FFmpeg Rendering**:
   - Click **Render Video** -> Initiates async render job (`POST /api/v1/sessions/{id}/render`).
   - Polls job until completion. Generates final MP4 with valid H.264/AAC streams and audit manifest.
   - Click **Download Rendered Video** or **Preview Rendered**.
6. **Verify Source Immutability**:
   - `D:\dance` remains unchanged at `602f3ca0899ad6206a99b4d6b65f1a09cd6b480ec3ad95bb3badd1732e37467a`.
