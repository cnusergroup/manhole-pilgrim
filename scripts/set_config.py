"""Write apiKey / proxyUrl into web/config.js.  Usage: python scripts/set_config.py --key-file <file> --proxy <url>"""
import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--key-file")
ap.add_argument("--proxy")
a = ap.parse_args()
cfg = ROOT / "web" / "config.js"
s = cfg.read_text(encoding="utf-8")
if a.key_file:
    key = pathlib.Path(a.key_file).read_text(encoding="utf-8").strip()
    s = re.sub(r'apiKey: "[^"]*"', f'apiKey: "{key}"', s)
if a.proxy:
    if "proxyUrl:" in s:
        s = re.sub(r'proxyUrl: "[^"]*"', f'proxyUrl: "{a.proxy}"', s)
    else:
        s = s.replace("  mapStyle:", f'  proxyUrl: "{a.proxy}",\n  mapStyle:', 1)
cfg.write_text(s, encoding="utf-8")
print(re.sub(r'(v1\.public\.\w{12})[^"]*', r"\1…", s))
