
import requests
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

URL = (
    "https://iss.moex.com/iss/engines/stock/"
    "markets/index/securities/IMOEX/candles.json"
)

PAGE_SIZE = 500
LOOKBACK_DAYS = 30
INTERVAL = 10
MOSCOW = ZoneInfo("Europe/Moscow")


def load_candles():
    now = datetime.now(MOSCOW)
    date_from = now.date() - timedelta(days=LOOKBACK_DAYS)

    params = {
        "interval": INTERVAL,
        "from": date_from.isoformat(),
        "till": now.date().isoformat(),
        "start": 0,
        "iss.meta": "off",
    }

    result = []
    start = 0

    while True:
        params["start"] = start

        response = requests.get(
            URL, params=params, timeout=30
        )
        response.raise_for_status()

        payload = response.json()
        block = payload.get("candles", {})
        columns = block.get("columns", [])
        rows = block.get("data", [])

        if not rows:
            break

        result.extend(
            dict(zip(columns, row)) for row in rows
        )

        start += len(rows)

        if len(rows) < PAGE_SIZE:
            break

    return result, now


def valid_ohlc(c):
    try:
        o = float(c["open"])
        h = float(c["high"])
        l = float(c["low"])
        close = float(c["close"])

        return (
            min(o, h, l, close) > 0
            and h >= max(o, l, close)
            and l <= min(o, h, close)
        )
    except (ValueError, TypeError, KeyError):
        return False


def build_30m(candles):
    groups = {}

    for c in candles:
        t = datetime.strptime(
            c["begin"], "%Y-%m-%d %H:%M:%S"
        )

        bucket_minute = (t.minute // 30) * 30
        key = (
            t.strftime("%Y-%m-%d %H:")
            + f"{bucket_minute:02d}"
        )

        groups.setdefault(key, []).append(c)

    result = []
    incomplete = 0
    continuity_errors = 0

    for key, group in sorted(groups.items()):
        group.sort(key=lambda x: x["begin"])

        if len(group) != 3:
            incomplete += 1
            continue

        times = [
            datetime.strptime(
                c["begin"], "%Y-%m-%d %H:%M:%S"
            )
            for c in group
        ]

        expected_start = datetime.strptime(
            key, "%Y-%m-%d %H:%M"
        )

        if (
            times[0] != expected_start
            or times[1] - times[0] != timedelta(minutes=10)
            or times[2] - times[1] != timedelta(minutes=10)
        ):
            continuity_errors += 1
            continue

        result.append({
            "begin": key + ":00",
            "open": float(group[0]["open"]),
            "high": max(float(x["high"]) for x in group),
            "low": min(float(x["low"]) for x in group),
            "close": float(group[-1]["close"]),
            "source": group,
        })

    return result, incomplete, continuity_errors


def main():
    try:
        raw, now = load_candles()

        print("=== IMOEX: КОНТРОЛЬ ИСХОДНЫХ ДАННЫХ ===")
        print("Получено строк:", len(raw))

        timestamps = [
            c.get("begin") for c in raw if c.get("begin")
        ]

        duplicates = len(timestamps) - len(set(timestamps))

        unique = {
            c["begin"]: c
            for c in raw
            if c.get("begin")
        }

        candles = sorted(
            unique.values(),
            key=lambda x: x["begin"]
        )

        invalid = [
            c for c in candles if not valid_ohlc(c)
        ]

        valid = [
            c for c in candles if valid_ohlc(c)
        ]

        completed = []

        for c in valid:
            begin = datetime.strptime(
                c["begin"], "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=MOSCOW)

            if begin + timedelta(minutes=INTERVAL) <= now:
                completed.append(c)

        print("Дубликатов:", duplicates)
        print("Некорректных OHLC:", len(invalid))
        print("Закрытых 10M:", len(completed))
        print("Исключено незакрытых:", len(valid) - len(completed))

        bars_30m, incomplete, continuity_errors = build_30m(
            completed
        )

        print("\n=== IMOEX: АГРЕГАЦИЯ 30M ===")
        print("Полных свечей:", len(bars_30m))
        print("Неполных групп:", incomplete)
        print("Ошибок последовательности:", continuity_errors)

        verification_errors = 0

        for bar in bars_30m:
            source = bar["source"]

            expected = {
                "open": float(source[0]["open"]),
                "high": max(float(x["high"]) for x in source),
                "low": min(float(x["low"]) for x in source),
                "close": float(source[-1]["close"]),
            }

            for field, value in expected.items():
                if abs(bar[field] - value) > 0.000001:
                    verification_errors += 1

        print("Ошибок сверки OHLC:", verification_errors)

        print("\n=== ПОДРОБНАЯ СВЕРКА ПОСЛЕДНИХ 5 СВЕЧЕЙ ===")

        for bar in bars_30m[-5:]:
            print("\n30M:", bar["begin"])
            print(
                f"O:{bar['open']} "
                f"H:{bar['high']} "
                f"L:{bar['low']} "
                f"C:{bar['close']}"
            )

            print("Исходные 10M:")

            for c in bar["source"]:
                print(
                    f"  {c['begin']} | "
                    f"O:{c['open']} "
                    f"H:{c['high']} "
                    f"L:{c['low']} "
                    f"C:{c['close']}"
                )

        print("\n=== ИТОГ ===")

        if (
            duplicates == 0
            and not invalid
            and continuity_errors == 0
            and verification_errors == 0
        ):
            print("Проверенные условия выполнены.")
        else:
            print("Обнаружены проблемы. Требуется разбор.")

        if completed:
            print("\nПоследняя 10M:", completed[-1]["begin"])

        if bars_30m:
            print("Последняя 30M:", bars_30m[-1]["begin"])

    except requests.RequestException as error:
        print("Ошибка MOEX ISS:", error)

    except (ValueError, KeyError, TypeError) as error:
        print("Ошибка обработки:", error)


if __name__ == "__main__":
    main()
