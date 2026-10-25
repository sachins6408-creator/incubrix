import pytest
import os
import subprocess
from pathlib import Path
from incubrix.core.config import settings

@pytest.fixture(scope="session")
def test_video_path(tmp_path_factory) -> str:
    """
    Generates a real 10-second test video with video and audio streams using ffmpeg.
    Guarantees test suite independence from external files.
    """
    temp_dir = tmp_path_factory.mktemp("media")
    video_file = temp_dir / "synthetic_test_video.mp4"

    ffmpeg_bin = settings.FFMPEG_PATH
    # Generate 10 seconds of test video with test audio tone
    cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "lavfi", "-i", "testsrc=duration=10:size=640x360:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=10",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(video_file)
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return str(video_file)
