
import requests
import csv
from datetime import datetime
from collections import Counter, defaultdict

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

        block = response.json().get("candles", {})
        columns = block.get("columns", [])
        rows = block.get("data", [])

        if not rows:
            break

        all_rows.extend(dict(zip(columns, row)) for row in rows)
        start += len(rows)

    return sorted(all_rows, key=lambda x: x["begin"])


def main():
    print("ПРОВЕРКА ВРЕМЕННОЙ НЕПРЕРЫВНОСТИ MXZ6")

    rows = load_candles()

    if not rows:
        print("Свечи не получены")
        return

    daily = defaultdict(int)
    gaps = []
    gap_frequency = Counter()

    for row in rows:
        daily[row["begin"][:10]] += 1

    for previous, current in zip(rows, rows[1:]):
        t1 = datetime.fromisoformat(previous["begin"])
        t2 = datetime.fromisoformat(current["begin"])

        minutes = int((t2 - t1).total_seconds() / 60)

        if minutes > INTERVAL:
            gap = {
                "date": t1.date().isoformat(),
                "from": t1.strftime("%H:%M"),
                "to": t2.strftime("%H:%M"),
                "minutes": minutes
            }
            gaps.append(gap)
            gap_frequency[minutes] += 1

    print("\n===== СВЕЧИ ПО ДНЯМ =====")
    for day in sorted(daily):
        print(day, daily[day])

    print("\n===== ПРОМЕЖУТКИ ДЛИННЕЕ 10 МИНУТ =====")
    print("Всего промежутков:", len(gaps))

    for gap in gaps:
        print(
            gap["date"],
            gap["from"], "->", gap["to"],
            "| минут:", gap["minutes"]
        )

    print("\n===== ЧАСТОТА ДЛИТЕЛЬНОСТИ ПРОМЕЖУТКОВ =====")
    for minutes, count in sorted(gap_frequency.items()):
        print(f"{minutes} минут: {count}")

    print("\nВсего свечей:", len(rows))
    print("Торговых дат:", len(daily))


if __name__ == "__main__":
    main()
