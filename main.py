
import requests
import csv
from datetime import datetime
from collections import defaultdict

SECID = "MXZ6"
DATE_FROM = "2026-10-01"
DATE_TILL = "2026-11-13"

URL = (
    "https://iss.moex.com/iss/engines/futures/markets/forts/"
    "boards/rfud/securities/MXZ6/candles.json"
)

BASE_FIELDS = [
    "open", "close", "high", "low",
    "value", "volume", "begin", "end"
]


def load_candles():
    result = []
    start = 0

    while True:
        params = {
            "from": DATE_FROM,
            "till": DATE_TILL,
            "interval": 10,
            "start": start,
            "limit": 500,
            "iss.meta": "off"
        }

        response = requests.get(URL, params=params, timeout=30)
        response.raise_for_status()

        block = response.json().get("candles", {})
        columns = block.get("columns", [])
        data = block.get("data", [])

        if not data:
            break

        result.extend(dict(zip(columns, row)) for row in data)
        start += len(data)

    return sorted(result, key=lambda x: x["begin"])


def split_sessions(rows):
    sessions = []
    current = []

    for row in rows:
        if current:
            previous_time = datetime.fromisoformat(
                current[-1]["begin"]
            )
            current_time = datetime.fromisoformat(row["begin"])

            minutes = (
                current_time - previous_time
            ).total_seconds() / 60

            if minutes > 10:
                sessions.append(current)
                current = []

        current.append(row)

    if current:
        sessions.append(current)

    return sessions


def aggregate_sessions(sessions, barsize):
    result = []

    for session_number, session in enumerate(sessions, start=1):
        for start in range(0, len(session), barsize):
            chunk = session[start:start + barsize]

            bar = {
                "session_id": session_number,
                "begin": chunk[0]["begin"],
                "end": chunk[-1]["end"],
                "open": chunk[0]["open"],
                "high": max(float(x["high"]) for x in chunk),
                "low": min(float(x["low"]) for x in chunk),
                "close": chunk[-1]["close"],
                "volume": sum(float(x["volume"]) for x in chunk),
                "source_count": len(chunk),
                "is_complete": len(chunk) == barsize
            }

            result.append(bar)

    return result


def save_csv(filename, rows):
    if not rows:
        print("Нет данных для файла:", filename)
        return

    fields = list(rows[0].keys())

    with open(filename, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def report(name, rows):
    complete = sum(1 for x in rows if x["is_complete"])
    partial = len(rows) - complete

    print(f"\n===== {name} =====")
    print("Всего баров:", len(rows))
    print("Полных:", complete)
    print("Неполных:", partial)

    if rows:
        print("Первый:", rows[0]["begin"])
        print("Последний:", rows[-1]["begin"])

        print("\nПоследние 5 баров:")
        for bar in rows[-5:]:
            print(
                bar["begin"],
                "O:", bar["open"],
                "H:", bar["high"],
                "L:", bar["low"],
                "C:", bar["close"],
                "V:", int(bar["volume"]),
                "Полный:", bar["is_complete"]
            )


def main():
    print("АГРЕГАЦИЯ ИСТОРИИ", SECID)

    candles = load_candles()
    print("Исходных 10M свечей:", len(candles))

    sessions = split_sessions(candles)
    print("Непрерывных торговых сессий:", len(sessions))

    for name, size in [
        ("30M", 3),
        ("1H", 6),
        ("4H", 24)
    ]:
        bars = aggregate_sessions(sessions, size)

        filename = (
            f"{SECID}_{name}_"
            f"{DATE_FROM}_{DATE_TILL}.csv"
        )

        save_csv(filename, bars)
        report(name, bars)

        print("Файл:", filename)


if __name__ == "__main__":
    main()
