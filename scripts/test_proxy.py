"""Smoke-test the Amazon Location proxy (infra/proxy.yaml).

Usage: python scripts/test_proxy.py <ApiUrl>
Checks happy paths for every operation plus the guard rails (outside Japan, bad params, unknown op).
"""
import json
import sys
import urllib.error
import urllib.request

API = sys.argv[1].rstrip("/")
KYOTO = [135.7588, 34.9858]
STOPS = [[135.80, 35.00], [135.70, 34.95], [135.76, 35.05]]


def post(op, body):
    req = urllib.request.Request(f"{API}/{op}", data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json", "origin": "http://localhost:8765"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


cases = [
    ("search-text ok", "search-text", {"QueryText": "京都駅", "BiasPosition": KYOTO}, 200),
    ("isolines ok", "isolines", {"Origin": KYOTO, "Thresholds": {"Time": [1800]}}, 200),
    ("optimize ok", "optimize-waypoints", {"Origin": KYOTO, "Destination": KYOTO,
                                           "Waypoints": [{"Id": str(i), "Position": p} for i, p in enumerate(STOPS)]}, 200),
    ("routes ok", "routes", {"Origin": KYOTO, "Destination": KYOTO, "Waypoints": [{"Position": p} for p in STOPS]}, 200),
    ("matrix ok", "route-matrix", {"Origins": [{"Position": p} for p in [KYOTO] + STOPS],
                                   "Destinations": [{"Position": p} for p in [KYOTO] + STOPS]}, 200),
    ("outside Japan", "isolines", {"Origin": [-122.4, 37.8], "Thresholds": {"Time": [1800]}}, 400),
    ("bad time budget", "isolines", {"Origin": KYOTO, "Thresholds": {"Time": [86400]}}, 400),
    ("too many stops", "optimize-waypoints", {"Origin": KYOTO, "Destination": KYOTO,
                                              "Waypoints": [{"Id": str(i), "Position": KYOTO} for i in range(30)]}, 400),
    ("unknown op", "geocode", {}, 404),
]
fails = 0
for name, op, body, want in cases:
    code, out = post(op, body)
    ok = code == want
    fails += not ok
    detail = out.get("message") or ",".join(list(out)[:3])
    print(f"{'PASS' if ok else 'FAIL'}  {name:18s} {code}  {detail}"[:140])
sys.exit(1 if fails else 0)
