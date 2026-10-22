#!/usr/bin/env python3
"""Build, test and record the real walkthrough at 1600x1000, then encode a shareable H.264 MP4."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headed", action="store_true", help="show Chromium while recording")
    parser.add_argument("--slow-ms", type=int, default=1200)
    parser.add_argument("--step-ms", type=int, default=2000)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/demo/demo-walkthrough.mp4")
    args = parser.parse_args()
    if args.slow_ms < 0 or args.step_ms < 0:
        parser.error("recording delays must be nonnegative")
    ffmpeg = shutil.which("ffmpeg")
    npm = shutil.which("npm")
    if not ffmpeg or not npm:
        parser.error("FFmpeg and Node 22 LTS/npm must be installed and on PATH")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = ROOT / "e2e/artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    capture = Path(tempfile.mkdtemp(prefix="recording-", dir=artifacts))
    env = {**os.environ, "E2E_RECORD": "1", "E2E_HEADED": "1" if args.headed else "0",
           "E2E_WIDTH": "1600", "E2E_HEIGHT": "1000", "E2E_SLOW_MO_MS": str(args.slow_ms),
           "E2E_STEP_PAUSE_MS": str(args.step_ms), "E2E_ARTIFACTS_DIR": str(capture)}
    subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True, timeout=180)
    subprocess.run([sys.executable, "-m", "pytest", "e2e/test_walkthrough.py", "-q", "-s"],
                   cwd=ROOT, env=env, check=True, timeout=240)
    videos = list((capture / "video").glob("*.webm"))
    if len(videos) != 1:
        raise RuntimeError(f"Expected one completed recording, found {len(videos)} in {capture}")
    temporary = output.with_name(output.stem + ".partial.mp4")
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(videos[0]),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-an", "-movflags", "+faststart", str(temporary)], check=True, timeout=180)
    temporary.replace(output)
    shutil.copyfile(capture / "03-list.png", output.with_name(output.stem + "-poster.png"))
    shutil.copyfile(capture / "steps.md", output.with_name(output.stem + "-steps.md"))
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        info = subprocess.check_output([ffprobe, "-v", "error", "-select_streams", "v:0",
                  "-show_entries", "stream=codec_name,width,height,pix_fmt:format=duration,size",
                  "-of", "json", str(output)], text=True)
        print(info)
        video = json.loads(info)["streams"][0]
        if (video["width"], video["height"], video["codec_name"]) != (1600, 1000, "h264"):
            raise RuntimeError("Unexpected recording format")
    print(f"Recorded: {output} ({output.stat().st_size:,} bytes)")
    print(f"Source video and test screenshots: {capture}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
