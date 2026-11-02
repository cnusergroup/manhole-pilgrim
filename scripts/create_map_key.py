"""Create the browser API key for map tiles only (Amazon Location Maps), with referer restriction and an expiry.

Usage: python scripts/create_map_key.py --name manhole-pilgrim-tiles --referers https://main.<appid>.amplifyapp.com/*,http://localhost:8765/* --expires 2026-12-31
Prints the key to paste into web/config.js (apiKey). Places/Routes go through the proxy, so this key cannot call them.
"""
import argparse
import json
import subprocess


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="manhole-pilgrim-tiles")
    ap.add_argument("--referers", required=True)
    ap.add_argument("--expires", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--region", default="ap-northeast-1")
    a = ap.parse_args()
    restrictions = {
        "AllowActions": ["geo-maps:GetTile"],
        "AllowResources": [f"arn:aws:geo-maps:{a.region}::provider/default"],
        "AllowReferers": a.referers.split(","),
    }
    out = subprocess.run(["aws", "location", "create-key", "--region", a.region, "--key-name", a.name,
                          "--expire-time", f"{a.expires}T23:59:59Z", "--restrictions", json.dumps(restrictions),
                          "--query", "Key", "--output", "text"], capture_output=True, text=True, check=True)
    print(out.stdout.strip())


if __name__ == "__main__":
    main()
