# -*- coding: utf-8 -*-
"""
把股價轉成 web/price.json,給前端 K 線圖讀取。
優先使用 data/0050_price_adj.csv(還原股價,線才會連續、沒有除息缺口);
如果這個檔案不存在(例如還沒重跑 fetch_price.py),自動退回用 data/0050_price.csv(原始價)。

輸出格式用「欄位陣列」而不是「每天一個物件」,檔案可以小一點:
{
  "dates": ["2003-06-30", ...],
  "o": [...], "h": [...], "l": [...], "c": [...],
  "v": [9930000, ...],   # 股數(前端會除以 1000 換算成「張」)
  "adjusted": true/false  # 讓前端知道現在顯示的是不是還原股價,可以顯示提示
}

執行: python scripts\\export_price_json.py
"""
import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
ADJ_FILE = DATA_DIR / "0050_price_adj.csv"
RAW_FILE = DATA_DIR / "0050_price.csv"
OUTPUT_FILE = WEB_DIR / "price.json"

if __name__ == "__main__":
    if ADJ_FILE.exists():
        price_file, adjusted = ADJ_FILE, True
    elif RAW_FILE.exists():
        price_file, adjusted = RAW_FILE, False
        print("找不到還原股價 0050_price_adj.csv,先用原始價代替。"
              "重跑 fetch_price.py 就會補上還原價,K 線圖到時會自動換成連續版本。")
    else:
        raise SystemExit(f"找不到 {ADJ_FILE} 也找不到 {RAW_FILE},請先執行 fetch_price.py")

    df = pd.read_csv(price_file)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").drop_duplicates(subset="Date").reset_index(drop=True)

    payload = {
        "dates": df["Date"].dt.strftime("%Y-%m-%d").tolist(),
        "o": df["Open"].round(2).tolist(),
        "h": df["High"].round(2).tolist(),
        "l": df["Low"].round(2).tolist(),
        "c": df["Close"].round(2).tolist(),
        "v": df["Volume"].fillna(0).astype(int).tolist() if "Volume" in df.columns else [0] * len(df),
        "adjusted": adjusted,
    }

    WEB_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_kb = OUTPUT_FILE.stat().st_size / 1024
    tag = "還原股價" if adjusted else "原始股價(尚未還原)"
    print(f"已輸出 {len(df)} 筆 K 線資料({tag},{df['Date'].min().date()} ~ {df['Date'].max().date()}) "
          f"-> {OUTPUT_FILE} ({size_kb:.0f} KB)")
