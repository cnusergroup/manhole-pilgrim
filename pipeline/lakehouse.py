"""Load cards into an Apache Iceberg table on S3 (via Amazon Athena) and export the web GeoJSON from it.

  data/cards_enriched.jsonl ──► s3://<bucket>/raw/cards/              (Athena external JSON table: raw_cards)
                               │  MERGE INTO cards ... (one commit per series on backfill, one per refresh after)
                               ▼
                         s3://<bucket>/warehouse/cards/               (Iceberg table: manhole_pilgrim.cards)
                               │  SELECT ... (Athena)
                               ▼
                         web/data/cards.geojson + web/data/lake.json  (snapshot history for the UI footer)

Usage:
  python pipeline/lakehouse.py --backfill   # first run: replays history, 1 Iceberg snapshot per series
  python pipeline/lakehouse.py              # refresh: single MERGE of the latest scrape
"""
import argparse
import csv
import io
import json
import pathlib
import time

import boto3

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGION = "ap-northeast-1"
ACCOUNT = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
BUCKET = f"manhole-pilgrim-lake-{ACCOUNT}"
DB = "manhole_pilgrim"
SRC = ROOT / "data" / "cards_enriched.jsonl"
WEB = ROOT / "web" / "data"

s3 = boto3.client("s3", region_name=REGION)
athena = boto3.client("athena", region_name=REGION)

COLS = [  # name, athena type
    ("id", "string"), ("pref_code", "string"), ("pref", "string"), ("muni", "string"), ("code", "string"),
    ("series", "int"), ("issued", "string"), ("image", "string"), ("place", "string"), ("place_url", "string"),
    ("address", "string"), ("hours", "string"), ("ended", "boolean"), ("geo_precision", "string"),
    ("ptype", "string"), ("geo_pref", "string"), ("lon", "double"), ("lat", "double"),
]


def q(sql: str, fetch: bool = False):
    """Run an Athena query and wait. Returns rows (list[dict]) when fetch=True."""
    qid = athena.start_query_execution(
        QueryString=sql, QueryExecutionContext={"Database": DB if "CREATE DATABASE" not in sql else "default"},
        ResultConfiguration={"OutputLocation": f"s3://{BUCKET}/athena-results/"},
    )["QueryExecutionId"]
    while True:
        st = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        if st["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if st["State"] != "SUCCEEDED":
        raise RuntimeError(f"{st['State']}: {st.get('StateChangeReason')}\n{sql[:300]}")
    if not fetch:
        return None
    # 结果 CSV 直接从 S3 读，避免分页
    body = s3.get_object(Bucket=BUCKET, Key=f"athena-results/{qid}.csv")["Body"].read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(body)))


def ensure_infra() -> None:
    try:
        s3.head_bucket(Bucket=BUCKET)
    except Exception:
        s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION})
        s3.put_public_access_block(Bucket=BUCKET, PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    q(f"CREATE DATABASE IF NOT EXISTS {DB}")
    cols = ",\n  ".join(f"`{n}` {t}" for n, t in COLS)
    q(f"""CREATE EXTERNAL TABLE IF NOT EXISTS raw_cards (
  {cols})
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://{BUCKET}/raw/cards/'""")
    q(f"""CREATE TABLE IF NOT EXISTS cards (
  {cols},
  `issued_date` date,
  `updated_at` timestamp)
PARTITIONED BY (pref_code)
LOCATION 's3://{BUCKET}/warehouse/cards/'
TBLPROPERTIES ('table_type'='ICEBERG', 'format'='parquet', 'write_compression'='zstd')""")


def upload_raw() -> None:
    s3.upload_file(str(SRC), BUCKET, "raw/cards/cards.jsonl")


def merge(where: str = "TRUE") -> None:
    names = [n for n, _ in COLS]
    upd = ", ".join(f"{n} = r.{n}" for n in names if n != "id")
    ins_cols = ", ".join(names + ["issued_date", "updated_at"])
    ins_vals = ", ".join([f"r.{n}" for n in names] + ["r.issued_date", "r.updated_at"])
    q(f"""MERGE INTO cards t
USING (SELECT *, TRY(CAST(date_parse(issued, '%Y/%m/%d') AS date)) AS issued_date,
              CAST(current_timestamp AS timestamp(6)) AS updated_at
       FROM raw_cards WHERE {where}) r
ON t.id = r.id
WHEN MATCHED THEN UPDATE SET {upd}, issued_date = r.issued_date, updated_at = r.updated_at
WHEN NOT MATCHED THEN INSERT ({ins_cols}) VALUES ({ins_vals})""")


def export() -> None:
    rows = q("SELECT * FROM cards ORDER BY pref_code, series, id", fetch=True)
    feats = []
    for r in rows:
        p = {n: r[n] for n, _ in COLS if n not in ("lon", "lat")}
        p["series"] = int(p["series"]) if p["series"] else None
        p["ended"] = p["ended"] == "true"
        p["precision"] = p.pop("geo_precision")
        p["year"] = int(r["issued"][:4]) if r["issued"][:4].isdigit() else None
        for k, v in list(p.items()):
            if v == "":
                p[k] = None
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
                      "properties": p})
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "cards.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                                                  ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    snaps = q('SELECT committed_at, snapshot_id, operation, summary FROM "cards$snapshots" ORDER BY committed_at', fetch=True)
    lake = {
        "table": f"{DB}.cards", "format": "Apache Iceberg (Parquet, zstd) on Amazon S3, queried with Amazon Athena",
        "rows": len(feats), "snapshots": len(snaps),
        "latest": {"committed_at": snaps[-1]["committed_at"], "snapshot_id": snaps[-1]["snapshot_id"]} if snaps else None,
    }
    (WEB / "lake.json").write_text(json.dumps(lake, ensure_ascii=False, indent=1), encoding="utf-8")
    print("exported", len(feats), "features;", len(snaps), "snapshots")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true", help="replay history: one Iceberg commit per series")
    args = ap.parse_args()
    ensure_infra()
    upload_raw()
    if args.backfill:
        max_s = int(q("SELECT max(series) AS m FROM raw_cards", fetch=True)[0]["m"])
        for s in range(1, max_s + 1):
            merge(f"series = {s}")
            print("committed series", s)
    merge()  # 全量 MERGE：捕获停发、地址变更等
    export()


if __name__ == "__main__":
    main()
