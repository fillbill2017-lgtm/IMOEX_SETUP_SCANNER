
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

URL = (
    "https://iss.moex.com/iss/engines/stock/markets/index/"
    "securities/{secid}/candles.json"
)

TARGET_DATE = "2026-11-13"
INTERVAL = 10
PAGE_SIZE = 500
MOSCOW = ZoneInfo("Europe/Moscow")


def fetch_candles(secid):
    """Получает все 10-минутные свечи за заданную дату."""
    all_rows = []
    start = 0

    while True:
        params = {
            "interval": INTERVAL,
            "from": TARGET_DATE,
            "till": "2026-11-14",
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
        rows = data.get("candles", {}).get("data", [])

        if not rows:
            break

        all_rows.extend(rows)
        start += len(rows)

        if len(rows) < PAGE_SIZE:
            break

    return all_rows


def parse_time(value):
    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MOSCOW)

    return dt.astimezone(MOSCOW)


def inspect_security(secid):
    print(f"\n{'=' * 55}")
    print(f"ИНСТРУМЕНТ: {secid}")
    print(f"{'=' * 55}")

    try:
        rows = fetch_candles(secid)
    except Exception as error:
        print(f"ОШИБКА ЗАПРОСА: {error}")
        return None

    if not rows:
        print("Свечи не получены.")
        return []

    candles = []

    for row in rows:
        begin, open_, high, low, close, volume = row[:6]

        candles.append({
            "time": parse_time(begin),
            "open": float(open_),
            "high": float(high),
            "low": float(low),
            "close": float(close),
        })

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

    only_first = first_times - second_times
    only_second = second_times - first_times

    print(f"Только в IMOEX: {len(only_first)}")
    print(f"Только в IMOEX2: {len(only_second)}")

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
