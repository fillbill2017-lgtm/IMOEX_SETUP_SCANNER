
import requests
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

URL = "https://iss.moex.com/iss/engines/stock/markets/index/securities/IMOEX/candles.json"

PAGE_SIZE = 500
LOOKBACK_DAYS = 30
INTERVAL_MINUTES = 10
MOSCOW = ZoneInfo("Europe/Moscow")


def load_candles():
    now = datetime.now(MOSCOW)
    date_from = now.date() - timedelta(days=LOOKBACK_DAYS)

    params = {
        "interval": INTERVAL_MINUTES,
        "from": date_from.isoformat(),
        "till": now.date().isoformat(),
        "start": 0,
        "iss.meta": "off",
    }

    candles = []
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

        candles.extend(dict(zip(columns, row)) for row in rows)
        start += len(rows)

        if len(rows) < PAGE_SIZE:
            break

    return candles, now


def main():
    try:
        raw, now = load_candles()

        if not raw:
            print("MOEX ISS не вернула свечи.")
            return

        print("=== КОНТРОЛЬ КАЧЕСТВА IMOEX ===")
        print("Всего получено строк:", len(raw))

        # Проверка обязательных полей
        required = {"begin", "open", "high", "low", "close"}
        missing_fields = required.difference(raw[0].keys())

        if missing_fields:
            print("ОШИБКА. Нет полей:", sorted(missing_fields))
            return

        # Проверка дубликатов
        timestamps = [c.get("begin") for c in raw]
        valid_timestamps = [t for t in timestamps if t]

        duplicate_count = (
            len(valid_timestamps) - len(set(valid_timestamps))
        )

        missing_time_count = len(raw) - len(valid_timestamps)

        # Удаляем дубликаты только после подсчёта
        unique = {}
        for candle in raw:
            if candle.get("begin"):
                unique[candle["begin"]] = candle

        candles = sorted(
            unique.values(),
            key=lambda c: c["begin"]
        )

        # Проверка корректности OHLC
        invalid = []

        for c in candles:
            try:
                o = float(c["open"])
                h = float(c["high"])
                l = float(c["low"])
                close = float(c["close"])

                if min(o, h, l, close) <= 0:
                    raise ValueError("Цена не положительная")

                if h < max(o, l, close):
                    raise ValueError("Некорректный максимум")

                if l > min(o, h, close):
                    raise ValueError("Некорректный минимум")

            except (ValueError, TypeError, KeyError):
                invalid.append(c)

        # Исключаем ещё не закрытые свечи
        completed = []

        for c in candles:
            begin = datetime.strptime(
                c["begin"], "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=MOSCOW)

            candle_end = begin + timedelta(
                minutes=INTERVAL_MINUTES
            )

            if candle_end <= now:
                completed.append(c)

        # Разрывы между свечами внутри одного календарного дня
        gaps = []

        for previous, current in zip(
            completed, completed[1:]
        ):
            t1 = datetime.strptime(
                previous["begin"], "%Y-%m-%d %H:%M:%S"
            )
            t2 = datetime.strptime(
                current["begin"], "%Y-%m-%d %H:%M:%S"
            )

            if t1.date() == t2.date():
                minutes = int((t2 - t1).total_seconds() / 60)

                if minutes > INTERVAL_MINUTES:
                    gaps.append((previous["begin"], current["begin"], minutes))

        print("Дубликатов:", duplicate_count)
        print("Строк без времени:", missing_time_count)
        print("Некорректных OHLC:", len(invalid))
        print("Незакрытых свечей исключено:", len(candles) - len(completed))
        print("Разрывов внутри дня:", len(gaps))
        print("Закрытых уникальных свечей:", len(completed))

        if invalid:
            print("\nПримеры некорректных свечей:")
            for c in invalid[:5]:
                print(c)

        if gaps:
            print("\nПримеры внутридневных разрывов:")
            for gap in gaps[:10]:
                print(
                    f"{gap[0]} -> {gap[1]} "
                    f"({gap[2]} минут)"
                )

        print("\nПоследние 10 закрытых свечей:")

        for c in completed[-10:]:
            print(
                f"{c['begin']} | "
                f"O:{c['open']} H:{c['high']} "
                f"L:{c['low']} C:{c['close']}"
            )

        if completed:
            print("\nПервая закрытая:", completed[0]["begin"])
            print("Последняя закрытая:", completed[-1]["begin"])

    except requests.RequestException as error:
        print("Ошибка подключения:", error)
    except (ValueError, KeyError, TypeError) as error:
        print("Ошибка обработки данных:", error)


if __name__ == "__main__":
    main()
