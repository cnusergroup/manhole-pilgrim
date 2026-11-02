"""Deploy (or update) the Amazon Location proxy stack defined in infra/proxy.yaml.

Usage:
  python scripts/deploy_proxy.py --origins https://main.<appid>.amplifyapp.com,http://localhost:8765
  python scripts/deploy_proxy.py --origins ... --limits '{"search-text":1000,"isolines":500,...}'

Parameters go through a JSON file (no shell quoting of the JSON caps). Prints the API URL for web/config.js.
"""
import argparse
import json
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_LIMITS = {"search-text": 1000, "isolines": 500, "optimize-waypoints": 300, "routes": 600, "route-matrix": 200}


def aws(*args, check=True):
    return subprocess.run(["aws", *args], capture_output=True, text=True, check=check)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origins", required=True, help="comma-separated browser origins allowed by CORS")
    ap.add_argument("--limits", default=json.dumps(DEFAULT_LIMITS), help="JSON object of per-operation daily caps")
    ap.add_argument("--stack", default="manhole-pilgrim-proxy")
    ap.add_argument("--region", default="ap-northeast-1")
    a = ap.parse_args()

    limits = {**DEFAULT_LIMITS, **json.loads(a.limits)}  # every operation must have a cap
    params = [{"ParameterKey": "AllowedOrigins", "ParameterValue": a.origins},
              {"ParameterKey": "DailyLimits", "ParameterValue": json.dumps(limits, separators=(",", ":"))}]
    pfile = pathlib.Path(tempfile.gettempdir()) / f"{a.stack}-params.json"
    pfile.write_text(json.dumps(params), encoding="utf-8")
    common = ["--region", a.region, "--stack-name", a.stack, "--capabilities", "CAPABILITY_IAM",
              "--template-body", (ROOT / "infra" / "proxy.yaml").as_uri().replace("file:///", "file://"),
              "--parameters", pfile.as_uri().replace("file:///", "file://")]

    exists = aws("cloudformation", "describe-stacks", "--region", a.region, "--stack-name", a.stack, check=False).returncode == 0
    r = aws("cloudformation", "update-stack" if exists else "create-stack", *common, check=False)
    if r.returncode != 0 and "No updates are to be performed" not in r.stderr:
        raise SystemExit(r.stderr)
    if r.returncode == 0:
        aws("cloudformation", "wait", "stack-update-complete" if exists else "stack-create-complete",
            "--region", a.region, "--stack-name", a.stack)
    url = aws("cloudformation", "describe-stacks", "--region", a.region, "--stack-name", a.stack, "--query",
              "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue | [0]", "--output", "text").stdout.strip()
    print("daily caps:", limits)
    print("proxyUrl:", url)


if __name__ == "__main__":
    main()
