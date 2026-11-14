
import requests
import csv
from datetime import datetime
from statistics import median

# =========================================================
# НАСТРОЙКИ
# =========================================================

SECID = "MXZ6"
DATE_FROM = "2026-10-01"
DATE_TILL = "2026-11-13"

URL = (
    "https://iss.moex.com/iss/engines/futures/markets/forts/"
    f"boards/rfud/securities/{SECID}/candles.json"
)

LEFT = 2
RIGHT = 2

ATR_PERIOD = 14
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
VOLUME_PERIOD = 20

# Начальное тестовое допущение.
ZONE_ATR_FACTOR = 0.25
MIN_ZONE_PIVOTS = 2


# =========================================================
# 1. ЗАГРУЗКА ДАННЫХ MOEX
# =========================================================

def load_candles():
    result = []
    start = 0

    while True:
        params = {
            "from": DATE_FROM,
            "till": DATE_TILL,
            "interval": 10,
            "start": start,
            "limit": 500,
            "iss.meta": "off"
        }

        response = requests.get(
            URL,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        block = response.json().get("candles", {})
        columns = block.get("columns", [])
        data = block.get("data", [])

        if not data:
            break

        result.extend(
            dict(zip(columns, row))
            for row in data
        )

        start += len(data)

    return sorted(
        result,
        key=lambda x: x["begin"]
    )


# =========================================================
# 2. РАЗДЕЛЕНИЕ НА СЕССИИ
# =========================================================

def split_sessions(rows):
    sessions = []
    current = []

    for row in rows:
        if current:
            previous = datetime.fromisoformat(
                current[-1]["begin"]
            )

            actual = datetime.fromisoformat(
                row["begin"]
            )

            minutes = (
                actual - previous
            ).total_seconds() / 60

            if minutes > 10:
                sessions.append(current)
                current = []

        current.append(row)

    if current:
        sessions.append(current)

    return sessions


# =========================================================
# 3. АГРЕГАЦИЯ ТАЙМФРЕЙМОВ
# =========================================================

def aggregate_sessions(sessions, size):
    bars = []

    for session_id, session in enumerate(sessions, 1):
        for start in range(0, len(session), size):
            chunk = session[start:start + size]

            complete = len(chunk) == size

            bars.append({
                "session_id": session_id,
                "begin": chunk[0]["begin"],
                "end": chunk[-1]["end"],
                "open": float(chunk[0]["open"]),
                "high": max(
                    float(x["high"]) for x in chunk
                ),
                "low": min(
                    float(x["low"]) for x in chunk
                ),
                "close": float(chunk[-1]["close"]),
                "volume": sum(
                    float(x["volume"]) for x in chunk
                ),
                "source_count": len(chunk),
                "is_complete": complete
            })

    return bars


# =========================================================
# 4. EMA
# =========================================================

def calculate_ema(values, period):
    result = [None] * len(values)

    if len(values) < period:
        return result

    initial = sum(values[:period]) / period
    result[period - 1] = initial

    multiplier = 2 / (period + 1)
    previous = initial

    for i in range(period, len(values)):
        current = (
            values[i] * multiplier
            + previous * (1 - multiplier)
        )

        result[i] = current
        previous = current

    return result


# =========================================================
# 5. RSI WILDER
# =========================================================

def calculate_rsi(values, period=14):
    result = [None] * len(values)

    if len(values) <= period:
        return result

    gains = []
    losses = []

    for i in range(1, period + 1):
        change = values[i] - values[i - 1]

        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    average_gain = sum(gains) / period
    average_loss = sum(losses) / period

    def get_rsi(gain, loss):
        if loss == 0:
            return 100.0 if gain > 0 else 50.0

        rs = gain / loss

        return 100 - (100 / (1 + rs))

    result[period] = get_rsi(
        average_gain,
        average_loss
    )

    for i in range(period + 1, len(values)):
        change = values[i] - values[i - 1]

        gain = max(change, 0)
        loss = max(-change, 0)

        average_gain = (
            average_gain * (period - 1) + gain
        ) / period

        average_loss = (
            average_loss * (period - 1) + loss
        ) / period

        result[i] = get_rsi(
            average_gain,
            average_loss
        )

    return result


# =========================================================
# 6. ATR WILDER
# =========================================================

def calculate_atr(bars, period=14):
    result = [None] * len(bars)

    if len(bars) <= period:
        return result

    true_ranges = []

    for i, bar in enumerate(bars):
        high = bar["high"]
        low = bar["low"]

        if i == 0:
            tr = high - low
        else:
            previous_close = bars[i - 1]["close"]

            tr = max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close)
            )

        true_ranges.append(tr)

    initial = sum(
        true_ranges[1:period + 1]
    ) / period

    result[period] = initial
    previous = initial

    for i in range(period + 1, len(bars)):
        current = (
            previous * (period - 1)
            + true_ranges[i]
        ) / period

        result[i] = current
        previous = current

    return result


