# -*- coding: utf-8 -*-
"""
產生 2003~2016 年連假種子資料(近似版,非官方逐年公告的彈性放假/補班規則)。

規則:
- 固定國曆假日:元旦(1/1)、和平紀念日(2/28)、國慶日(10/10)
- 兒童節(4/4):只從 2011 年起算(2011年以前不是國定假日)
- 清明節/民族掃墓節:用節氣對照表(近似,2003~2016)
- 端午節(農曆5/5)、中秋節(農曆8/15):用農曆轉換套件算
- 春節:除夕(農曆年末日) + 初一 + 初二 + 初三
- 另外把 2003~2016 所有週六、週日都加進去,讓週末可以跟上面的假日自然接成
  連續3天以上的連假(真正只有週六週日、沒連到假日的,本來就會因為只有2天
  被 build_holiday_periods() 的 min_len=3 篩掉,不會誤判成連假)

輸出: data/holidays_seed_2003_2016.csv (覆蓋掉原本只有示範資料的版本)
"""
from datetime import date, timedelta
from pathlib import Path

from zhdate import ZhDate

OUTPUT = Path(__file__).resolve().parent.parent / "data" / "holidays_seed_2003_2016.csv"

YEARS = range(2003, 2017)

# 清明節(民族掃墓節)近似日期對照表,2003~2016
QINGMING = {
    2003: (4, 5), 2004: (4, 4), 2005: (4, 5), 2006: (4, 5),
    2007: (4, 5), 2008: (4, 4), 2009: (4, 4), 2010: (4, 5),
    2011: (4, 5), 2012: (4, 4), 2013: (4, 4), 2014: (4, 5),
    2015: (4, 5), 2016: (4, 4),
}


def add(rows, d: date, note: str):
    rows.append((d.strftime("%Y-%m-%d"), note))


def build():
    rows = []

    for y in YEARS:
        add(rows, date(y, 1, 1), "元旦")
        add(rows, date(y, 2, 28), "和平紀念日")
        add(rows, date(y, 10, 10), "國慶日")

        if y >= 2011:
            add(rows, date(y, 4, 4), "兒童節")

        qm_month, qm_day = QINGMING[y]
        add(rows, date(y, qm_month, qm_day), "民族掃墓節")

        duanwu = ZhDate(y, 5, 5).to_datetime().date()
        add(rows, duanwu, "端午節")

        zhongqiu = ZhDate(y, 8, 15).to_datetime().date()
        add(rows, zhongqiu, "中秋節")

        # 春節:除夕 + 初一初二初三
        try:
            new_year_day1 = ZhDate(y, 1, 1).to_datetime().date()
        except Exception:
            continue
        chuxi = new_year_day1 - timedelta(days=1)
        add(rows, chuxi, "除夕")
        add(rows, new_year_day1, "春節")
        add(rows, new_year_day1 + timedelta(days=1), "春節")
        add(rows, new_year_day1 + timedelta(days=2), "春節")

    # 加入所有週六、週日(2003-01-01 ~ 2016-12-31)
    d = date(2003, 1, 1)
    end = date(2016, 12, 31)
    while d <= end:
        if d.weekday() == 5:
            add(rows, d, "週六")
        elif d.weekday() == 6:
            add(rows, d, "週日")
        d += timedelta(days=1)

    # 同一天如果有多個 note(例如假日剛好是週六),只留第一個真正的假日名稱
    seen = {}
    order = []
    for d_str, note in rows:
        if d_str not in seen:
            seen[d_str] = note
            order.append(d_str)
        else:
            # 已經有假日名稱的話,不要被「週六/週日」蓋掉
            if seen[d_str] in ("週六", "週日") and note not in ("週六", "週日"):
                seen[d_str] = note

    order.sort()
    return order, seen


if __name__ == "__main__":
    order, seen = build()
    OUTPUT.parent.mkdir(exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig") as f:
        f.write("date,note\n")
        for d_str in order:
            f.write(f"{d_str},{seen[d_str]}\n")
    print(f"產生 {len(order)} 筆(2003-01-01 ~ 2016-12-31,含假日+週末) -> {OUTPUT}")
