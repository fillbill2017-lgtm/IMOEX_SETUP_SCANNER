
import requests
import json

BASE_URL = "https://iss.moex.com/iss/analyticalproducts/futoi/securities"

TARGET_DATE = "2026-11-12"
TICKER = "mx"


def main():
    url = f"{BASE_URL}/{TICKER}.json"

    params = {
        "from": TARGET_DATE,
        "till": TARGET_DATE,
        "iss.meta": "off",
    }

    print("ПРОВЕРКА ИСТОРИЧЕСКОГО OI MOEX")
    print("Базовый актив:", TICKER.upper())
    print("Дата:", TARGET_DATE)
    print("URL:", url)

    try:
        response = requests.get(
            url,
            params=params,
            timeout=30
        )

        print("\nHTTP STATUS:", response.status_code)
        print("Ответ сервера:", response.reason)

        response.raise_for_status()

        result = response.json()

        print("\n=== РАЗДЕЛЫ ОТВЕТА ===")
        print(list(result.keys()))

        for section_name, section in result.items():
            if not isinstance(section, dict):
                continue

            columns = section.get("columns", [])
            rows = section.get("data", [])

            print(f"\n=== {section_name} ===")
            print("Поля:", columns)
            print("Количество строк:", len(rows))

            for row in rows[:12]:
                print(dict(zip(columns, row)))

        print("\n=== ПОЛНЫЙ РЕЗУЛЬТАТ ===")
        print(json.dumps(result, ensure_ascii=False)[:12000])

    except requests.exceptions.HTTPError as error:
        print("\nHTTP ОШИБКА:", error)
        print("Тело ответа:")
        print(response.text[:3000])

    except Exception as error:
        print("\nОШИБКА:", repr(error))


if __name__ == "__main__":
    main()