# =========================================================
# 7. ИНДИКАТОРЫ И ОБЪЁМ
# =========================================================

def enrich_indicators(bars):
    if not bars:
        return bars

    indices = [
        i for i, bar in enumerate(bars)
        if bar.get("is_complete", True)
    ]

    usable = [
        bars[i] for i in indices
    ]

    if not usable:
        return bars

    closes = [
        x["close"] for x in usable
    ]

    volumes = [
        x["volume"] for x in usable
    ]

    ema20 = calculate_ema(
        closes,
        EMA_FAST
    )

    ema50 = calculate_ema(
        closes,
        EMA_SLOW
    )

    rsi = calculate_rsi(
        closes,
        RSI_PERIOD
    )

    atr = calculate_atr(
        usable,
        ATR_PERIOD
    )

    ema12 = calculate_ema(closes, 12)
    ema26 = calculate_ema(closes, 26)

    macd_line = [None] * len(usable)

    for i in range(len(usable)):
        if (
            ema12[i] is not None
            and ema26[i] is not None
        ):
            macd_line[i] = (
                ema12[i] - ema26[i]
            )

    macd_signal = [None] * len(usable)

    first_macd = next(
        (
            i for i, value in enumerate(macd_line)
            if value is not None
        ),
        None
    )

    if first_macd is not None:
        valid_macd = macd_line[first_macd:]

        valid_signal = calculate_ema(
            valid_macd,
            9
        )

        for j, value in enumerate(valid_signal):
            macd_signal[first_macd + j] = value

    for j, original_index in enumerate(indices):
        bar = bars[original_index]

        # Средний объём предыдущих 20 свечей.
        # Текущая свеча в среднее не включается.
        if j >= VOLUME_PERIOD:
            average_volume = sum(
                volumes[j - VOLUME_PERIOD:j]
            ) / VOLUME_PERIOD
        else:
            average_volume = None

        if (
            average_volume is not None
            and average_volume > 0
        ):
            volume_ratio = (
                volumes[j] / average_volume
            )
        else:
            volume_ratio = None

        macd = macd_line[j]
        signal = macd_signal[j]

        histogram = (
            macd - signal
            if macd is not None and signal is not None
            else None
        )

        bar["ema20"] = ema20[j]
        bar["ema50"] = ema50[j]
        bar["rsi14"] = rsi[j]
        bar["macd"] = macd
        bar["macd_signal"] = signal
        bar["macd_histogram"] = histogram
        bar["atr14"] = atr[j]
        bar["volume_sma20"] = average_volume
        bar["volume_ratio20"] = volume_ratio

    return bars


# =========================================================
# 8. ПОИСК ПОДТВЕРЖДЁННЫХ ЭКСТРЕМУМОВ
# =========================================================

def detect_pivots(
    bars,
    left=LEFT,
    right=RIGHT,
    cross_sessions=False
):
    pivots = []

    if cross_sessions:
        sequences = [[
            x for x in bars
            if x["is_complete"]
        ]]
    else:
        session_ids = sorted(
            set(x["session_id"] for x in bars)
        )

        sequences = []

        for session_id in session_ids:
            sequence = [
                x for x in bars
                if x["session_id"] == session_id
                and x["is_complete"]
            ]

            sequences.append(sequence)

    for sequence in sequences:
        for i in range(
            left,
            len(sequence) - right
        ):
            bar = sequence[i]

            previous = sequence[i-left:i]
            following = sequence[i+1:i+right+1]

            is_high = (
                all(
                    bar["high"] > x["high"]
                    for x in previous
                )
                and all(
                    bar["high"] > x["high"]
                    for x in following
                )
            )

            is_low = (
                all(
                    bar["low"] < x["low"]
                    for x in previous
                )
                and all(
                    bar["low"] < x["low"]
                    for x in following
                )
            )

            confirmed_at = following[-1]["end"]

            if is_high:
                pivots.append({
                    "session_id": bar["session_id"],
                    "type": "HIGH",
                    "time": bar["begin"],
                    "confirmed_at": confirmed_at,
                    "price": bar["high"]
                })

            if is_low:
                pivots.append({
                    "session_id": bar["session_id"],
                    "type": "LOW",
                    "time": bar["begin"],
                    "confirmed_at": confirmed_at,
                    "price": bar["low"]
                })

    return sorted(
        pivots,
        key=lambda x: (x["time"], x["type"])
    )


