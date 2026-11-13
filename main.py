
import requests
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

URL = (
    "https://iss.moex.com/iss/engines/stock/"
    "markets/index/securities/IMOEX/candles.json"
)

PAGE_SIZE = 500
LOOKBACK_DAYS = 30
INTERVAL_MINUTES = 10
MOSCOW = ZoneInfo("Europe/Moscow")


def load_candles():
    now = datetime.now(MOSCOW)
    date_from = now.date() - timedelta(days=LOOKBACK_DAYS)

    params = {
        "interval": INTERVAL_MINUTES,
        "from": date_from.isoformat(),
        "till": now.date().isoformat(),
        "start": 0,
        "iss.meta": "off",
    }

    candles = []
    start = 0

    while True:
        params["start"] = start

        response = requests.get(
            URL,
            params=params,
            timeout=30
        )
        response.raise_for_status()

        payload = response.json()
        block = payload.get("candles", {})
        columns = block.get("columns", [])
        rows = block.get("data", [])

        if not rows:
            break

        candles.extend(
            dict(zip(columns, row))
            for row in rows
        )

        start += len(rows)

        if len(rows) < PAGE_SIZE:
            break

    return candles, now


def validate_ohlc(candle):
    try:
        o = float(candle["open"])
        h = float(candle["high"])
        l = float(candle["low"])
        c = float(candle["close"])

        if min(o, h, l, c) <= 0:
            return False

        if h < max(o, l, c):
            return False

        if l > min(o, h, c):
            return False

        return True

    except (ValueError, TypeError, KeyError):
        return False


def build_30m_candles(candles):
    groups = {}

    for candle in candles:
        timestamp = datetime.strptime(
            candle["begin"],
            "%Y-%m-%d %H:%M:%S"
        )

        bucket_minute = (timestamp.minute // 30) * 30

        key = (
            timestamp.strftime("%Y-%m-%d %H:")
            + f"{bucket_minute:02d}"
        )

        groups.setdefault(key, []).append(candle)

    result = []
    incomplete = 0

    for key, group in sorted(groups.items()):
        group.sort(key=lambda item: item["begin"])

        if len(group) != 3:
            incomplete += 1
            continue

        times = [
            datetime.strptime(
                item["begin"],
                "%Y-%m-%d %H:%M:%S"
            )
            for item in group
        ]

        if not (
            times[1] - times[0] == timedelta(minutes=10)
            and times[2] - times[1] == timedelta(minutes=10)
        ):
            incomplete += 1
            continue

        result.append({
            "begin": group[0]["begin"],
            "open": float(group[0]["open"]),
            "high": max(float(x["high"]) for x in group),
            "low": min(float(x["low"]) for x in group),
            "close": float(group[-1]["close"]),
        })

    return result, incomplete


def main():
    try:
        raw, now = load_candles()

        print("=== КОНТРОЛЬ КАЧЕСТВА IMOEX ===")
        print("Получено строк:", len(raw))

        if not raw:
            print("Нет данных от MOEX ISS.")
            return

        required = {
            "begin", "open", "high", "low", "close"
        }

        missing_fields = required.difference(raw[0].keys())

        if missing_fields:
            print("Отсутствуют поля:", sorted(missing_fields))
            return

        timestamps = [
            item.get("begin")
            for item in raw
            if item.get("begin")
        ]

        duplicates = len(timestamps) - len(set(timestamps))

        unique = {}

        for candle in raw:
            if candle.get("begin"):
                unique[candle["begin"]] = candle

        candles = sorted(
            unique.values(),
            key=lambda item: item["begin"]
        )

        invalid = [
            candle
            for candle in candles
            if not validate_ohlc(candle)
        ]

        valid = [
            candle
            for candle in candles
            if validate_ohlc(candle)
        ]

        completed = []

        for candle in valid:
            begin = datetime.strptime(
                candle["begin"],
                "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=MOSCOW)

            end = begin + timedelta(
                minutes=INTERVAL_MINUTES
            )

            if end <= now:
                completed.append(candle)

        print("Дубликатов:", duplicates)
        print("Некорректных OHLC:", len(invalid))
        print(
            "Незакрытых свечей исключено:",
            len(valid) - len(completed)
        )
        print(
            "Закрытых уникальных свечей:",
            len(completed)
        )

        print("\nПоследние 10 закрытых свечей 10M:")

        for candle in completed[-10:]:
            print(
                f"{candle['begin']} | "
                f"O:{candle['open']} "
                f"H:{candle['high']} "
                f"L:{candle['low']} "
                f"C:{candle['close']}"
            )

        candles_30m, incomplete = build_30m_candles(
            completed
        )

        invalid_30m = [
            candle
            for candle in candles_30m
            if not validate_ohlc(candle)
        ]

        print("\n=== АГРЕГАЦИЯ 30M ===")
        print("Полноценных свечей:", len(candles_30m))
        print("Неполных групп исключено:", incomplete)
        print("Некорректных свечей 30M:", len(invalid_30m))

        print("\nПоследние 10 свечей 30M:")

        for candle in candles_30m[-10:]:
            print(
                f"{candle['begin']} | "
                f"O:{candle['open']} "
                f"H:{candle['high']} "
                f"L:{candle['low']} "
                f"C:{candle['close']}"
            )

        if completed:
            print("\nПервая 10M:", completed[0]["begin"])
            print("Последняя 10M:", completed[-1]["begin"])

        if candles_30m:
            print("Первая 30M:", candles_30m[0]["begin"])
            print("Последняя 30M:", candles_30m[-1]["begin"])

    except requests.RequestException as error:
        print("Ошибка подключения к MOEX ISS:", error)

    except (ValueError, KeyError, TypeError) as error:
        print("Ошибка обработки данных:", error)


if __name__ == "__main__":
    main()
