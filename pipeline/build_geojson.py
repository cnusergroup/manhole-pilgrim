"""Turn cards_geo.json into web/data/cards.geojson (+ a small stats.json)."""
import json
import pathlib
import re

from parse import PREFS

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "cards_geo.json"
OUT_DIR = ROOT / "web" / "data"

# 配布点类型：按名称关键词归类（顺序即优先级）
PLACE_TYPES = [
    ("sewer", r"下水|処理場|処分場|汚水|浄化センター|水再生|水環境|浄水|水道|ポンプ場|クリーンセンター|クリーンピア|水みらい|清流センター"),
    ("roadside", r"道の駅"),
    ("museum", r"博物館|資料館|史料館|展示館|美術館|記念館|ミュージアム|ミュジアム|MUSEUM|歴史館|郷土館|文学館|科学館|植物園|家住宅|酒蔵|蔵春閣"),
    ("tourist", r"観光|案内所|インフォメーション|ツーリスト|物産|まちの駅|ビジターセンター|交流館|COMPASS|産業館"),
    ("onsen", r"温泉|保養"),
    ("park", r"公園|アリーナ|体育館|スポーツ|運動|テニス"),
    ("station", r"駅"),
    ("library", r"図書館"),
    ("cityhall", r"市役所|町役場|村役場|区役所|役場|庁舎|市庁|支所|総合事務所|行政センター|役所|総合窓口|営業センター"),
    ("community", r"センター|交流|プラザ|ホール|会館|公民館|劇場|BASE|ベース|広場"),
    ("shop", r"ショップ|SHOP|商店|イオン|店|工房|味噌|組合|ランド"),
]


def place_type(name: str | None, category: str | None) -> str:
    s = name or ""
    for key, pat in PLACE_TYPES:
        if re.search(pat, s):
            return key
    if category:
        if "観光" in category:
            return "tourist"
        if "官庁" in category or "市庁舎" in category:
            return "cityhall"
        if "博物館" in category:
            return "museum"
    return "other"


def main() -> None:
    cards = json.loads(SRC.read_text(encoding="utf-8"))
    feats = []
    for c in cards:
        name = re.sub(r"【[^】]*】", "", c["place_name"] or "").strip() or None
        year = int(c["issued"][:4]) if re.match(r"\d{4}", c["issued"] or "") else None
        ended = "配布終了" in (c["stock"] or "") or "配布終了" in (c["distribution_raw"] or "")
        # 地理编码结果所在的都道府県（用于发现“跨县配布”的卡）
        label = c.get("geo_label") or ""
        geo_pref = next((p for p in PREFS if p in label), None) if c["precision"] != "municipality" else None
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
            "properties": {
                "id": c["id"], "pref": c["pref"], "pref_code": c["pref_code"],
                "muni": c["municipality"], "code": c["card_code"], "series": c["series"],
                "issued": c["issued"], "year": year, "image": c["image"],
                "place": name, "place_url": c["place_url"], "address": c["address"] or c["geo_label"],
                "hours": c["hours"], "ended": ended, "precision": c["precision"],
                "ptype": place_type(name, c.get("place_category")),
                "geo_pref": geo_pref,
            },
        })
    # 数据湖输入：每行一条记录（lakehouse.py 加载进 Iceberg）
    with (ROOT / "data" / "cards_enriched.jsonl").open("w", encoding="utf-8") as fh:
        for f in feats:
            p = dict(f["properties"])
            p["geo_precision"] = p.pop("precision")
            p.pop("year", None)
            p["lon"], p["lat"] = f["geometry"]["coordinates"]
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "cards.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    from collections import Counter
    stats = {
        "total": len(feats),
        "ptype": Counter(f["properties"]["ptype"] for f in feats),
        "series": Counter(f["properties"]["series"] for f in feats),
        "pref": Counter(f["properties"]["pref"] for f in feats),
    }
    (OUT_DIR / "stats.json").write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")
    print(len(feats), dict(stats["ptype"]))


if __name__ == "__main__":
    main()
