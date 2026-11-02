"""Find when the scripted demo starts inside a screen recording.

Record with ?demo=1&wait: the page holds a white slate until window.__demoGo() is called, and cuts to
the dark stage at demo t=0. We find that cut from per-frame mean luma (ffmpeg signalstats).

Usage: python scripts/find_start.py <recording.mp4>  -> prints the demo t=0 offset in seconds
"""
import re
import subprocess
import sys


def lumas(path: str, seconds: float = 20, fps: int = 10):
    cmd = ["ffmpeg", "-v", "info", "-t", str(seconds), "-i", path,
           "-vf", f"fps={fps},scale=192:-1,signalstats,metadata=print:key=lavfi.signalstats.YAVG", "-f", "null", "-"]
    err = subprocess.run(cmd, capture_output=True, text=True).stderr
    times = [float(x) for x in re.findall(r"pts_time:([\d.]+)", err)]
    ys = [float(x) for x in re.findall(r"YAVG=([\d.]+)", err)]
    return list(zip(times, ys))


def main() -> None:
    """With ?demo=1&wait the page shows a white slate until the demo starts; t=0 is the white→dark cut."""
    path = sys.argv[1]
    data = lumas(path, seconds=40, fps=30)
    for (t0, y0), (t1, y1) in zip(data, data[1:]):
        if y0 > 200 and y1 < 120:
            print(f"{t1:.3f}")
            return
    sys.exit("slate cut not found")


if __name__ == "__main__":
    main()