# =========================================================
# 9. КЛАССИФИКАЦИЯ ЭКСТРЕМУМОВ
# =========================================================

def classify_pivots(pivots):
    previous = {
        "HIGH": None,
        "LOW": None
    }

    for pivot in pivots:
        kind = pivot["type"]
        old = previous[kind]

        if old is None:
            label = "FIRST"

        elif pivot["price"] > old:
            label = (
                "HH" if kind == "HIGH" else "HL"
            )

        elif pivot["price"] < old:
            label = (
                "LH" if kind == "HIGH" else "LL"
            )

        else:
            label = "EQUAL"

        pivot["structure"] = label
        previous[kind] = pivot["price"]

    return pivots


# =========================================================
# 10. ПОСТРОЕНИЕ КАРТЫ УРОВНЕЙ 4H
# =========================================================

def count_touch_episodes(bars, zone_low, zone_high, start_time):
    """
    Считает отдельные эпизоды контакта 4H-свечей с зоной.
    Несколько подряд идущих свечей внутри/на границе зоны = один эпизод.
    Учитываются только свечи после первого подтверждения экстремума,
    образовавшего кластер. Это описательная статистика текущей карты,
    не готовая логика исторического тестирования.
    """
    touches = []
    in_episode = False

    for bar in bars:
        if not bar.get("is_complete", False):
            continue

        if bar["end"] <= start_time:
            continue

        intersects = (
            bar["high"] >= zone_low
            and bar["low"] <= zone_high
        )

        if intersects and not in_episode:
            touches.append({
                "time": bar["begin"],
                "end": bar["end"]
            })

        in_episode = intersects

    return touches


def merge_overlapping_zones(zones):
    """
    Объединяет только геометрически пересекающиеся зоны одного типа.
    HIGH и LOW никогда не объединяются между собой.
    """
    merged = []

    for zone_type in ("RESISTANCE", "SUPPORT"):
        group = sorted(
            [z for z in zones if z["zone_type"] == zone_type],
            key=lambda z: (z["zone_low"], z["zone_high"])
        )

        current = None

        for zone in group:
            if current is None:
                current = dict(zone)
                current["_prices"] = list(zone["_prices"])
                current["_pivots"] = list(zone["_pivots"])
                continue

            if zone["zone_low"] <= current["zone_high"]:
                current["zone_low"] = min(
                    current["zone_low"], zone["zone_low"]
                )
                current["zone_high"] = max(
                    current["zone_high"], zone["zone_high"]
                )
                current["_prices"].extend(zone["_prices"])
                current["_pivots"].extend(zone["_pivots"])
            else:
                merged.append(current)
                current = dict(zone)
                current["_prices"] = list(zone["_prices"])
                current["_pivots"] = list(zone["_pivots"])

        if current is not None:
            merged.append(current)

    return merged


