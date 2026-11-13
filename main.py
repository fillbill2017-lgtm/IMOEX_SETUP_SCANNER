
import requests
from datetime import date, timedelta

URL = "https://iss.moex.com/iss/engines/stock/markets/index/securities/IMOEX/candles.json"

PAGE_SIZE = 500
LOOKBACK_DAYS = 30


def load_candles():
    today = date.today()
    date_from = today - timedelta(days=LOOKBACK_DAYS)

    params = {
        "interval": 10,
        "from": date_from.isoformat(),
        "till": today.isoformat(),
        "start": 0,
        "iss.meta": "off",
    }

    all_candles = []
    start = 0

    while True:
        params["start"] = start
        response = requests.get(URL, params=params, timeout=30)
        response.raise_for_status()

        payload = response.json()
        block = payload.get("candles", {})
        columns = block.get("columns", [])
        rows = block.get("data", [])

        if not rows:
            break

        all_candles.extend(
            dict(zip(columns, row)) for row in rows
        )

        start += len(rows)

        if len(rows) < PAGE_SIZE:
            break

    unique = {
        candle.get("begin"): candle
        for candle in all_candles
    }

    return sorted(
        unique.values(),
        key=lambda candle: candle.get("begin") or ""
    )


def main():
    try:
        candles = load_candles()

        if not candles:
            print("MOEX ISS не вернула свечи.")
            return

        required = {"begin", "open", "high", "low", "close"}
        missing = required.difference(candles[0].keys())

        if missing:
            print("Отсутствуют поля:", ", ".join(sorted(missing)))
            return

        print(f"Получено 10-минутных свечей: {len(candles)}")
        print("Последние 10 свечей IMOEX:")

        for candle in candles[-10:]:
            print(
                f"Время: {candle.get('begin')} | "
                f"O: {candle.get('open')} | "
                f"H: {candle.get('high')} | "
                f"L: {candle.get('low')} | "
                f"C: {candle.get('close')} | "
                f"Объём: {candle.get('volume')}"
            )

        print("Первая свеча:", candles[0].get("begin"))
        print("Последняя свеча:", candles[-1].get("begin"))

    except requests.RequestException as error:
        print(f"Ошибка подключения к MOEX ISS: {error}")
    except (ValueError, KeyError, TypeError) as error:
        print(f"Ошибка обработки ответа: {error}")


if __name__ == "__main__":
    main()
