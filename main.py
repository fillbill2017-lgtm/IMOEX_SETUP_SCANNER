
import requests
from datetime import date, timedelta

URL = "https://iss.moex.com/iss/engines/stock/markets/index/securities/IMOEX/candles.json"

today = date.today()
date_from = today - timedelta(days=30)

params = {
    "interval": 60,
    "from": date_from.isoformat(),
    "till": today.isoformat(),
    "start": 0,
    "iss.meta": "off",
}


def main():
    try:
        response = requests.get(URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        candles_block = data.get("candles", {})
        candles = candles_block.get("data", [])
        columns = candles_block.get("columns", [])

        if not candles:
            print("MOEX ISS не вернула свечи за выбранный период.")
            return

        print(f"Получено свечей: {len(candles)}")
        print("Последние 10 доступных часовых свечей IMOEX:")

        items = [dict(zip(columns, candle)) for candle in candles]
        items.sort(key=lambda x: x.get("begin") or "")

        for item in items[-10:]:
            print(
                f"Начало: {item.get('begin')} | "
                f"Закрытие: {item.get('close')} | "
                f"Объём: {item.get('volume')}"
            )

        print("Первая свеча:", items[0].get("begin"))
        print("Последняя свеча:", items[-1].get("begin"))

    except requests.RequestException as error:
        print(f"Ошибка подключения к MOEX ISS: {error}")
    except (ValueError, KeyError) as error:
        print(f"Ошибка обработки ответа: {error}")


if __name__ == "__main__":
    main()