def build_level_map(
    pivots,
    atr_value,
    latest_price,
    complete_bars
):
    if atr_value is None or atr_value <= 0:
        return [], None

    tolerance = atr_value * ZONE_ATR_FACTOR
    raw_zones = []

    # Максимумы и минимумы кластеризуются раздельно.
    for pivot_type in ("HIGH", "LOW"):
        typed_pivots = sorted(
            [p for p in pivots if p["type"] == pivot_type],
            key=lambda x: x["price"]
        )

        clusters = []
        current = []

        for pivot in typed_pivots:
            if not current:
                current = [pivot]
                continue

            cluster_min = current[0]["price"]

            if pivot["price"] - cluster_min <= tolerance:
                current.append(pivot)
            else:
                clusters.append(current)
                current = [pivot]

        if current:
            clusters.append(current)

        for cluster in clusters:
            if len(cluster) < MIN_ZONE_PIVOTS:
                continue

            prices = [p["price"] for p in cluster]
            center = median(prices)
            zone_low = min(prices) - tolerance / 2
            zone_high = max(prices) + tolerance / 2

            confirmations = sorted(
                p["confirmed_at"] for p in cluster
            )
            pivot_times = sorted(p["time"] for p in cluster)
            first_confirmation = confirmations[0]
            last_confirmation = confirmations[-1]

            zone_type = (
                "RESISTANCE" if pivot_type == "HIGH" else "SUPPORT"
            )

            raw_zones.append({
                "zone_type": zone_type,
                "zone_low": zone_low,
                "zone_high": zone_high,
                "center": center,
                "pivot_count": len(cluster),
                "high_count": len(cluster) if pivot_type == "HIGH" else 0,
                "low_count": len(cluster) if pivot_type == "LOW" else 0,
                "first_pivot_time": pivot_times[0],
                "last_pivot_time": pivot_times[-1],
                "first_confirmation": first_confirmation,
                "last_confirmation": last_confirmation,
                "_prices": prices,
                "_pivots": list(cluster)
            })

    # Если расширенные границы кластеров пересеклись,
    # объединяем их только внутри одного типа уровня.
    zones = merge_overlapping_zones(raw_zones)

    result = []

    for zone in zones:
        prices = zone["_prices"]
        pivots_in_zone = zone["_pivots"]
        zone_low = zone["zone_low"]
        zone_high = zone["zone_high"]
        center = median(prices)

        # После объединения пересекающихся кластеров обновляем даты.
        first_confirmation = min(
            p["confirmed_at"] for p in pivots_in_zone
        )
        last_confirmation = max(
            p["confirmed_at"] for p in pivots_in_zone
        )
        first_pivot_time = min(
            p["time"] for p in pivots_in_zone
        )
        last_pivot_time = max(
            p["time"] for p in pivots_in_zone
        )

        touches = count_touch_episodes(
            complete_bars,
            zone_low,
            zone_high,
            first_confirmation
        )

        if latest_price > zone_high:
            position = "BELOW_PRICE"
        elif latest_price < zone_low:
            position = "ABOVE_PRICE"
        else:
            position = "PRICE_INSIDE_ZONE"

        result.append({
            "zone_type": zone["zone_type"],
            "zone_low": round(zone_low, 2),
            "zone_high": round(zone_high, 2),
            "center": round(center, 2),
            "pivot_count": len(pivots_in_zone),
            "high_count": sum(
                p["type"] == "HIGH" for p in pivots_in_zone
            ),
            "low_count": sum(
                p["type"] == "LOW" for p in pivots_in_zone
            ),
            "touch_count": len(touches),
            "first_touch": touches[0]["time"] if touches else None,
            "last_touch": touches[-1]["time"] if touches else None,
            "first_pivot_time": first_pivot_time,
            "last_pivot_time": last_pivot_time,
            "first_confirmation": first_confirmation,
            "last_confirmation": last_confirmation,
            "position": position,
            "distance_points": round(center - latest_price, 2),
            "distance_atr": round(
                (center - latest_price) / atr_value, 3
            )
        })

    result.sort(
        key=lambda x: abs(x["center"] - latest_price)
    )

    for index, zone in enumerate(result, 1):
        zone["zone_id"] = index

    return result, tolerance


# =========================================================
# 11. КОНТЕКСТ 1H ОТНОСИТЕЛЬНО УРОВНЕЙ
# =========================================================

