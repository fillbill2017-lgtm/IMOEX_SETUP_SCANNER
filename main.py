
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import Counter

URL = (
    "https://iss.moex.com/iss/engines/stock/markets/index/"
    "securities/IMOEX/candles.json"
)

TARGET_DATE = "2026-11-12"
INTERVAL = 10
MOSCOW = ZoneInfo("Europe/Moscow")


def fetch_data():
    rows_all = []
    columns = None
    start = 0

    while True:
        params = {
            "interval": INTERVAL,
            "from": TARGET_DATE,
            "till": TARGET_DATE,
            "start": start,
            "limit": 500,
            "iss.meta": "off",
        }

        response = requests.get(URL, params=params, timeout=30)
        response.raise_for_status()

        block = response.json()["candles"]
        page_columns = block["columns"]
        rows = block["data"]

        if columns is None:
            columns = page_columns

        if not rows:
            break

        rows_all.extend(rows)
        start += len(rows)

        if len(rows) < 500:
            break

    return columns, rows_all


def main():
    print("КОНТРОЛЬ НЕПРЕРЫВНОСТИ IMOEX")
    print("Дата:", TARGET_DATE)

    columns, rows = fetch_data()
    print("Поля MOEX:", columns)

    candles = []

    for row in rows:
        r = dict(zip(columns, row))

        time = datetime.fromisoformat(str(r["begin"]))
        end = datetime.fromisoformat(str(r["end"]))

        if time.tzinfo is None:
            time = time.replace(tzinfo=MOSCOW)

        if end.tzinfo is None:
            end = end.replace(tzinfo=MOSCOW)

        candles.append({
            "time": time.astimezone(MOSCOW),
            "end": end.astimezone(MOSCOW),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
        })

    candles.sort(key=lambda x: x["time"])

    times = [c["time"] for c in candles]
    counts = Counter(times)

    duplicates = [
        t for t, count in counts.items()
        if count > 1
    ]

    gaps = []

    for previous, current in zip(times, times[1:]):
        difference = current - previous

        if difference != timedelta(minutes=INTERVAL):
            gaps.append((previous, current, difference))

    invalid = []

    for c in candles:
        if not (
            c["low"] <= c["open"] <= c["high"]
            and c["low"] <= c["close"] <= c["high"]
            and c["low"] <= c["high"]
        ):
            invalid.append(c)

    flat = [
        c for c in candles
        if c["open"] == c["high"]
        == c["low"] == c["close"]
    ]

    print("\n=== ОБЩИЕ РЕЗУЛЬТАТЫ ===")
    print("Всего свечей:", len(candles))
    print("Дубликатов:", len(duplicates))
    print("Разрывов времени:", len(gaps))
    print("Некорректных OHLC:", len(invalid))
    print("Свечей с нулевым диапазоном:", len(flat))

    if candles:
        print("\nПервая свеча:")
        print(candles[0])

        print("\nПоследняя свеча:")
        print(candles[-1])

    if duplicates:
        print("\nДубликаты:")
        for t in duplicates:
            print(t)

    if gaps:
        print("\nРазрывы:")
        for previous, current, difference in gaps:
            print(previous, "->", current, "|", difference)

    if flat:
        print("\nСвечи с нулевым диапазоном:")
        for c in flat:
            print(c)

    print("\n=== ПОСЛЕДНИЕ 10 СВЕЧЕЙ ===")

    for c in candles[-10:]:
        print(
            f"{c['time']:%H:%M} - {c['end']:%H:%M} | "
            f"O:{c['open']} H:{c['high']} "
            f"L:{c['low']} C:{c['close']}"
        )

    print("\n=== ПРОВЕРКА ЗАВЕРШЕНА ===")


if __name__ == "__main__":
    main()
