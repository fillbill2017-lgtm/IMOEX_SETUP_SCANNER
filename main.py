
import requests

URL = (
    "https://iss.moex.com/iss/analyticalproducts/"
    "futoi/securities/mx.json"
)

TARGET_DATE = "2026-10-15"


def main():
    params = {
        "from": TARGET_DATE,
        "till": TARGET_DATE,
        "iss.meta": "off",
    }

    print("ПРОВЕРКА ИСТОРИЧЕСКОГО OI MIX")
    print("Дата:", TARGET_DATE)

    response = requests.get(URL, params=params, timeout=30)

    print("HTTP STATUS:", response.status_code)
    response.raise_for_status()

    result = response.json()

    section = result.get("futoi", {})
    columns = section.get("columns", [])
    rows = section.get("data", [])

    print("\n=== ПОЛЯ ===")
    print(columns)

    print("\n=== КОЛИЧЕСТВО ЗАПИСЕЙ ===")
    print(len(rows))

    if columns == ["ERROR_MESSAGE"]:
        print("\nОШИБКА MOEX:")
        for row in rows:
            print(row[0])
        return

    if not rows:
        print("\nДАННЫЕ НЕ ВОЗВРАЩЕНЫ")
        return

    print("\n=== ПЕРВЫЕ 20 ЗАПИСЕЙ ===")

    for row in rows[:20]:
        print(dict(zip(columns, row)))

    print("\n=== ПОСЛЕДНИЕ 10 ЗАПИСЕЙ ===")

    for row in rows[-10:]:
        print(dict(zip(columns, row)))

    print("\n=== ПРОВЕРКА ЗАВЕРШЕНА ===")


if __name__ == "__main__":
    main()
