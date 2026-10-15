# 台股連假效應分析 — 0050 元大台灣50

分析台灣各個國定假日(元旦、春節、清明、端午、中秋...等)前後,0050 ETF 的報酬率表現,
並提供一個可以逐年查看對應 K 線走勢的網頁。

🔗 **網站**: 部署完成後會是 `https://<你的 GitHub 帳號>.github.io/<這個 repo 的名稱>/`

## 這是什麼

- 用固定規則 + 農曆換算,產生 2003 年至今每個台灣國定假日的日期區間(不依賴殘缺的政府開放資料)
- 抓 0050 從上市至今的股價(原始價 + 自算還原股價,處理過除權息、股票分割、無成交日等細節)
- 統計每個節日「連假前後」的報酬率(前後 1/3/5 日、連假期間缺口報酬)
- 網頁可以逐年點進去看當時的 K 線走勢(含成交量、縮放拖曳、自訂天數報酬計算)

## 專案結構

```
scripts/
  fetch_holidays.py       產生節日日期區間(data/holidays.csv)
  fetch_price.py          抓股價,原始價 + 自算還原股價(data/0050_price*.csv)
  analyze.py               算連假前後報酬率統計(data/holiday_stats_*.csv)
  export_json.py          把統計結果轉成網頁用的 web/data.json
  export_price_json.py    把股價轉成網頁用的 web/price.json
web/
  index.html              網站主頁面
  candlestick.js           手刻的 K 線圖元件(不依賴第三方圖表庫)
  vendor/chart.umd.js      Chart.js(畫長條圖用)
  data.json, price.json    網頁讀取的資料(由上面腳本產生)
data/                      中間產生的 CSV
update_all.bat             Windows 用:一次重跑完整流程
```

## 本機更新資料

```
python scripts\fetch_price.py
python scripts\fetch_holidays.py
python scripts\analyze.py
python scripts\export_json.py
python scripts\export_price_json.py
```

或是直接雙擊 / 執行 `update_all.bat` 一次跑完。

跑完之後,要讓**線上的網站**也更新,還要再做這兩步,把新產生的資料推上 GitHub:

```
git add data web
git commit -m "更新資料"
git push
```

Push 上去之後,GitHub Actions 會自動重新部署網站(幾十秒內生效),不用手動做其他事。

## 需要安裝的 Python 套件

```
pip install -r requirements.txt
```

## 本機預覽網站

```
cd web
python -m http.server 8000
```

瀏覽器打開 `http://localhost:8000`