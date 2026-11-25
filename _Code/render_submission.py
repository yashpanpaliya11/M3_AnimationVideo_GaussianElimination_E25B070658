"""Rebuild the submission animation from the scene code and student voice-over."""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import ImageDraw

from render_video import BG, INK, PANEL, MUTED, FPS, W, H, frame, text, wrap

SOURCE = Path(__file__).resolve().parent
TIMELINE = json.loads((SOURCE / "Timeline.json").read_text())
ANCHORS = np.array(json.loads((SOURCE / "timing.json").read_text()))
NARRATION = SOURCE / "assets" / "voiceover.m4a"

def render(destination):
    times = np.array([shot["start"] for shot in TIMELINE])
    count = round(ANCHORS[-1, 1] * FPS)
    original_times = np.interp(np.arange(count) / FPS, ANCHORS[:, 1], ANCHORS[:, 0])
    command = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(NARRATION), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", str(destination),
    ]
    with subprocess.Popen(command, stdin=subprocess.PIPE) as process:
        for original_time in original_times:
            shot = np.searchsorted(times, original_time, side="right") - 1
            im = frame(shot, original_time - times[shot], TIMELINE[shot]["duration"])
            d = ImageDraw.Draw(im)
            d.rectangle((0, 931, W, H), fill=BG)
            d.rectangle((99, 30, 524, 112), fill=BG)
            d.rounded_rectangle((100, 42, 178, 94), radius=16, fill=INK)
            text(d, (139, 68), "M3", 23, PANEL, True, "mm")
            text(d, (197, 68), "LINEAR ALGEBRA", 23, INK, True, "lm")
            if shot == len(TIMELINE)-1:
                d.rectangle((1090, 398, 1830, 798), fill=BG)
                wrap(d, "OpenAI Codex assisted with the script, example, animation and supporting documents. Animation produced with Pillow and FFmpeg. No music or stock visuals.",
                     1090, 403, 695, 32, MUTED)
            process.stdin.write(im.tobytes())
        process.stdin.close()
        if process.wait():
            raise RuntimeError("FFmpeg failed to render the submission.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=SOURCE.parent / "Rebuilt_Video.mp4")
    render(parser.parse_args().output)
