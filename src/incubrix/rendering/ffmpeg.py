import os
import subprocess
import hashlib
from typing import List, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
from incubrix.core.config import settings
from incubrix.core.errors import IncuBrixError, FFmpegDependencyError
from incubrix.media.probe import MediaProbe
from incubrix.engine.timeline import Timeline
from incubrix.storage.backend import storage
from incubrix.core.logging import logger

class FFmpegRenderer:
    @classmethod
    def render_timeline(cls, session_id: str, job_id: str, timeline: Timeline) -> Dict[str, Any]:
        """
        Translates canonical Timeline segments, speed changes, and captions into a clean FFmpeg filter_complex pipeline.
        Executes FFmpeg, inspects output with FFprobe, verifies sha256, and returns manifest.
        """
        asset = storage.get_asset(timeline.asset_id)
        if not asset:
            raise IncuBrixError("ASSET_NOT_FOUND", f"Asset {timeline.asset_id} does not exist.")

        input_path = Path(asset["file_path"])
        if not input_path.exists():
            raise IncuBrixError("FILE_NOT_FOUND", f"Source file {input_path} missing.")

        has_audio = asset.get("audio_codec") is not None
        output_filename = f"render_{session_id}_{job_id}.mp4"
        output_path = settings.RENDERS_DIR / output_filename

        ffmpeg_bin = MediaProbe.get_ffmpeg_path()
        created_at = datetime.utcnow().isoformat() + "Z"

        # Build filter_complex command
        # For each segment i:
        #   [0:v]trim=start=S:end=E,setpts=PTS-STARTPTS,setpts=PTS*(1/speed)[v_i]
        #   [0:a]atrim=start=S:end=E,asetpts=PTS-STARTPTS,atempo=speed[a_i]
        # Then concat: [v_0][a_0]...[v_N][a_N]concat=n=N:v=1:a=1[outv_raw][outa]
        # Then captions drawtext if present on [outv_raw] -> [outv]

        filter_parts: List[str] = []
        v_stream_labels: List[str] = []
        a_stream_labels: List[str] = []

        for idx, seg in enumerate(timeline.segments):
            v_label = f"v{idx}"
            a_label = f"a{idx}"

            # Video trim & speed
            # setpts = (PTS-STARTPTS)*(1/speed)
            v_filter = f"[0:v]trim=start={seg.source_start}:end={seg.source_end},setpts=PTS-STARTPTS"
            if seg.speed != 1.0:
                v_filter += f",setpts=PTS/{seg.speed}"
            v_filter += f"[{v_label}]"
            filter_parts.append(v_filter)
            v_stream_labels.append(f"[{v_label}]")

            # Audio trim & speed
            if has_audio:
                a_filter = f"[0:a]atrim=start={seg.source_start}:end={seg.source_end},asetpts=PTS-STARTPTS"
                if seg.speed != 1.0:
                    # ffmpeg atempo supports 0.5 to 2.0. Chain if necessary
                    tempo = seg.speed
                    tempo_filters = []
                    while tempo > 2.0:
                        tempo_filters.append("atempo=2.0")
                        tempo /= 2.0
                    while tempo < 0.5:
                        tempo_filters.append("atempo=0.5")
                        tempo /= 0.5
                    tempo_filters.append(f"atempo={round(tempo, 4)}")
                    a_filter += "," + ",".join(tempo_filters)
                a_filter += f"[{a_label}]"
                filter_parts.append(a_filter)
                a_stream_labels.append(f"[{a_label}]")

        # Concat filter
        n_segs = len(timeline.segments)
        concat_inputs = ""
        for i in range(n_segs):
            concat_inputs += v_stream_labels[i]
            if has_audio:
                concat_inputs += a_stream_labels[i]

        a_flag = 1 if has_audio else 0
        concat_out_v = "v_concat" if cls._has_captions(timeline) else "outv"
        concat_out_a = "outa" if has_audio else ""
        
        concat_filter = f"{concat_inputs}concat=n={n_segs}:v=1:a={a_flag}[{concat_out_v}]"
        if has_audio:
            concat_filter += f"[{concat_out_a}]"
        filter_parts.append(concat_filter)

        # Captions overlay (drawtext)
        if cls._has_captions(timeline):
            drawtext_filters = []
            cur_in = concat_out_v
            cap_idx = 0
            for seg in timeline.segments:
                for cap in seg.captions:
                    next_out = f"v_cap_{cap_idx}"
                    # Escape special characters in text
                    escaped_text = cap.text.replace("'", "\\'").replace(":", "\\:")
                    # Y position
                    y_pos = "(h-text_h-30)" if cap.position == "bottom" else ("30" if cap.position == "top" else "(h-text_h)/2")
                    dt = f"drawtext=text='{escaped_text}':fontcolor={cap.color}:fontsize={cap.font_size}:x=(w-text_w)/2:y={y_pos}:enable='between(t,{cap.start_time},{cap.end_time})'"
                    drawtext_filters.append(f"[{cur_in}]{dt}[{next_out}]")
                    cur_in = next_out
                    cap_idx += 1
            # Final rename
            filter_parts.extend(drawtext_filters[:-1])
            # Last drawtext outputs to [outv]
            if drawtext_filters:
                last_dt = drawtext_filters[-1].rsplit("[", 1)[0] + "[outv]"
                filter_parts.append(last_dt)

        filter_complex_str = ";".join(filter_parts)

        # Build command list
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(input_path),
            "-filter_complex", filter_complex_str,
            "-map", "[outv]"
        ]
        if has_audio:
            cmd.extend(["-map", f"[{concat_out_a}]", "-c:a", "aac", "-b:a", "192k"])
        
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path)
        ])

        logger.info(f"Executing FFmpeg render command: {' '.join(cmd)}")

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            logger.error(f"FFmpeg render failed: {proc.stderr}")
            raise IncuBrixError("RENDER_FAILED", f"FFmpeg execution failed: {proc.stderr[-1000:]}")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise IncuBrixError("RENDER_EMPTY", "FFmpeg finished without creating a valid output video.")

        # Probe output
        probe_info = MediaProbe.probe_file(output_path)

        # Compute output SHA256
        hasher = hashlib.sha256()
        with open(output_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        out_sha256 = hasher.hexdigest()

        completed_at = datetime.utcnow().isoformat() + "Z"

        manifest = {
            "manifest_version": "1.0",
            "job_id": job_id,
            "session_id": session_id,
            "input_asset_id": timeline.asset_id,
            "input_sha256": asset["sha256"],
            "timeline_hash": timeline.canonical_hash(),
            "ffmpeg_command": cmd,
            "output_path": str(output_path),
            "output_filename": output_filename,
            "output_sha256": out_sha256,
            "output_duration": probe_info["duration"],
            "output_width": probe_info["width"],
            "output_height": probe_info["height"],
            "output_fps": probe_info["fps"],
            "output_video_codec": probe_info["video_codec"],
            "output_audio_codec": probe_info["audio_codec"],
            "status": "COMPLETED",
            "created_at": created_at,
            "completed_at": completed_at,
        }

        return manifest

    @classmethod
    def _has_captions(cls, timeline: Timeline) -> bool:
        return any(bool(seg.captions) for seg in timeline.segments)
