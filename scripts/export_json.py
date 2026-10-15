# -*- coding: utf-8 -*-
"""
把 analyze.py 算出來的統計結果轉成網頁要讀的 JSON。
這版改成「依節日分組」的結構(每個節日一個獨立區塊,裡面放這個節日
每一年的明細 + 彙總統計),方便網頁做成分頁/手風琴互動。

輸入: data/holiday_stats_detail.csv, data/holiday_stats_summary.csv
輸出: web/data.json

執行: python scripts\\export_json.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
DETAIL_FILE = DATA_DIR / "holiday_stats_detail.csv"
SUMMARY_FILE = DATA_DIR / "holiday_stats_summary.csv"
OUTPUT_FILE = WEB_DIR / "data.json"

CANONICAL_ORDER = [
    "元旦", "春節", "和平紀念日", "兒童節", "清明節",
    "端午節", "中秋節", "國慶日", "台灣光復節", "行憲紀念日",
    "勞動節", "教師節",
]


def order_key(name: str) -> int:
    return CANONICAL_ORDER.index(name) if name in CANONICAL_ORDER else 999


def clean_record(d: dict) -> dict:
    return {k: (None if pd.isna(v) else v) for k, v in d.items()}


if __name__ == "__main__":
    if not DETAIL_FILE.exists() or not SUMMARY_FILE.exists():
        raise SystemExit("找不到統計結果,請先執行 scripts\\analyze.py")

    detail = pd.read_csv(DETAIL_FILE)
    summary = pd.read_csv(SUMMARY_FILE).set_index("holiday_name")

    holidays = []
    for name, group in detail.groupby("holiday_name"):
        years = group.sort_values("year", ascending=False)
        stats = clean_record(summary.loc[name].to_dict()) if name in summary.index else {}
        holidays.append({
            "name": name,
            "sample_count": int(len(group)),
            "stats": stats,
            "years": [clean_record(r) for r in years.to_dict(orient="records")],
        })

    holidays.sort(key=lambda h: (order_key(h["name"]), h["name"]))

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "holiday_count": len(holidays),
        "detail_count": int(len(detail)),
        "holidays": holidays,
    }

    WEB_DIR.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已輸出 {len(holidays)} 種節日、共 {len(detail)} 筆明細 -> {OUTPUT_FILE}")
