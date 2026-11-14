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
