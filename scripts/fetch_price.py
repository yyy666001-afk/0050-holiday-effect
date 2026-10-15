"""
抓取並「持續累積」0050 的歷史股價(原始價 + 自算還原股價)。
資料來源:FinMind 開放資料 API(https://finmind.github.io/)

**還原價計算說明**:FinMind 的 TaiwanStockPriceAdj(還原股價)只限付費的 backer/sponsor
會員使用,免費額度打不到(會回 400)。所以這版改成自己算還原價,用兩份免費資料:
  - TaiwanStockDividendResult(除權除息結果表):每次除權息事件的 before_price(除權息前
    收盤參考價)/ after_price(除權息後參考價),兩者相除就是調整比例。
    **注意**:這兩個欄位對 ETF(像 0050)有時候會是 0 或缺值(FinMind 對 ETF 的欄位填寫
    不像一般個股那麼完整),這種情況下改用備援算法:拿我們自己抓到的原始股價,找事件日前一個
    交易日的實際收盤價,搭配這份資料集另外給的股利金額(stock_and_cache_dividend)自己反推
    比例 = (前一日收盤 − 股利金額) ÷ 前一日收盤,一樣可以算出正確的調整比例,不會因為 FinMind
    欄位缺值就漏掉這次事件。
  - TaiwanStockSplitPrice(股票分割價格表):0050 在 2025-06-18 做過一次 1 拆 4,
    同一套比例邏輯處理(分割這份欄位比較穩定,不用備援)。
算法:事件依日期排序,從最新的一天往回算,每遇到一個事件,把「那天之前」的所有歷史價格
乘上這次事件的調整比例,這跟還原股價的標準算法一致。

**無成交日補值**:交易所對完全沒有成交的個股,開高低收會公告為 `--`,FinMind 原始轉成數值 0。
如果直接拿 0 去乘調整比例,還原股價會出現一根砍到接近 0 的假跳空。這版會把這種「收盤價是 0」
的日子,改成沿用前一個有效交易日的收盤價。

輸出三個檔案:
  data/0050_price.csv          原始收盤價(analyze.py 用,增量更新,已補無成交日)
  data/0050_dividend_events.csv 抓到的除權息+分割事件(含用的是哪種算法),留底備查
  data/0050_price_adj.csv      自算還原股價(K 線圖用)

任何一步失敗,都不會讓本地已經存好的資料消失,最多就是這次沒補到新資料。

執行: python scripts\\fetch_price.py
"""
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT = DATA_DIR / "0050_price.csv"
OUTPUT_ADJ = DATA_DIR / "0050_price_adj.csv"
OUTPUT_EVENTS = DATA_DIR / "0050_dividend_events.csv"
STOCK_ID = "0050"
START_DATE = "2003-06-25"
URL = "https://api.finmindtrade.com/api/v4/data"

OVERLAP_DAYS = 10  # 補增量時往回多抓幾個交易日當緩衝


def _request(dataset: str, start_date: str = START_DATE, data_id: str = STOCK_ID) -> list:
    params = {"dataset": dataset, "data_id": data_id, "start_date": start_date}
    resp = requests.get(URL, params=params, timeout=60)
    resp.raise_for_status()
    j = resp.json()
    if j.get("status") != 200:
        raise RuntimeError(f"伺服器訊息: {j.get('msg')}")
    data = j.get("data", [])
    if not data:
        raise RuntimeError("回傳資料是空的")
    return data


