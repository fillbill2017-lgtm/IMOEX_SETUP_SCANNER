
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

URL = (
    "https://iss.moex.com/iss/engines/stock/markets/index/"
    "securities/IMOEX/candles.json"
)

TARGET_DATE = "2026-11-12"
MOSCOW = ZoneInfo("Europe/Moscow")


def fetch_data():
    params = {
        "interval": 10,
        "from": TARGET_DATE,
        "till": TARGET_DATE,
        "start": 0,
        "limit": 500,
        "iss.meta": "off",
    }

    response = requests.get(URL, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()["candles"]
    columns = data["columns"]
    rows = data["data"]

    return [dict(zip(columns, row)) for row in rows]


def main():
    rows = fetch_data()

    print("ПРОВЕРКА ОБЪЁМА И СТОИМОСТИ IMOEX")
    print("Дата:", TARGET_DATE)
    print("Всего свечей:", len(rows))

    zero_volume = 0
    zero_value = 0

    for row in rows:
        volume = float(row["volume"] or 0)
        value = float(row["value"] or 0)

        if volume == 0:
            zero_volume += 1

        if value == 0:
            zero_value += 1

    print("\n=== ОБЩАЯ СТАТИСТИКА ===")
    print("Свечей с нулевым volume:", zero_volume)
    print("Свечей с нулевым value:", zero_value)

    print("\n=== ПОСЛЕДНИЕ 15 СВЕЧЕЙ ===")

    for row in rows[-15:]:
        time = datetime.fromisoformat(str(row["begin"]))

        if time.tzinfo is None:
            time = time.replace(tzinfo=MOSCOW)

        print(
            f"{time:%H:%M} | "
            f"O:{row['open']} H:{row['high']} "
            f"L:{row['low']} C:{row['close']} | "
            f"Volume:{row['volume']} | "
            f"Value:{row['value']}"
        )

    print("\n=== СВЕЧИ С НУЛЕВЫМ ДИАПАЗОНОМ ===")

    for row in rows:
        if (
            row["open"] == row["high"]
            == row["low"] == row["close"]
        ):
            print(row)

    print("\n=== ПРОВЕРКА ЗАВЕРШЕНА ===")


if __name__ == "__main__":
    main()
