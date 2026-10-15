@echo off
REM 自動更新整條資料流水線:抓股價 -> 抓節日(確保涵蓋到今年/明年) -> 算統計 -> 匯出網頁資料
REM 用法:把這個檔案放在 0050-holiday-effect 資料夾最外層(跟 scripts、web、data 同一層)
REM 想排程每天自動跑:Windows 搜尋「工作排程器」-> 建立基本工作 -> 觸發程序選「每天」
REM                   -> 執行動作選「啟動程式」-> 程式/指令選這個 .bat 檔的完整路徑

cd /d "%~dp0"

echo [1/4] 抓最新股價(原始價 + 還原價)...
python scripts\fetch_price.py
if errorlevel 1 goto :error

echo [2/4] 更新節日資料(預設涵蓋 2003 ~ 今年+1,寫在 fetch_holidays.py 裡面)...
python scripts\fetch_holidays.py
if errorlevel 1 goto :error

echo [3/4] 重新計算連假效應統計...
python scripts\analyze.py
if errorlevel 1 goto :error

echo [4/4] 匯出網頁用的 JSON...
python scripts\export_json.py
if errorlevel 1 goto :error
python scripts\export_price_json.py
if errorlevel 1 goto :error

echo.
echo 全部更新完成!
goto :eof

:error
echo.
echo 更新過程中某一步失敗了,往上看是哪一步出錯。
exit /b 1
