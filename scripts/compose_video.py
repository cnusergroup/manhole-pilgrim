"""Mux the silent screen recording with the Amazon Polly narration.

Usage: python scripts/compose_video.py <recording.mp4> [--music path.mp3]

- Finds demo t=0 (white slate -> dark cut, see find_start.py)
- Places each voice clip at leadIn + sum(prev durations + gap)  (same formula as web/demo.js)
- Optional background music, ducked to -24 dB under the voice
- Burns nothing in: captions are already rendered by the page; video/narration.srt is a separate soft-sub file
- Output: video/manhole-pilgrim-demo.mp4 (1080p30 H.264 + AAC, < 3 min enforced)
"""
import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from find_start import lumas  # noqa: E402

OUT = ROOT / "video" / "manhole-pilgrim-demo.mp4"
TAIL = 2.8  # 最后一句之后保留的秒数


def slate_cut(path: str) -> float:
    data = lumas(path, seconds=40, fps=30)
    for (_, y0), (t1, y1) in zip(data, data[1:]):
        if y0 > 200 and y1 < 120:
            return t1
    raise SystemExit("slate cut not found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("recording")
    ap.add_argument("--music")
    args = ap.parse_args()

    js = (ROOT / "web" / "demo_timing.js").read_text(encoding="utf-8")
    timing = json.loads(js[js.index("{"): js.rindex("}") + 1])
    t0 = slate_cut(args.recording)

    starts, at = [], timing["leadIn"]
    for seg in timing["list"]:
        starts.append((seg["id"], at))
        at += timing["segments"][seg["id"]] + timing["gap"]
    total = starts[-1][1] + timing["segments"][starts[-1][0]] + TAIL
    if total >= 179.5:
        raise SystemExit(f"video would be {total:.1f}s; must stay under 3 minutes")
    print(f"slate cut at {t0:.3f}s, output length {total:.1f}s")

    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{total:.3f}", "-i", args.recording]
    for sid, _ in starts:
        cmd += ["-i", str(ROOT / "video" / "voice" / f"{sid}.mp3")]
    filters, labels = [], []
    for i, (sid, st) in enumerate(starts, start=1):
        ms = int(round(st * 1000))
        filters.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{i}]")
        labels.append(f"[v{i}]")
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[voice]")
    if args.music:
        cmd += ["-stream_loop", "-1", "-i", args.music]
        m = len(starts) + 1
        filters.append(f"[{m}:a]aresample=48000,volume=-24dB,atrim=0:{total:.3f},afade=t=out:st={total - 2.5:.3f}:d=2.5[bg]")
        filters.append("[voice][bg]amix=inputs=2:normalize=0:duration=first[aout]")
        amap = "[aout]"
    else:
        amap = "[voice]"
    filters.append(f"[0:v]scale=1920:1080:flags=lanczos,fps=30,fade=t=in:st=0:d=0.5,fade=t=out:st={total - 1.2:.3f}:d=1.2[vout]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", amap,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}", str(OUT)]
    subprocess.run(cmd, check=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
