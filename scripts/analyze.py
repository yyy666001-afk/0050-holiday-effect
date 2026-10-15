# -*- coding: utf-8 -*-
"""
讀取 data/0050_price.csv + data/holidays.csv,
算出每個「節日」(不是每個補假/調整放假標籤)前後的報酬率統計。

重點:holidays.csv 裡同一個過年,不同年度常常被官方資料標成「小年夜」
「除夕」「初一」「調整放假」等不同備註,如果直接拿備註當名字分組,
樣本數會被拆得亂七八糟。這裡用 canonicalize_holiday_name() 把一個連假
區間裡出現過的所有備註,對應回「春節」「中秋節」這種固定的節日名稱,
再用這個名稱分組,一個節日一年只會有一筆。

「補假」「調整放假」「彈性放假」「週六」「週日」這種純粹是連接用的標籤,
如果區間裡沒有任何真正的節日名稱,整筆會被跳過(不算進統計)。

輸出:
  data/holiday_stats_detail.csv   每個節日、每個年度的明細(已歸類)
  data/holiday_stats_summary.csv  依「節日」彙總(跨年度)的統計量

執行: python scripts\\analyze.py
"""
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRICE_FILE = DATA_DIR / "0050_price.csv"
HOLIDAYS_FILE = DATA_DIR / "holidays.csv"
DETAIL_OUTPUT = DATA_DIR / "holiday_stats_detail.csv"
SUMMARY_OUTPUT = DATA_DIR / "holiday_stats_summary.csv"

WINDOWS = [1, 3, 5]  # 要計算的前後交易日天數窗口

# 節日歸類規則:(關鍵字, 正式名稱),由上到下依序比對,
# 一個連假區間的所有備註只要「包含」某個關鍵字,就歸到對應的節日。
HOLIDAY_RULES = [
    ("元旦", "元旦"),
    ("小年夜", "春節"),
    ("除夕", "春節"),
    ("初一", "春節"),
    ("初二", "春節"),
    ("初三", "春節"),
    ("初四", "春節"),
    ("初五", "春節"),
    ("春節", "春節"),
    ("和平紀念日", "和平紀念日"),
    ("228", "和平紀念日"),
    ("二二八", "和平紀念日"),
    ("兒童節", "兒童節"),
    ("民族掃墓節", "清明節"),
    ("清明", "清明節"),
    ("端午", "端午節"),
    ("中秋", "中秋節"),
    ("國慶", "國慶日"),
    ("光復", "台灣光復節"),
    ("行憲", "行憲紀念日"),
    ("勞動節", "勞動節"),
    ("教師節", "教師節"),
    ("孔子", "教師節"),
]

# 這些備註本身不代表任何節日,只是連假裡的連接日,不能單獨拿來當節日名稱
CONNECTOR_ONLY = {
    "補假", "調整放假", "彈性放假", "週六", "週日", "連假", "", "nan", "nat", "none",
}

# 彙總/網頁顯示時的節日排序(依年曆習慣排序,而不是字母或樣本數)
CANONICAL_ORDER = [
    "元旦", "春節", "和平紀念日", "兒童節", "清明節",
    "端午節", "中秋節", "國慶日", "台灣光復節", "行憲紀念日",
    "勞動節", "教師節",
]


def canonicalize_holiday_name(all_notes: str):
    """把一個連假區間的所有備註,歸類成一個正式節日名稱;
    如果裡面沒有任何真正的節日(只有補假/調整放假/週末這種連接標籤),回傳 None(跳過)。
    """
    notes = [n.strip() for n in str(all_notes).split("|") if n.strip()]
    matched = []
    for note in notes:
        if note.lower() in CONNECTOR_ONLY:
            continue
        for keyword, canonical in HOLIDAY_RULES:
            if keyword in note:
                if canonical not in matched:
                    matched.append(canonical)
                break
    if not matched:
        return None
    if len(matched) == 1:
        return matched[0]
    matched.sort(key=lambda x: CANONICAL_ORDER.index(x) if x in CANONICAL_ORDER else 999)
    return "/".join(matched)


def load_price() -> pd.DataFrame:
    df = pd.read_csv(PRICE_FILE)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").drop_duplicates(subset="Date").reset_index(drop=True)
    return df


def load_holidays():
    df = pd.read_csv(HOLIDAYS_FILE)
    if "all_notes" not in df.columns:
        df["all_notes"] = df["holiday_name"]
    df["canonical_name"] = df["all_notes"].apply(canonicalize_holiday_name)
    skipped = df[df["canonical_name"].isna()]
    df = df.dropna(subset=["canonical_name"]).copy()
    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    return df.sort_values("start_date").reset_index(drop=True), skipped


