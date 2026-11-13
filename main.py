
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
            "till": "2026-11-13",
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

        data = response.json()
        candle_data = data.get("candles", {})

        page_columns = candle_data.get("columns", [])
        rows = candle_data.get("data", [])

        if columns is None:
            columns = page_columns
        elif columns != page_columns:
            raise ValueError(
                f"{secid}: изменился состав полей MOEX ISS"
            )

        if not rows:
            break

        all_rows.extend(rows)
        start += len(rows)

        if len(rows) < PAGE_SIZE:
            break

    return columns or [], all_rows


def parse_time(value):
    if isinstance(value, datetime):
        dt = value
    else:
        if value is None:
            raise ValueError("Время свечи отсутствует")

        dt = datetime.fromisoformat(str(value))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MOSCOW)

    return dt.astimezone(MOSCOW)


def inspect_security(secid):
    print(f"\n{'=' * 55}")
    print(f"ИНСТРУМЕНТ: {secid}")
    print(f"{'=' * 55}")

    try:
        columns, rows = fetch_candles(secid)
    except Exception as error:
        print(f"ОШИБКА ЗАПРОСА: {error}")
        return None

    if not rows:
        print("Свечи не получены.")
        print("Поля ответа:", columns)
        return []

    print("Поля MOEX ISS:", columns)

    candles = []

    for index, row in enumerate(rows):
        record = dict(zip(columns, row))

        required = ["begin", "open", "high", "low", "close"]
        missing = [field for field in required if field not in record]

        if missing:
            raise ValueError(
                f"{secid}: отсутствуют поля {missing}. "
                f"Доступные поля: {columns}"
            )

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
                f"{secid}: ошибка обработки строки {index}: "
                f"{record}. Причина: {error}"
            ) from error

        candles.append(candle)

    candles.sort(key=lambda x: x["time"])

    times = [c["time"] for c in candles]

    print(f"Получено свечей: {len(candles)}")
    print(f"Первая свеча: {times[0]}")
    print(f"Последняя свеча: {times[-1]}")

    after_17_30 = [
        c for c in candles
        if c["time"].hour > 17
        or (c["time"].hour == 17 and c["time"].minute >= 30)
    ]

    after_18_00 = [
        c for c in candles
        if c["time"].hour >= 18
    ]

    print(f"Свечей с 17:30 включительно: {len(after_17_30)}")
    print(f"Свечей с 18:00 включительно: {len(after_18_00)}")

    print("\nПоследние 15 свечей:")

    for c in candles[-15:]:
        print(
            f"{c['time']:%Y-%m-%d %H:%M} | "
            f"O:{c['open']} "
            f"H:{c['high']} "
            f"L:{c['low']} "
            f"C:{c['close']}"
        )

    return candles


def compare(first, second):
    print(f"\n{'=' * 55}")
    print("СРАВНЕНИЕ IMOEX И IMOEX2")
    print(f"{'=' * 55}")

    if first is None or second is None:
        print("Сравнение невозможно: ошибка одного из запросов.")
        return

    if not first or not second:
        print("У одного из инструментов нет свечей.")
        return

    first_times = {c["time"] for c in first}
    second_times = {c["time"] for c in second}

    common = first_times & second_times

    print(f"Свечей IMOEX: {len(first)}")
    print(f"Свечей IMOEX2: {len(second)}")
    print(f"Общих временных отметок: {len(common)}")
    print(f"Только в IMOEX: {len(first_times - second_times)}")
    print(f"Только в IMOEX2: {len(second_times - first_times)}")

    first_map = {c["time"]: c for c in first}
    second_map = {c["time"]: c for c in second}

    print("\nПоследние 10 общих свечей:")

    for timestamp in sorted(common)[-10:]:
        a = first_map[timestamp]
        b = second_map[timestamp]

        print(
            f"{timestamp:%H:%M} | "
            f"IMOEX C:{a['close']} | "
            f"IMOEX2 C:{b['close']}"
        )


def main():
    print("ПРОВЕРКА MOEX ISS")
    print(f"Дата проверки: {TARGET_DATE}")
    print(f"Интервал: {INTERVAL} минут")

    imoex = inspect_security("IMOEX")
    imoex2 = inspect_security("IMOEX2")

    compare(imoex, imoex2)

    print("\n=== ПРОВЕРКА ЗАВЕРШЕНА ===")


if __name__ == "__main__":
    main()
