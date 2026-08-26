"""Replace defense.mp4 audio with your recorded voice track."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VIDEO = ROOT / "docs" / "evidence" / "defense.mp4"
DEFAULT_OUT = ROOT / "docs" / "evidence" / "defense.mp4"
BACKUP = ROOT / "docs" / "evidence" / "defense_dmitry_backup.mp4"


def probe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        text=True,
    ).strip()
    return float(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Swap defense video audio with your recording")
    parser.add_argument("audio", type=Path, help="Your voice MP3/WAV/M4A")
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    if not args.audio.exists():
        raise SystemExit(f"audio not found: {args.audio}")
    if not args.video.exists():
        raise SystemExit(f"video not found: {args.video}")

    v_dur = probe_duration(args.video)
    a_dur = probe_duration(args.audio)
    print(f"video={v_dur:.1f}s audio={a_dur:.1f}s")

    if not args.no_backup and args.out == args.video and not BACKUP.exists():
        shutil.copy2(args.video, BACKUP)
        print(f"backup -> {BACKUP}")

    tmp = args.out.with_suffix(".tmp.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(args.video),
        "-i",
        str(args.audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(tmp),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr[-2000:] if proc.stderr else "ffmpeg failed")

    shutil.move(str(tmp), str(args.out))
    br = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=bit_rate",
            "-of",
            "default=nw=1:nk=1",
            str(args.out),
        ],
        text=True,
    ).strip()
    print(f"saved {args.out} audio_bitrate={br}")


if __name__ == "__main__":
    main()