def _load_local(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        return df if len(df) else None
    except Exception:
        return None


def _fill_no_trade_days(df: pd.DataFrame) -> pd.DataFrame:
    """把收盤價為 0(當天無公告成交價)的列,用前一個有效交易日的 O/H/L/C 補值。"""
    df = df.sort_values("Date").reset_index(drop=True)
    zero_mask = df["Close"].astype(float) <= 0
    n = int(zero_mask.sum())
    if n:
        for col in ["Open", "High", "Low", "Close"]:
            df.loc[zero_mask, col] = pd.NA
        df[["Open", "High", "Low", "Close"]] = df[["Open", "High", "Low", "Close"]].ffill()
        print(f"[原始價] 發現 {n} 天無公告成交價(當日完全沒有交易),已用前一個有效交易日的收盤價補值")
    return df


# ---------- 原始價:增量更新 ----------
def update_raw_price() -> pd.DataFrame:
    local = _load_local(OUTPUT)

    if local is not None:
        last_date = pd.to_datetime(local["Date"]).max()
        fetch_from = (last_date - pd.Timedelta(days=OVERLAP_DAYS)).strftime("%Y-%m-%d")
        print(f"[原始價] 本地已有 {len(local)} 筆,最新到 {last_date.date()},這次只補 {fetch_from} 之後的增量 ...")
    else:
        fetch_from = START_DATE
        print(f"[原始價] 本地沒有資料,第一次抓全部歷史(從 {START_DATE} 開始)...")

    try:
        raw = _request("TaiwanStockPrice", fetch_from)
    except Exception as e:
        if local is not None:
            print(f"[原始價] 這次抓取失敗({e}),本地既有的 {len(local)} 筆資料維持不變,沒有任何損失。")
            return _fill_no_trade_days(local)
        raise SystemExit(f"[原始價] 第一次抓取就失敗,且本地沒有任何備援資料:{e}")

    new = pd.DataFrame(raw).rename(columns={
        "date": "Date", "open": "Open", "max": "High", "min": "Low",
        "close": "Close", "Trading_Volume": "Volume",
    })[["Date", "Open", "High", "Low", "Close", "Volume"]]

    if local is not None:
        merged = pd.concat([local, new], ignore_index=True)
        merged["Date"] = merged["Date"].astype(str)
        merged = merged.drop_duplicates(subset="Date", keep="last").sort_values("Date").reset_index(drop=True)
    else:
        merged = new.sort_values("Date").reset_index(drop=True)

    merged = _fill_no_trade_days(merged)

    DATA_DIR.mkdir(exist_ok=True)
    merged.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    added = len(merged) - (len(local) if local is not None else 0)
    print(f"[原始價] 新增/更新 {added} 筆,目前共 {len(merged)} 筆,"
          f"區間 {merged['Date'].min()} ~ {merged['Date'].max()} -> {OUTPUT}")
    return merged


# ---------- 除權息 + 分割事件:免費資料集,每次整段重抓(資料量很小) ----------
def fetch_adjustment_events(raw: pd.DataFrame) -> pd.DataFrame | None:
    """raw: 已經補過無成交日的原始股價,拿來在 FinMind 欄位缺值時當備援資料源。"""
    raw_by_date = raw.set_index(pd.to_datetime(raw["Date"]))["Close"].astype(float)
    events = []

    try:
        div = _request("TaiwanStockDividendResult", START_DATE)
        print(f"[調整事件] 除權息事件(FinMind 回傳){len(div)} 筆,逐筆檢查:")
        for row in div:
            date = row["date"]
            before, after = row.get("before_price") or 0, row.get("after_price") or 0
            dividend = row.get("stock_and_cache_dividend") or 0
            ratio, method = None, None

            if before > 0 and after > 0:
                ratio, method = after / before, "FinMind before/after"
            elif dividend > 0:
                # 備援:用我們自己的原始股價,找事件日前一個交易日的實際收盤價來反推比例
                prior = raw_by_date[raw_by_date.index < pd.to_datetime(date)]
                if len(prior):
                    prev_close = prior.iloc[-1]
                    if prev_close > 0:
                        ratio = (prev_close - dividend) / prev_close
                        method = f"備援:前一日收盤{prev_close}−股利{dividend}"

            if ratio is None:
                print(f"  {date}: before={before} after={after} dividend={dividend} -> 無法算出比例,已跳過")
                continue

            print(f"  {date}: ratio={ratio:.5f}({method})")
            events.append({"date": date, "type": "除權息", "ratio": ratio, "method": method})
    except Exception as e:
        print(f"[調整事件] 除權息資料抓取失敗({e}),這部分會被跳過(不影響既有本地資料)")

    try:
        split = _request("TaiwanStockSplitPrice", START_DATE)
        split_n = 0
        for row in split:
            if row.get("stock_id") != STOCK_ID:
                continue
            before, after = row.get("before_price"), row.get("after_price")
            if before and after and before > 0:
                events.append({"date": row["date"], "type": f"分割({row.get('type', '')})",
                                "ratio": after / before, "method": "FinMind before/after"})
                split_n += 1
        print(f"[調整事件] 分割事件(0050){split_n} 筆")
    except Exception as e:
        print(f"[調整事件] 分割資料抓取失敗({e}),這部分會被跳過(不影響既有本地資料)")

    if not events:
        return None

    df = pd.DataFrame(events).sort_values("date").reset_index(drop=True)
    DATA_DIR.mkdir(exist_ok=True)
    df.to_csv(OUTPUT_EVENTS, index=False, encoding="utf-8-sig")
    print(f"[調整事件] 共套用 {len(df)} 筆 -> {OUTPUT_EVENTS}")
    return df


# ---------- 用事件表反推還原股價 ----------
def build_adjusted_price(raw: pd.DataFrame, events: pd.DataFrame | None):
    if events is None or events.empty:
        local_adj = _load_local(OUTPUT_ADJ)
        if local_adj is not None:
            print(f"[還原價] 這次沒有可用的調整事件,保留本地既有的 {len(local_adj)} 筆還原價不覆蓋。")
        else:
            print("[還原價] 沒有調整事件可用,也沒有本地備援,跳過(K 線圖會自動退回用原始價)。")
        return

    df = raw.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    for col in ["Open", "High", "Low", "Close"]:
        df[f"{col}_adj"] = df[col].astype(float)

    events = events.copy()
    events["date"] = pd.to_datetime(events["date"])
    events = events.sort_values("date", ascending=False)  # 從最新往回處理

    for _, ev in events.iterrows():
        mask = df["Date"] < ev["date"]
        for col in ["Open", "High", "Low", "Close"]:
            df.loc[mask, f"{col}_adj"] = df.loc[mask, f"{col}_adj"] * ev["ratio"]

    out = df[["Date"]].copy()
    out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")
    for col in ["Open", "High", "Low", "Close"]:
        out[col] = df[f"{col}_adj"].round(3)
    out["Volume"] = df["Volume"]

    DATA_DIR.mkdir(exist_ok=True)
    out.to_csv(OUTPUT_ADJ, index=False, encoding="utf-8-sig")
    print(f"[還原價] 套用 {len(events)} 個調整事件,共 {len(out)} 筆,"
          f"區間 {out['Date'].min()} ~ {out['Date'].max()} -> {OUTPUT_ADJ}")


if __name__ == "__main__":
    raw_df = update_raw_price()
    events_df = fetch_adjustment_events(raw_df)
    build_adjusted_price(raw_df, events_df)
