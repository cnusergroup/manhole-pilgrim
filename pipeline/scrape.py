"""Fetch manhole card listings from GKP (gk-p.jp/mhcard) per prefecture.

Raw HTML is cached under data/raw/ so parsing can be re-run offline and the
source site is hit at most once per prefecture (1.5s polite delay).
"""
import pathlib
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
URL = "https://www.gk-p.jp/mhcard/?pref={code}"
UA = "manhole-pilgrim-hackathon/0.1 (research; contact via GitHub repo)"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = UA
    for n in range(1, 48):
        code = f"{n:02d}"
        out = RAW / f"pref{code}.html"
        if out.exists() and out.stat().st_size > 10_000:
            continue
        r = session.get(URL.format(code=code), timeout=30)
        r.raise_for_status()
        r.encoding = "utf-8"
        out.write_text(r.text, encoding="utf-8")
        print(code, len(r.text))
        time.sleep(1.5)


if __name__ == "__main__":
    main()
