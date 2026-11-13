
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

URL = (
    "https://iss.moex.com/iss/engines/stock/markets/index/"
    "securities/{secid}/candles.json"
)

TARGET_DATE = "2026-11-12"
INTERVAL = 10
PAGE_SIZE = 500
MOSCOW = ZoneInfo("Europe/Moscow")


def fetch_candles(secid):
    all_rows = []
    columns = None
    start = 0

    while True:
        params = {
            "interval": INTERVAL,
            "from": TARGET_DATE,
            "till": TARGET_DATE,
            "start": start,
            "limit": PAGE_SIZE,
            "iss.meta": "off",
        }

        response = requests.get(
            URL.format(secid=secid),
            params=params,
            timeout=30,
        )
        response.raise_for_status()

        candle_data = response.json().get("candles", {})
        page_columns = candle_data.get("columns", [])
        rows = candle_data.get("data", [])

        if columns is None:
            columns = page_columns
        elif columns != page_columns:
            raise ValueError("Изменился состав полей MOEX ISS")

        if not rows:
            break

        all_rows.extend(rows)
        start += len(rows)

        if len(rows) < PAGE_SIZE:
            break

    return columns or [], all_rows


def parse_time(value):
    dt = datetime.fromisoformat(str(value))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MOSCOW)

    return dt.astimezone(MOSCOW)


def inspect_security(secid):
    print("\n" + "=" * 55)
    print(f"ИНСТРУМЕНТ: {secid}")
    print("=" * 55)

    try:
        columns, rows = fetch_candles(secid)
    except Exception as error:
        print(f"ОШИБКА ЗАПРОСА: {error}")
        return None

    print("Поля MOEX ISS:", columns)

    if not rows:
        print("Свечи не получены.")
        return []

    candles = []

    for index, row in enumerate(rows):
        record = dict(zip(columns, row))

        try:
            candle = {
                "time": parse_time(record["begin"]),
                "open": float(record["open"]),
                "high": float(record["high"]),
                "low": float(record["low"]),
                "close": float(record["close"]),
            }
        except Exception as error:
            raise ValueError(
                f"Ошибка строки {index}: {record}; {error}"
            ) from error

        candles.append(candle)

    candles.sort(key=lambda x: x["time"])

    # Защита от попадания чужой даты в результат
    candles = [
        c for c in candles
        if c["time"].strftime("%Y-%m-%d") == TARGET_DATE
    ]

    print(f"Дата проверки: {TARGET_DATE}")
    print(f"Свечей за этот день: {len(candles)}")

    if not candles:
        return []

    print(f"Первая свеча: {candles[0]['time']}")
    print(f"Последняя свеча: {candles[-1]['time']}")

    periods = {
        "До 10:00": lambda t: t.hour < 10,
        "10:00–18:00": lambda t: 10 <= t.hour < 18,
        "18:00–19:00": lambda t: 18 <= t.hour < 19,
        "19:00–23:59": lambda t: t.hour >= 19,
    }

    print("\nРаспределение свечей по времени:")

    for name, condition in periods.items():
        count = sum(condition(c["time"]) for c in candles)
        print(f"{name}: {count}")

    print("\nВсе свечи с 17:30 и позже:")

    evening = [
        c for c in candles
        if c["time"].hour > 17
        or (c["time"].hour == 17 and c["time"].minute >= 30)
    ]

    if not evening:
        print("Нет свечей.")
    else:
        for c in evening:
            print(
                f"{c['time']:%H:%M} | "
                f"O:{c['open']} H:{c['high']} "
                f"L:{c['low']} C:{c['close']}"
            )

    return candles


def compare(first, second):
    print("\n" + "=" * 55)
    print("СРАВНЕНИЕ IMOEX И IMOEX2")
    print("=" * 55)

    if first is None or second is None:
        print("Сравнение невозможно: ошибка запроса.")
        return

    first_map = {c["time"]: c for c in first}
    second_map = {c["time"]: c for c in second}

    first_times = set(first_map)
    second_times = set(second_map)
    common = sorted(first_times & second_times)

    print(f"Свечей IMOEX: {len(first)}")
    print(f"Свечей IMOEX2: {len(second)}")
    print(f"Общих временных отметок: {len(common)}")
    print(f"Только в IMOEX: {len(first_times - second_times)}")
    print(f"Только в IMOEX2: {len(second_times - first_times)}")

    differences = 0

    for timestamp in common:
        a = first_map[timestamp]
        b = second_map[timestamp]

        if any(
            a[field] != b[field]
            for field in ("open", "high", "low", "close")
        ):
            differences += 1
            print(
                f"РАЗЛИЧИЕ {timestamp:%H:%M}: "
                f"IMOEX C:{a['close']} | IMOEX2 C:{b['close']}"
            )

    print(f"Свечей с различиями OHLC: {differences}")


def main():
    print("ПРОВЕРКА MOEX ISS")
    print(f"Дата: {TARGET_DATE}")
    print(f"Интервал: {INTERVAL} минут")

    imoex = inspect_security("IMOEX")
    imoex2 = inspect_security("IMOEX2")

    compare(imoex, imoex2)

    print("\n=== ПРОВЕРКА ЗАВЕРШЕНА ===")


if __name__ == "__main__":
    main()
