"""Parse cached GKP prefecture pages into a flat cards.json.

One record per card row. Distribution address is extracted heuristically from
the 配布場所 cell (lines before the 問合せ先 block).
"""
import json
import pathlib
import re

from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "cards.json"

PREFS = ["北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県",
         "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
         "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
         "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
         "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"]

ADDR_RE = re.compile(r"(都|道|府|県|市|区|町|村|郡).*\d|[0-9０-９]+[-－ー‐丁番]")
PHONE_RE = re.compile(r"(電話|TEL|ＴＥＬ|Tel)\s*[:：]?\s*([0-9０-９\-－ー（）()]+)")
CONTACT_RE = re.compile(r"[（(]\s*問合せ先|[（(]\s*問い合わせ先|[（(]\s*お問合せ")


def lines_of(td) -> list[str]:
    for br in td.find_all("br"):
        br.replace_with("\n")
    return [re.sub(r"\s+", " ", s).strip() for s in td.get_text().split("\n") if s.strip()]


def pick_address(lines: list[str], pref: str) -> str | None:
    for ln in lines:
        s = re.sub(r"^(住所|所在地)\s*[:：]\s*", "", ln)
        if s.startswith(("※", "電話", "TEL", "【")):
            continue
        if s.startswith(pref) or (ADDR_RE.search(s) and not PHONE_RE.search(s) and len(s) < 80):
            return s
    return None


def parse_file(path: pathlib.Path) -> list[dict]:
    code = path.stem.replace("pref", "")
    pref = PREFS[int(code) - 1]
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    table = soup.select_one("table.table1")
    if table is None:
        return []
    cards = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 7:
            continue
        muni_lines = lines_of(tds[0])
        muni = muni_lines[0] if muni_lines else ""
        m = re.search(r"[（(]\s*([A-Za-z0-9]+)\s*[)）]", tds[0].get_text())
        series_code = m.group(1) if m else None
        if m:
            muni = re.sub(r"[（(]\s*[A-Za-z0-9]+\s*[)）]", "", muni).strip()
        img = tds[1].find("img")
        img_src = img["src"].replace("http://", "https://") if img and img.get("src") else None
        sm = re.search(r"(\d+)", tds[2].get_text())
        series = int(sm.group(1)) if sm else None
        date = tds[3].get_text(strip=True)

        link = tds[4].find("a")
        place_url = link["href"] if link and link.get("href", "").startswith("http") else None
        dist_lines = lines_of(tds[4])
        main_lines = []
        for ln in dist_lines:
            if CONTACT_RE.search(ln):
                break
            main_lines.append(ln)
        place_name = main_lines[0] if main_lines else None
        address = pick_address(main_lines[1:], pref) or pick_address(main_lines[:1], pref)
        if address == place_name and len(main_lines) > 1:
            place_name = main_lines[0]
        ph = PHONE_RE.search(" ".join(main_lines))

        hours = " / ".join(lines_of(tds[5]))
        stock = " ".join(lines_of(tds[6]))
        img_id = pathlib.Path(img_src).stem if img_src else f"{code}-{len(cards)}"
        cards.append({
            "id": img_id,
            "pref_code": code,
            "pref": pref,
            "municipality": muni,
            "card_code": series_code,
            "series": series,
            "issued": date,
            "image": img_src,
            "place_name": place_name,
            "place_url": place_url,
            "address": address,
            "phone": ph.group(2) if ph else None,
            "hours": hours,
            "stock": stock,
            "distribution_raw": " / ".join(dist_lines),
        })
    return cards


def main() -> None:
    all_cards = []
    for p in sorted(RAW.glob("pref*.html")):
        cs = parse_file(p)
        all_cards.extend(cs)
        print(p.stem, len(cs))
    # dedupe ids
    seen = {}
    for c in all_cards:
        if c["id"] in seen:
            seen[c["id"]] += 1
            c["id"] = f'{c["id"]}_{seen[c["id"]]}'
        else:
            seen[c["id"]] = 0
    OUT.write_text(json.dumps(all_cards, ensure_ascii=False, indent=1), encoding="utf-8")
    no_addr = [c for c in all_cards if not c["address"]]
    print("total", len(all_cards), "missing address", len(no_addr))
    for c in no_addr[:15]:
        print("  ", c["pref"], c["municipality"], "|", c["distribution_raw"][:120])


if __name__ == "__main__":
    main()
