
import requests
import csv
from datetime import datetime

SECID = "MXZ6"
DATE_FROM = "2026-10-01"
DATE_TILL = "2026-11-13"

URL = (
    "https://iss.moex.com/iss/engines/futures/markets/forts/"
    "boards/rfud/securities/MXZ6/candles.json"
)


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
            previous = datetime.fromisoformat(current[-1]["begin"])
            actual = datetime.fromisoformat(row["begin"])

            if (actual - previous).total_seconds() > 600:
                sessions.append(current)
                current = []

        current.append(row)

    if current:
        sessions.append(current)

    return sessions


def aggregate(sessions, size):
    result = []

    for session_id, session in enumerate(sessions, 1):
        for start in range(0, len(session), size):
            chunk = session[start:start + size]

            result.append({
                "session_id": session_id,
                "begin": chunk[0]["begin"],
                "end": chunk[-1]["end"],
                "open": float(chunk[0]["open"]),
                "high": max(float(x["high"]) for x in chunk),
                "low": min(float(x["low"]) for x in chunk),
                "close": float(chunk[-1]["close"]),
                "volume": sum(float(x["volume"]) for x in chunk),
                "source_count": len(chunk),
                "is_complete": len(chunk) == size
            })

    return result


def detect_pivots(bars, left=2, right=2):
    complete = [b for b in bars if b["is_complete"]]
    pivots = []

    for i in range(left, len(complete) - right):
        bar = complete[i]

        previous = complete[i-left:i]
        following = complete[i+1:i+right+1]

        is_high = (
            all(bar["high"] > x["high"] for x in previous)
            and all(bar["high"] > x["high"] for x in following)
        )

        is_low = (
            all(bar["low"] < x["low"] for x in previous)
            and all(bar["low"] < x["low"] for x in following)
        )

        confirmed_at = complete[i + right]["end"]

        if is_high:
            pivots.append({
                "type": "HIGH",
                "time": bar["begin"],
                "confirmed_at": confirmed_at,
                "price": bar["high"]
            })

        if is_low:
            pivots.append({
                "type": "LOW",
                "time": bar["begin"],
                "confirmed_at": confirmed_at,
                "price": bar["low"]
            })

    return sorted(pivots, key=lambda x: x["time"])


def classify_pivots(pivots):
    previous = {"HIGH": None, "LOW": None}

    for pivot in pivots:
        kind = pivot["type"]
        old = previous[kind]

        if old is None:
            pivot["structure"] = "FIRST"
        elif pivot["price"] > old:
            pivot["structure"] = "HH" if kind == "HIGH" else "HL"
        elif pivot["price"] < old:
            pivot["structure"] = "LH" if kind == "HIGH" else "LL"
        else:
            pivot["structure"] = "EQUAL"

        previous[kind] = pivot["price"]

    return pivots


def save_csv(filename, rows):
    if not rows:
        print("Нет данных:", filename)
        return

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    print("АНАЛИЗ СТРУКТУРЫ MXZ6")

    candles = load_candles()
    sessions = split_sessions(candles)

    for name, size in [("1H", 6), ("4H", 24)]:
        bars = aggregate(sessions, size)
        pivots = classify_pivots(
            detect_pivots(bars, left=2, right=2)
        )

        filename = f"MXZ6_{name}_PIVOTS.csv"
        save_csv(filename, pivots)

        highs = [x for x in pivots if x["type"] == "HIGH"]
        lows = [x for x in pivots if x["type"] == "LOW"]

        print(f"\n===== {name} =====")
        print("Полных свечей:", sum(x["is_complete"] for x in bars))
        print("Локальных максимумов:", len(highs))
        print("Локальных минимумов:", len(lows))

        print("\nПоследние 15 подтверждённых экстремумов:")

        for p in pivots[-15:]:
            print(
                p["time"],
                p["type"],
                p["price"],
                p["structure"],
                "| подтверждён:", p["confirmed_at"]
            )

        print("Файл:", filename)


if __name__ == "__main__":
    main()
