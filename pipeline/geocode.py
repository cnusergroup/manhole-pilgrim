"""Geocode card distribution points with Amazon Location Service (Places API v2).

Strategy per card (results cached in data/geocode_cache.json):
  1. Municipality centroid via Geocode("<pref><municipality>") - used as bias + sanity anchor.
  2. If an address was parsed: Geocode(address). Accept if within MAX_KM of the anchor.
  3. Else / on failure: SearchText(place name + municipality) biased to the anchor (POI search).
  4. Fallback: municipality centroid, flagged precision="municipality".

IntendedUse="Storage" is required because results are persisted and republished.
"""
import json
import math
import pathlib
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import boto3

from parse import PREFS

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARDS = ROOT / "data" / "cards.json"
CACHE = ROOT / "data" / "geocode_cache.json"
OUT = ROOT / "data" / "cards_geo.json"
MAX_KM = 60

client = boto3.client("geo-places", region_name="ap-northeast-1")
lock = threading.Lock()
cache: dict = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def km(a, b) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def cached(key: str, fn):
    with lock:
        if key in cache:
            return cache[key]
    try:
        val = fn()
    except Exception as e:  # keep going; record the failure
        val = {"error": str(e)[:200]}
    with lock:
        cache[key] = val
        if len(cache) % 50 == 0:  # 周期性落盘，中断也不丢进度
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return val


def _item(resp):
    items = resp.get("ResultItems") or []
    if not items:
        return None
    it = items[0]
    cats = [c.get("LocalizedName") or c.get("Name") for c in it.get("Categories", []) if c.get("Primary")]
    return {"pos": it["Position"], "label": it.get("Address", {}).get("Label") or it.get("Title"),
            "region": it.get("Address", {}).get("Region", {}).get("Name"),
            "type": it.get("PlaceType"), "category": cats[0] if cats else None}


def geocode(q: str):
    return cached("g:" + q, lambda: _item(client.geocode(
        QueryText=q, Filter={"IncludeCountries": ["JPN"]}, Language="ja",
        IntendedUse="Storage", MaxResults=1)))


def search(q: str, bias):
    return cached(f"s:{q}@{bias[0]:.2f},{bias[1]:.2f}", lambda: _item(client.search_text(
        QueryText=q, BiasPosition=bias, Filter={"IncludeCountries": ["JPN"]}, Language="ja",
        IntendedUse="Storage", MaxResults=1)))


def clean_name(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"【[^】]*】", "", s)
    s = re.sub(r"^[※・\s]+", "", s)
    return s.strip() or None


def ok(r) -> bool:
    return bool(r) and "pos" in r


def locate(card: dict) -> dict:
    pref, muni = card["pref"], card["municipality"]
    anchor = geocode(f"{pref}{muni}")
    if not ok(anchor) or anchor.get("region") not in (pref, None):
        anchor = geocode(pref)
    a = anchor["pos"] if ok(anchor) else None

    # 县级 / 流域下水道等非市町村发行的卡（编号中段 000），配布点可在县内任意位置
    pref_level = card["id"].split("-")[1:2] == ["000"] or muni in (pref, "流域下水道")

    def plausible(r, expect_pref=pref) -> bool:
        if not ok(r):
            return False
        if pref_level or expect_pref != pref:
            return r.get("region") == expect_pref
        return a is None or km(r["pos"], a) < MAX_KM

    addr = card.get("address")
    if addr:
        # 地址明确写了其他都道府県（跨县配布）时，以地址为准
        named = next((p for p in PREFS if addr.startswith(p)), None)
        q = addr if named else pref + addr
        r = geocode(q)
        if plausible(r, named or pref):
            return {**r, "precision": "address"}

    name = clean_name(card.get("place_name"))
    if name and a:
        r = search(f"{name} {pref if pref_level else muni}", a)
        if plausible(r):
            return {**r, "precision": "poi"}

    if a:
        return {**anchor, "precision": "municipality"}
    return {"precision": "none"}


def main() -> None:
    cards = json.loads(CARDS.read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(locate, cards))
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    out, stats = [], {}
    for c, r in zip(cards, results):
        stats[r["precision"]] = stats.get(r["precision"], 0) + 1
        if "pos" not in r:
            continue
        out.append({**c, "lon": round(r["pos"][0], 6), "lat": round(r["pos"][1], 6),
                    "precision": r["precision"], "geo_label": r.get("label"),
                    "place_category": r.get("category") if r["precision"] == "poi" else None})
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(stats, "written", len(out))


if __name__ == "__main__":
    main()