def print_1h_context(bars, zones):
    complete = [
        x for x in bars
        if x["is_complete"]
    ]

    if not complete:
        print("Нет полных свечей 1H")
        return

    last = complete[-1]
    price = last["close"]

    print("\n===== КОНТЕКСТ 1H =====")
    print("Время:", last["end"])
    print("Цена закрытия:", price)
    print("EMA20:", last["ema20"])
    print("EMA50:", last["ema50"])
    print("RSI14:", last["rsi14"])
    print("MACD:", last["macd"])
    print("MACD signal:", last["macd_signal"])
    print("MACD histogram:", last["macd_histogram"])
    print("ATR14:", last["atr14"])
    print("Объём:", last["volume"])
    print(
        "Средний объём предыдущих 20:",
        last["volume_sma20"]
    )
    print(
        "Объём / средний:",
        last["volume_ratio20"]
    )

    if last["ema20"] is not None:
        print(
            "Цена относительно EMA20:",
            "ВЫШЕ" if price > last["ema20"]
            else "НИЖЕ" if price < last["ema20"]
            else "НА EMA20"
        )

    if last["ema50"] is not None:
        print(
            "Цена относительно EMA50:",
            "ВЫШЕ" if price > last["ema50"]
            else "НИЖЕ" if price < last["ema50"]
            else "НА EMA50"
        )

    print("\nБЛИЖАЙШИЕ УРОВНИ 4H ПО ЦЕНЕ 1H:")

    if not zones:
        print("Нет зон, прошедших фильтр")
        return

    nearest = sorted(
        zones,
        key=lambda z: abs(z["center"] - price)
    )

    for zone in nearest[:5]:
        if price > zone["zone_high"]:
            position = (
                "НИЖЕ ЦЕНЫ — ПОТЕНЦИАЛЬНАЯ ПОДДЕРЖКА"
            )

        elif price < zone["zone_low"]:
            position = (
                "ВЫШЕ ЦЕНЫ — ПОТЕНЦИАЛЬНОЕ СОПРОТИВЛЕНИЕ"
            )

        else:
            position = "ЦЕНА ВНУТРИ ЗОНЫ"

        distance = zone["center"] - price

        print(
            f'Зона {zone["zone_low"]} - {zone["zone_high"]}',
            f'| центр={zone["center"]}',
            f'| экстремумов={zone["pivot_count"]}',
            f'| расстояние={round(distance, 2)}',
            f'| положение={position}'
        )


# =========================================================
# 12. СОХРАНЕНИЕ CSV
# =========================================================

def save_csv(filename, rows):
    if not rows:
        print("Нет данных:", filename)
        return

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0].keys())
        )

        writer.writeheader()
        writer.writerows(rows)


# =========================================================
# 13. ВЫВОД ИНДИКАТОРОВ
# =========================================================

def print_latest_indicators(name, bars):
    complete = [
        x for x in bars
        if x.get("is_complete", True)
    ]

    if not complete:
        return

    last = complete[-1]

    print(f"\n===== ИНДИКАТОРЫ {name} =====")
    print("Время:", last["end"])
    print("Close:", last["close"])
    print("EMA20:", last["ema20"])
    print("EMA50:", last["ema50"])
    print("RSI14:", last["rsi14"])
    print("MACD:", last["macd"])
    print("MACD signal:", last["macd_signal"])
    print("MACD histogram:", last["macd_histogram"])
    print("ATR14:", last["atr14"])
    print("Volume:", last["volume"])
    print("Volume SMA20:", last["volume_sma20"])
    print("Volume ratio:", last["volume_ratio20"])


# =========================================================
# 14. MAIN
# =========================================================

