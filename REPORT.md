# IncuBrix Implementation & Engineering Report

## Executive Summary
IncuBrix was built to solve the challenge of transforming unconstrained natural-language video editing commands into precise, deterministic, content-anchored timeline mutations that can be compiled directly into FFmpeg filter graphs and rendered into playable video files.

The application adheres strictly to honest outcomes, non-destructive editing, persistent state tracking, and genuine media processing without mocks or fake buttons.

---

## 1. Architecture & Design Choices

### 1.1 Content-Anchored Canonical Timeline
- **Concept**: Timeline segments do not hold raw frame buffers; instead, they reference immutable intervals of original source media (`source_start`, `source_end`), playback speed factors, captions, and audio filters.
- **Determinism**: The `canonical_dict()` and `canonical_hash()` algorithms produce stable, reproducible SHA-256 hashes across equivalent timeline states regardless of dictionary key ordering.
- **Source Immutability**: Edits modify only the timeline model, ensuring that the original media remains strictly unchanged on disk.

### 1.2 Unified Instruction Pipeline & Honest Outcomes
- **Single Dispatch Pipeline**: Both user-typed instructions and sample pills pass through `InstructionResolver.resolve_instruction()`. Sample buttons never bypass the parser.
- **Strict Status Contract**: Every instruction produces exactly one of:
  - `APPLIED`: Timeline was validated and changed.
  - `NEEDS_CLARIFICATION`: Multiple grounded occurrences exist; returns candidate options with stable IDs.
  - `REJECTED`: Instruction was out-of-range, unsupported, or ungrounded.
- **Grounded Clarification Resolution**: When ambiguous references like "pricing section" are received, the engine checks for grounded occurrences in the transcript. On videos lacking pricing sections (e.g. `D:\dance`), the engine rejects the command with a clear explanation rather than inventing fake data.

### 1.3 Asynchronous FFmpeg Rendering
- **Filter Graph Generation**: Compiles segments into an FFmpeg `filter_complex` script using `trim`, `setpts`, `atrim`, `atempo`, `concat`, and `drawtext` filters.
- **Audit Manifest**: Produces a comprehensive JSON manifest documenting the input asset hash, timeline hash, FFmpeg command line, output hash, duration, and video/audio stream properties.

---

## 2. Verification Evidence

### 2.1 Automated Test Suite
- Total Tests: **42 passed**
- Coverage areas:
  - Source file immutability and SHA-256 preservation
  - Deterministic timeline canonical hashing
  - Natural-language parsing of cuts, speed, reordering, captions, clarifications, and unsupported commands
  - Bounds safety (negative times, start >= end, out of range, empty timeline rejection)
  - Atomic undo, redo, and redo-stack invalidation
  - Media upload, FFprobe probing, and HTTP 206 byte-range streaming
  - Asynchronous FFmpeg background jobs and manifest generation
  - 404 and structured error responses

### 2.2 Scripted Session Scenarios
- **15 Reproducible Scripted Sessions** executed via `python tests/batch_runner.py`:
  - `session_01_cut_beginning`: APPLIED (Trim 5s)
  - `session_02_cut_end`: APPLIED (Remove last 3s)
  - `session_03_cut_middle`: APPLIED (Split 10s to 15s)
  - `session_04_speed_up_whole`: APPLIED (Speed 2x)
  - `session_05_slow_down`: APPLIED (Slow 0.5x)
  - `session_06_speed_range`: APPLIED (Speed range 5-10s)
  - `session_07_add_caption`: APPLIED (Add caption)
  - `session_08_change_caption_color`: APPLIED (Change caption color)
  - `session_09_remove_caption`: APPLIED (Remove caption)
  - `session_10_swap_segments`: APPLIED (Swap 2 segments)
  - `session_11_reverse_segments`: APPLIED (Reverse segments)
  - `session_12_undo_redo_pipeline`: APPLIED (Atomic undo/redo)
  - `session_13_restore_intro`: APPLIED (Restore intro)
  - `session_14_ambiguous_rejection`: REJECTED (Ungrounded section)
  - `session_15_invalid_bounds_rejection`: REJECTED (Out-of-bounds cut)
  - **Result: 15 / 15 Passed**

### 2.3 Real Media Demonstration with `D:\dance`
- Uploaded original video:
  - File size: 63,589,848 bytes
  - Resolution: 888x496 @ 59.88 fps (HEVC video, AAC stereo audio)
  - Initial SHA-256: `602f3ca0899ad6206a99b4d6b65f1a09cd6b480ec3ad95bb3badd1732e37467a`
- Edits applied:
  1. Cut first 5s -> New duration 25.03s (`APPLIED`)
  2. Set playback speed to 1.5x -> New duration 16.69s (`APPLIED`)
  3. Undo -> Duration restored to 25.03s (`APPLIED`)
  4. Redo -> Duration restored to 16.69s (`APPLIED`)
  5. Add caption "Dance Practice" -> Attached (`APPLIED`)
  6. Ambiguous command "Remove the pricing section" -> Rejected honestly (`REJECTED`)
- Render Execution:
  - FFmpeg compiled filter complex and encoded output to `data/storage/renders/render_...mp4`
  - Output duration: 16.70s
  - Output SHA-256: `cfed7085bb7b5edb3b6fc5e06735429bce3901aa140dd1d94c8022c72b87d094`
- Verification:
  - `D:\dance` final SHA-256: `602f3ca0899ad6206a99b4d6b65f1a09cd6b480ec3ad95bb3badd1732e37467a` (Zero bytes altered).

---

## 3. Known Limitations & Future Work
- **GPU Acceleration**: Current rendering pipeline uses `libx264` CPU encoding for maximum portability across test environments. Hardware encoders (`h264_nvenc` / `h264_amf`) can be added when compatible hardware is detected.
- **Advanced Transitions**: Crossfades and wipe transitions can be introduced into the filter graph generator.
- **External Speech Transcription**: Automated speech transcription currently requires Whisper or a similar model installed locally; when unavailable, the engine honestly reports transcription unavailability.
