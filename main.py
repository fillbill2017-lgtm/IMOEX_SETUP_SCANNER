import requests
from datetime import datetime, timezone

URL = "https://iss.moex.com/iss/engines/stock/markets/index/securities/IMOEX/candles.json"

params = {
    "interval": 60,
    "start": 0,
    "iss.reverse": 1,
    "iss.meta": "off",
}


def main():
    try:
        response = requests.get(URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        candles = data.get("candles", {}).get("data", [])
        columns = data.get("candles", {}).get("columns", [])

        if not candles:
            print("MOEX ISS вернула пустой список свечей.")
            return

        print("Получены последние доступные свечи IMOEX:")
        for candle in candles:
            item = dict(zip(columns, candle))
            print(
                f"Начало: {item.get('begin')} | "
                f"Закрытие: {item.get('close')} | "
                f"Объём: {item.get('volume')}"
            )

    except requests.RequestException as error:
        print(f"Ошибка подключения к MOEX ISS: {error}")
    except (ValueError, KeyError) as error:
        print(f"Ошибка обработки ответа: {error}")


if __name__ == "__main__":
    main()
