
import requests
import csv
from collections import Counter
from datetime import datetime

SECID = "MXZ6"
DATE_FROM = "2026-10-01"
DATE_TILL = "2026-11-13"
INTERVAL = 10

URL = (
    "https://iss.moex.com/iss/engines/futures/markets/forts/"
    "boards/rfud/securities/MXZ6/candles.json"
)

FIELDS = [
    "open", "close", "high", "low",
    "value", "volume", "begin", "end"
]


def load_candles():
    all_rows = []
    start = 0

    while True:
        params = {
            "from": DATE_FROM,
            "till": DATE_TILL,
            "interval": INTERVAL,
            "start": start,
            "limit": 500,
            "iss.meta": "off"
        }

        response = requests.get(URL, params=params, timeout=30)
        response.raise_for_status()

        result = response.json()
        block = result.get("candles", {})
        columns = block.get("columns", [])
        rows = block.get("data", [])

        if not rows:
            break

        for row in rows:
            all_rows.append(dict(zip(columns, row)))

        print(
            f"Получено: {len(all_rows)} свечей",
            f"| следующая позиция: {start + len(rows)}"
        )

        start += len(rows)

    return all_rows


def main():
    print("ЗАГРУЗКА ИСТОРИИ MIX")
    print("Контракт:", SECID)
    print("Период:", DATE_FROM, "-", DATE_TILL)

    rows = load_candles()

    if not rows:
        print("ОШИБКА: свечи не получены")
        return

    rows.sort(key=lambda x: x["begin"])

    begins = [row["begin"] for row in rows]
    duplicates = len(begins) - len(set(begins))

    invalid_ohlc = 0
    zero_volume = 0
    total_volume = 0
    trading_days = set()

    for row in rows:
        o = float(row["open"])
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])
        v = float(row["volume"])

        if h < max(o, c, l) or l > min(o, c, h):
            invalid_ohlc += 1

        if v == 0:
            zero_volume += 1

        total_volume += v
        trading_days.add(row["begin"][:10])

    filename = (
        f"{SECID}_{INTERVAL}m_"
        f"{DATE_FROM}_{DATE_TILL}.csv"
    )

    with open(filename, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print("\n===== КОНТРОЛЬ КАЧЕСТВА =====")
    print("Всего свечей:", len(rows))
    print("Первaя свеча:", rows[0]["begin"])
    print("Последняя свеча:", rows[-1]["begin"])
    print("Торговых дат:", len(trading_days))
    print("Дубликатов:", duplicates)
    print("Некорректных OHLC:", invalid_ohlc)
    print("Свечей с нулевым объёмом:", zero_volume)
    print("Суммарный объём:", int(total_volume))
    print("Файл сохранён:", filename)

    print("\nПоследние 10 свечей:")
    for row in rows[-10:]:
        print(
            row["begin"],
            "O:", row["open"],
            "H:", row["high"],
            "L:", row["low"],
            "C:", row["close"],
            "V:", row["volume"]
        )


if __name__ == "__main__":
    main()
