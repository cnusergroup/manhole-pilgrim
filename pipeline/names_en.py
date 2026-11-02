"""English names for prefectures and issuing municipalities, via Amazon Location Places Geocode (Language=en).

Writes web/data/names_en.json: {"pref": {"北海道": "Hokkaido", ...}, "muni": {"北海道|札幌市": "Sapporo-shi", ...}}
so the map can be searched and read in English. Results are cached in data/names_en_cache.json.
IntendedUse=Storage because the names are stored and republished.
"""
import json
import pathlib
import re
from concurrent.futures import ThreadPoolExecutor

import boto3

ROOT = pathlib.Path(__file__).resolve().parent.parent
GEO = ROOT / "web" / "data" / "cards.geojson"
OUT = ROOT / "web" / "data" / "names_en.json"
CACHE = ROOT / "data" / "names_en_cache.json"

PREF_EN = ["Hokkaido", "Aomori", "Iwate", "Miyagi", "Akita", "Yamagata", "Fukushima", "Ibaraki", "Tochigi", "Gunma",
           "Saitama", "Chiba", "Tokyo", "Kanagawa", "Niigata", "Toyama", "Ishikawa", "Fukui", "Yamanashi", "Nagano",
           "Gifu", "Shizuoka", "Aichi", "Mie", "Shiga", "Kyoto", "Osaka", "Hyogo", "Nara", "Wakayama",
           "Tottori", "Shimane", "Okayama", "Hiroshima", "Yamaguchi", "Tokushima", "Kagawa", "Ehime", "Kochi", "Fukuoka",
           "Saga", "Nagasaki", "Kumamoto", "Oita", "Miyazaki", "Kagoshima", "Okinawa"]
# 不是市町村的发行主体
SPECIAL = {"流域下水道": "Regional sewerage", "東京23区": "Tokyo 23 Wards", "UR都市機構": "UR Urban Renaissance Agency",
           "日本下水道事業団": "Japan Sewage Works Agency"}

client = boto3.client("geo-places", region_name="ap-northeast-1")
cache: dict = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def english(pref: str, muni: str):
    key = f"{pref}|{muni}"
    if key in cache:
        return key, cache[key]
    r = client.geocode(QueryText=f"{pref}{muni}", Filter={"IncludeCountries": ["JPN"]}, Language="en",
                       MaxResults=1, IntendedUse="Storage")
    it = (r.get("ResultItems") or [{}])[0]
    a = it.get("Address", {})
    # 只接受市町村级别的结果，避免把整个都道府县的名字当成市町村名
    name = a.get("Locality") if it.get("PlaceType") in ("Locality", "District", "SubDistrict") else None
    if not name and it.get("PlaceType") == "SubRegion":
        name = a.get("SubRegion", {}).get("Name")
    cache[key] = name
    return key, name


def main() -> None:
    feats = json.loads(GEO.read_text(encoding="utf-8"))["features"]
    pairs = sorted({(f["properties"]["pref"], f["properties"]["muni"]) for f in feats})
    prefs = sorted({p for p, _ in pairs}, key=lambda p: next(f["properties"]["pref_code"] for f in feats if f["properties"]["pref"] == p))
    pref_en = {}
    for p in prefs:
        code = int(next(f["properties"]["pref_code"] for f in feats if f["properties"]["pref"] == p))
        pref_en[p] = PREF_EN[code - 1]

    todo = []
    muni_en = {}
    for p, m in pairs:
        base = re.sub(r"\s+", "", m)
        if base in SPECIAL:
            muni_en[f"{p}|{m}"] = SPECIAL[base]
        elif base in (p, p[:-1]) or base.startswith(p):   # 县级发行，例如「長野県（流域下水道・C001）」
            muni_en[f"{p}|{m}"] = f"{pref_en[p]} Prefecture" + (" regional sewerage" if "流域" in base else "")
        else:
            todo.append((p, m))
    with ThreadPoolExecutor(max_workers=8) as ex:
        for key, name in ex.map(lambda pm: english(*pm), todo):
            if name:
                muni_en[key] = name
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    OUT.write_text(json.dumps({"pref": pref_en, "muni": muni_en}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    missing = [f"{p}{m}" for p, m in pairs if f"{p}|{m}" not in muni_en]
    print(f"issuers {len(pairs)}, english {len(muni_en)}, missing {len(missing)}: {missing[:15]}")


if __name__ == "__main__":
    main()