def analyze_one_holiday(price: pd.DataFrame, row):
    dates = price["Date"]
    closes = price["Close"]

    before_mask = dates < row["start_date"]
    after_mask = dates > row["end_date"]

    if not before_mask.any() or not after_mask.any():
        return None

    prev_idx = dates[before_mask].index[-1]
    next_idx = dates[after_mask].index[0]

    result = {
        "holiday_name": row["canonical_name"],
        "year": row["year"],
        "start_date": row["start_date"].strftime("%Y-%m-%d"),
        "end_date": row["end_date"].strftime("%Y-%m-%d"),
        "prev_trading_date": dates[prev_idx].strftime("%Y-%m-%d"),
        "next_trading_date": dates[next_idx].strftime("%Y-%m-%d"),
        "calendar_days": (row["end_date"] - row["start_date"]).days + 1,
    }

    prev_close = closes[prev_idx]
    next_close = closes[next_idx]
    result["gap_return_pct"] = round((next_close / prev_close - 1) * 100, 3)

    for n in WINDOWS:
        pre_start_idx = prev_idx - n
        if pre_start_idx >= 0:
            pre_start_close = closes[pre_start_idx]
            result[f"pre_{n}d_return_pct"] = round((prev_close / pre_start_close - 1) * 100, 3)
        else:
            result[f"pre_{n}d_return_pct"] = None

        post_end_idx = next_idx + n
        if post_end_idx < len(price):
            post_end_close = closes[post_end_idx]
            result[f"post_{n}d_return_pct"] = round((post_end_close / next_close - 1) * 100, 3)
        else:
            result[f"post_{n}d_return_pct"] = None

    return result


def build_summary(detail: pd.DataFrame) -> pd.DataFrame:
    metric_cols = ["gap_return_pct"] + [f"pre_{n}d_return_pct" for n in WINDOWS] + [f"post_{n}d_return_pct" for n in WINDOWS]

    rows = []
    for name, group in detail.groupby("holiday_name"):
        row = {"holiday_name": name, "sample_count": len(group)}
        for col in metric_cols:
            series = group[col].dropna()
            if series.empty:
                row[f"{col}_mean"] = None
                row[f"{col}_median"] = None
                row[f"{col}_win_rate"] = None
                continue
            row[f"{col}_mean"] = round(series.mean(), 3)
            row[f"{col}_median"] = round(series.median(), 3)
            row[f"{col}_win_rate"] = round((series > 0).mean() * 100, 1)
        rows.append(row)

    summary = pd.DataFrame(rows)
    summary["_order"] = summary["holiday_name"].apply(
        lambda x: CANONICAL_ORDER.index(x) if x in CANONICAL_ORDER else 999
    )
    summary = summary.sort_values(["_order", "holiday_name"]).drop(columns="_order")
    return summary


if __name__ == "__main__":
    if not PRICE_FILE.exists():
        raise SystemExit(f"找不到 {PRICE_FILE},請先執行 fetch_price.py")
    if not HOLIDAYS_FILE.exists():
        raise SystemExit(f"找不到 {HOLIDAYS_FILE},請先執行 fetch_holidays.py")

    price = load_price()
    holidays, skipped = load_holidays()
    print(f"holidays.csv 共 {len(holidays) + len(skipped)} 筆連假區間,"
          f"其中 {len(skipped)} 筆只有補假/調整放假/週末等連接標籤、沒有真正節日,已排除")

    results = []
    out_of_range = 0
    for _, row in holidays.iterrows():
        r = analyze_one_holiday(price, row)
        if r is None:
            out_of_range += 1
            continue
        results.append(r)

    detail = pd.DataFrame(results)
    if detail.empty:
        raise SystemExit("沒有任何連假落在股價資料範圍內,請確認 holidays.csv 跟 0050_price.csv")

    detail.to_csv(DETAIL_OUTPUT, index=False, encoding="utf-8-sig")
    print(f"明細 {len(detail)} 筆(跳過 {out_of_range} 筆資料範圍外的連假) -> {DETAIL_OUTPUT}")

    summary = build_summary(detail)
    summary.to_csv(SUMMARY_OUTPUT, index=False, encoding="utf-8-sig")
    print(f"彙總 {len(summary)} 種節日 -> {SUMMARY_OUTPUT}")
    print(summary[["holiday_name", "sample_count"]].to_string(index=False))
