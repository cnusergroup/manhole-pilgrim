"""How many manhole cards are within a 1-hour drive of Japan's main tourist hubs? (uses the proxy's CalculateIsolines)

Usage: python scripts/hub_reach.py <proxyUrl>
"""
import json
import pathlib
import sys
import urllib.request

API = sys.argv[1].rstrip("/")
ROOT = pathlib.Path(__file__).resolve().parent.parent
HUBS = {  # 主要车站坐标
    "Tokyo Station": [139.7671, 35.6812], "Osaka Station": [135.4959, 34.7025], "Kyoto Station": [135.7588, 34.9858],
    "Sapporo Station": [141.3502, 43.0693],  # road-snapped point just outside the station building
    "Hakata Station": [130.4207, 33.5897], "Hiroshima Station": [132.4757, 34.3976],
    "Nagoya Station": [136.8815, 35.1709], "Naha (Kokusai-dori)": [127.6845, 26.2152],
}
cards = json.loads((ROOT / "web" / "data" / "cards.geojson").read_text(encoding="utf-8"))["features"]


def inside(pt, ring):
    x, y, ins = pt[0], pt[1], False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            ins = not ins
    return ins


def in_polys(pt, polys):
    return any(inside(pt, p[0]) and not any(inside(pt, h) for h in p[1:]) for p in polys)


only = sys.argv[2:]  # optional: hub name prefixes to run
for name, pos in HUBS.items():
    if only and not name.startswith(tuple(only)):
        continue
    req = urllib.request.Request(f"{API}/isolines", method="POST", headers={"content-type": "application/json"},
                                 data=json.dumps({"Origin": pos, "Thresholds": {"Time": [3600]}}).encode())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            iso = json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"{name:22s} error {e.code}: {e.read()[:100]}")
        continue
    polys = [g.get("Polygon") or g.get("MultiPolygon") for i in iso["Isolines"] for g in i["Geometries"]]
    polys = [p for p in polys if p]
    hits = [f for f in cards if in_polys(f["geometry"]["coordinates"], polys)]
    munis = len({(f["properties"]["pref"], f["properties"]["muni"]) for f in hits})
    sewer = sum(f["properties"]["ptype"] == "sewer" for f in hits)
    print(f"{name:22s} {len(hits):4d} cards  {munis:3d} issuers  {sewer:3d} at sewage plants")