def main():
    print("=" * 60)
    print("MIX LEVEL MAP V1.1")
    print("Инструмент:", SECID)
    print("Период:", DATE_FROM, "-", DATE_TILL)
    print("=" * 60)

    candles = load_candles()

    if not candles:
        print("MOEX не вернула свечи")
        return

    sessions = split_sessions(candles)

    print("\nИсходных свечей:", len(candles))
    print("Торговых сессий:", len(sessions))

    # 10M
    bars_10m = [
        {
            "begin": x["begin"],
            "end": x["end"],
            "open": float(x["open"]),
            "high": float(x["high"]),
            "low": float(x["low"]),
            "close": float(x["close"]),
            "volume": float(x["volume"]),
            "is_complete": True
        }
        for x in candles
    ]

    bars_10m = enrich_indicators(bars_10m)

    # Агрегация
    bars_30m = aggregate_sessions(sessions, 3)
    bars_1h = aggregate_sessions(sessions, 6)
    bars_4h = aggregate_sessions(sessions, 24)

    # Индикаторы
    bars_30m = enrich_indicators(bars_30m)
    bars_1h = enrich_indicators(bars_1h)
    bars_4h = enrich_indicators(bars_4h)

    # Экстремумы
    pivots_30m = classify_pivots(
        detect_pivots(
            bars_30m,
            cross_sessions=False
        )
    )

    pivots_1h = classify_pivots(
        detect_pivots(
            bars_1h,
            cross_sessions=False
        )
    )

    pivots_4h = classify_pivots(
        detect_pivots(
            bars_4h,
            cross_sessions=True
        )
    )

    complete_4h = [
        x for x in bars_4h
        if x["is_complete"]
    ]

    complete_1h = [
        x for x in bars_1h
        if x["is_complete"]
    ]

    if not complete_4h or not complete_1h:
        print("Недостаточно полных свечей")
        return

    last_4h = complete_4h[-1]
    last_1h = complete_1h[-1]

    # Текущая карта уровней
    zones, tolerance = build_level_map(
        pivots_4h,
        last_4h["atr14"],
        last_4h["close"],
        complete_4h
    )

    print("\n===== КОНТРОЛЬ ДАННЫХ =====")
    print("Последняя 10M свеча:", candles[-1]["begin"])
    print("Последняя полная 1H:", last_1h["end"])
    print("Последняя полная 4H:", last_4h["end"])

    print("\n===== 4H LEVEL MAP V1.1 =====")
    print("Полных свечей 4H:", len(complete_4h))
    print(
        "Подтверждённых максимумов:",
        sum(x["type"] == "HIGH" for x in pivots_4h)
    )
    print(
        "Подтверждённых минимумов:",
        sum(x["type"] == "LOW" for x in pivots_4h)
    )
    print("Цена 4H:", last_4h["close"])
    print("ATR14 4H:", last_4h["atr14"])
    print("Допуск объединения зон:", tolerance)

    print("\nНАЙДЕННЫЕ ЗНАЧИМЫЕ ЗОНЫ:")

    if not zones:
        print("Зоны не найдены")
    else:
        for zone in zones:
            print(
                f'#{zone["zone_id"]}',
                f'{zone["zone_low"]} - {zone["zone_high"]}',
                f'центр={zone["center"]}',
                f'тип={zone["zone_type"]}',
                f'экстремумов={zone["pivot_count"]}',
                f'касания={zone["touch_count"]}',
                f'первый экстремум={zone["first_pivot_time"]}',
                f'последнее подтверждение={zone["last_confirmation"]}',
                f'положение={zone["position"]}'
            )

    print_1h_context(
        bars_1h,
        zones
    )

    print_latest_indicators(
        "30M",
        bars_30m
    )

    print_latest_indicators(
        "10M",
        bars_10m
    )

    print_latest_indicators(
        "4H",
        bars_4h
    )

    # Сохранение файлов
    save_csv(
        f"{SECID}_4H_PIVOTS_V1_1.csv",
        pivots_4h
    )

    save_csv(
        f"{SECID}_1H_PIVOTS_V1_1.csv",
        pivots_1h
    )

    save_csv(
        f"{SECID}_30M_PIVOTS_V1_1.csv",
        pivots_30m
    )

    save_csv(
        f"{SECID}_4H_LEVEL_MAP_V1_1.csv",
        zones
    )

    save_csv(
        f"{SECID}_4H_INDICATORS_V1_1.csv",
        complete_4h
    )

    save_csv(
        f"{SECID}_1H_INDICATORS_V1_1.csv",
        complete_1h
    )

    save_csv(
        f"{SECID}_30M_INDICATORS_V1_1.csv",
        [
            x for x in bars_30m
            if x["is_complete"]
        ]
    )

    save_csv(
        f"{SECID}_10M_INDICATORS_V1_1.csv",
        bars_10m
    )

    print("\n===== ФАЙЛЫ СОХРАНЕНЫ =====")
    print("4H_LEVEL_MAP")
    print("4H_PIVOTS")
    print("1H_PIVOTS")
    print("30M_PIVOTS")
    print("4H_INDICATORS")
    print("1H_INDICATORS")
    print("30M_INDICATORS")
    print("10M_INDICATORS")

    print("\nАНАЛИЗ ЗАВЕРШЁН")
    print("Торговые сигналы не формировались.")


if __name__ == "__main__":
    main()
