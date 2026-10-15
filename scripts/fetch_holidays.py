# -*- coding: utf-8 -*-
"""
用「固定規則」產生台灣節日的日期區間,取代直接依賴政府開放資料
(政府資料集常常只到 2017 年、且逐年格式不一致)。

設計原則:
  - 陽曆固定節日(元旦、228、兒童節、清明、勞動節、國慶、光復節、行憲紀念日):
    日期每年固定,直接寫死規則。
  - 陰曆節日(春節初一、端午、中秋):用 lunarcalendar 套件,把農曆日期換算成
    每一年對應的陽曆日期。
  - 不處理「補假/調整放假/彈性放假」這種行政公告細節。analyze.py 只需要
    「這個節日落在哪天(或哪個區間)」,就能往前往後抓最近的交易日計算報酬率,
    補假規則本身不影響這個分析目的。
  - 春節預設抓「除夕 ~ 初三」共 4 天當作區間(多數年份的基本放假區間),
    如果該年政府有多放 1-2 天,對分析結果影響很小,可忽略。

輸出格式跟舊版 holidays.csv 完全相容(year, holiday_name, all_notes,
start_date, end_date),可以直接餵給現有的 analyze.py,不用改 analyze.py。

執行: python scripts\\fetch_holidays.py [起始年] [結束年]
預設: 2003 ~ 今年+1
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from lunarcalendar import Converter, Lunar

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "holidays.csv"

# ---------- 陽曆固定節日:(月, 日, 節日名稱) ----------
FIXED_SOLAR_HOLIDAYS = [
    (1, 1, "元旦"),
    (2, 28, "和平紀念日"),
    (4, 4, "兒童節"),
    (4, 5, "清明節"),       # 民族掃墓節,現行多半固定 4/5(有些年份隨節氣微調,誤差一天內)
    (5, 1, "勞動節"),
    (10, 10, "國慶日"),
]

# ---------- 陰曆節日:(農曆月, 農曆日, 節日名稱, 區間起點偏移天數, 區間長度天數) ----------
# 偏移/長度是以「農曆當天」為基準往前後延伸的天數,抓常見放假區間
LUNAR_HOLIDAYS = [
    (1, 1, "春節", -1, 4),   # 除夕(初一前一天) ~ 初三,共 4 天
    (5, 5, "端午節", 0, 1),
    (8, 15, "中秋節", 0, 1),
]


def build_fixed_holidays(years):
    rows = []
    for year in years:
        for month, day, name in FIXED_SOLAR_HOLIDAYS:
            try:
                d = date(year, month, day)
            except ValueError:
                continue
            rows.append({
                "year": year,
                "holiday_name": name,
                "all_notes": name,
                "start_date": d.isoformat(),
                "end_date": d.isoformat(),
            })
    return rows


def build_lunar_holidays(years):
    rows = []
    for year in years:
        for lunar_month, lunar_day, name, offset, length in LUNAR_HOLIDAYS:
            try:
                solar = Converter.Lunar2Solar(Lunar(year, lunar_month, lunar_day, False))
            except Exception:
                continue  # 某些年份套件資料範圍外，跳過
            base = date(solar.year, solar.month, solar.day)
            start = base + timedelta(days=offset)
            end = start + timedelta(days=length - 1)
            rows.append({
                "year": year,
                "holiday_name": name,
                "all_notes": name,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            })
    return rows


if __name__ == "__main__":
    start_year = int(sys.argv[1]) if len(sys.argv) > 1 else 2003
    end_year = int(sys.argv[2]) if len(sys.argv) > 2 else date.today().year + 1
    years = range(start_year, end_year + 1)

    rows = build_fixed_holidays(years) + build_lunar_holidays(years)
    df = pd.DataFrame(rows).sort_values(["year", "start_date"]).reset_index(drop=True)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"產生 {len(df)} 筆節日資料({start_year}~{end_year}) -> {OUTPUT_FILE}")
    print(df["holiday_name"].value_counts())
