
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

            minutes = (actual - previous).total_seconds() / 60

            if minutes > 10:
                sessions.append(current)
                current = []

        current.append(row)

    if current:
        sessions.append(current)

    return sessions


def aggregate_sessions(sessions, size):
    bars = []

    for session_id, session in enumerate(sessions, 1):
        for start in range(0, len(session), size):
            chunk = session[start:start + size]
            complete = len(chunk) == size

            bars.append({
                "session_id": session_id,
                "begin": chunk[0]["begin"],
                "end": chunk[-1]["end"],
                "open": float(chunk[0]["open"]),
                "high": max(float(x["high"]) for x in chunk),
                "low": min(float(x["low"]) for x in chunk),
                "close": float(chunk[-1]["close"]),
                "volume": sum(float(x["volume"]) for x in chunk),
                "source_count": len(chunk),
                "is_complete": complete
            })

    return bars


def detect_pivots(bars, left=2, right=2, cross_sessions=False):
    pivots = []

    if cross_sessions:
        sequences = [[
            x for x in bars
            if x["is_complete"]
        ]]
    else:
        session_ids = sorted(set(x["session_id"] for x in bars))
        sequences = []

        for session_id in session_ids:
            sequence = [
                x for x in bars
                if x["session_id"] == session_id
                and x["is_complete"]
            ]
            sequences.append(sequence)

    for sequence in sequences:
        for i in range(left, len(sequence) - right):
            bar = sequence[i]

            previous = sequence[i-left:i]
            following = sequence[i+1:i+right+1]

            is_high = (
                all(bar["high"] > x["high"] for x in previous)
                and all(bar["high"] > x["high"] for x in following)
            )

            is_low = (
                all(bar["low"] < x["low"] for x in previous)
                and all(bar["low"] < x["low"] for x in following)
            )

            confirmed_at = following[-1]["end"]

            if is_high:
                pivots.append({
                    "session_id": bar["session_id"],
                    "type": "HIGH",
                    "time": bar["begin"],
                    "confirmed_at": confirmed_at,
                    "price": bar["high"]
                })

            if is_low:
                pivots.append({
                    "session_id": bar["session_id"],
                    "type": "LOW",
                    "time": bar["begin"],
                    "confirmed_at": confirmed_at,
                    "price": bar["low"]
                })

    return sorted(
        pivots,
        key=lambda x: (x["time"], x["type"])
    )


def classify_pivots(pivots):
    previous = {"HIGH": None, "LOW": None}

    for pivot in pivots:
        kind = pivot["type"]
        old = previous[kind]

        if old is None:
            label = "FIRST"
        elif pivot["price"] > old:
            label = "HH" if kind == "HIGH" else "HL"
        elif pivot["price"] < old:
            label = "LH" if kind == "HIGH" else "LL"
        else:
            label = "EQUAL"

        pivot["structure"] = label
        previous[kind] = pivot["price"]

    return pivots


def classify_market(pivots):
    highs = [p for p in pivots if p["type"] == "HIGH"]
    lows = [p for p in pivots if p["type"] == "LOW"]

    if len(highs) < 2 or len(lows) < 2:
        return {
            "state": "INSUFFICIENT_DATA",
            "reason": "Нужно минимум два подтверждённых максимума и два минимума",
            "highs": highs[-2:],
            "lows": lows[-2:]
        }

    high_old, high_new = highs[-2], highs[-1]
    low_old, low_new = lows[-2], lows[-1]

    higher_highs = high_new["price"] > high_old["price"]
    lower_highs = high_new["price"] < high_old["price"]

    higher_lows = low_new["price"] > low_old["price"]
    lower_lows = low_new["price"] < low_old["price"]

    if higher_highs and higher_lows:
        state = "UPTREND"
        reason = "Последние два максимума и минимума повышаются"

    elif lower_highs and lower_lows:
        state = "DOWNTREND"
        reason = "Последние два максимума и минимума понижаются"

    else:
        state = "TRANSITION"
        reason = "Направление максимумов и минимумов не совпадает или есть равные значения"

    return {
        "state": state,
        "reason": reason,
        "highs": [high_old, high_new],
        "lows": [low_old, low_new]
    }


def print_market_state(name, result):
    print(f"\n===== СОСТОЯНИЕ РЫНКА {name} =====")
    print("Классификация:", result["state"])
    print("Причина:", result["reason"])

    print("\nПоследние два максимума:")
    for p in result["highs"]:
        print(
            p["time"],
            p["price"],
            p.get("structure", ""),
            "| подтверждён:", p["confirmed_at"]
        )

    print("\nПоследние два минимума:")
    for p in result["lows"]:
        print(
            p["time"],
            p["price"],
            p.get("structure", ""),
            "| подтверждён:", p["confirmed_at"]
        )


def save_csv(filename, rows):
    if not rows:
        print("Нет данных:", filename)
        return

    with open(filename, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    print("АНАЛИЗ СТРУКТУРЫ MXZ6 — MARKET STATE V1.0")

    candles = load_candles()
    sessions = split_sessions(candles)

    print("Исходных свечей:", len(candles))
    print("Торговых сессий:", len(sessions))

    for name, size in [("1H", 6), ("4H", 24)]:
        bars = aggregate_sessions(sessions, size)

        cross_sessions = (name == "4H")

        pivots = detect_pivots(
            bars,
            left=2,
            right=2,
            cross_sessions=cross_sessions
        )

        pivots = classify_pivots(pivots)
        market_state = classify_market(pivots)

        complete_count = sum(x["is_complete"] for x in bars)
        partial_count = len(bars) - complete_count

        filename = f"MXZ6_{name}_PIVOTS_V2.csv"
        save_csv(filename, pivots)

        print(f"\n===== {name} =====")
        print("Всего баров:", len(bars))
        print("Полных:", complete_count)
        print("Неполных:", partial_count)
        print("Максимумов:", sum(x["type"] == "HIGH" for x in pivots))
        print("Минимумов:", sum(x["type"] == "LOW" for x in pivots))

        print_market_state(name, market_state)

        print("\nПоследние 15 экстремумов:")
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
