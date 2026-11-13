
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

BASE = "https://iss.moex.com/iss"
TICKER = "MXZ6"
TARGET_DATE = "2026-11-12"
MOSCOW = ZoneInfo("Europe/Moscow")

CANDLES_URL = (
    f"{BASE}/engines/futures/markets/forts/"
    f"boards/rfud/securities/{TICKER}/candles.json"
)

SECURITY_URL = (
    f"{BASE}/engines/futures/markets/forts/"
    f"securities/{TICKER}.json"
)


def request_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def fetch_candles():
    result = []
    start = 0

    while True:
        params = {
            "interval": 10,
            "from": TARGET_DATE,
            "till": TARGET_DATE,
            "start": start,
            "limit": 500,
            "iss.meta": "off",
        }

        data = request_json(CANDLES_URL, params)
        block = data["candles"]

        columns = block["columns"]
        rows = block["data"]

        if not rows:
            break

        result.extend(
            dict(zip(columns, row))
            for row in rows
        )

        start += len(rows)

        if len(rows) < 500:
            break

    return result


def print_table(block_name, block):
    if block_name not in block:
        print(f"\nБлок {block_name}: отсутствует")
        return

    data = block[block_name]

    print(f"\n=== {block_name.upper()} ===")
    print("Поля:", data["columns"])

    for row in data["data"]:
        print(dict(zip(data["columns"], row)))


def main():
    print("ПРОВЕРКА ФЬЮЧЕРСА MIX")
    print("Контракт:", TICKER)
    print("Дата:", TARGET_DATE)

    print("\n=== 1. СВЕЧИ ===")

    candles = fetch_candles()

    print("Получено свечей:", len(candles))

    if candles:
        columns = list(candles[0].keys())
        print("Поля:", columns)

        volumes = [
            float(c["volume"] or 0)
            for c in candles
        ]

        values = [
            float(c["value"] or 0)
            for c in candles
        ]

        print("Суммарный volume:", sum(volumes))
        print("Суммарный value:", sum(values))
        print("Свечей с нулевым volume:",
              sum(v == 0 for v in volumes))

        print("\nПоследние 10 свечей:")

        for c in candles[-10:]:
            print(
                f"{c['begin']} | "
                f"O:{c['open']} "
                f"H:{c['high']} "
                f"L:{c['low']} "
                f"C:{c['close']} | "
                f"Volume:{c['volume']} | "
                f"Value:{c['value']}"
            )

    print("\n=== 2. СТАТИСТИКА ИНСТРУМЕНТА ===")

    security = request_json(SECURITY_URL)

    print_table("securities", security)
    print_table("marketdata", security)

    print("\n=== ПРОВЕРКА ЗАВЕРШЕНА ===")


if __name__ == "__main__":
    main()
