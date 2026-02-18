"""
Filtros duros: zona, ambientes, terraza (m²), toilete, precio.
"""

import config
from zonaprop_scraper import parse_currency


def _norm_barrio(s: str | None) -> str:
    if not s:
        return ""
    # Normalizar acentos para matchear "Vicente López" / "vicente lopez"
    b = (s or "").strip().lower()
    for old, new in [("ó", "o"), ("á", "a"), ("é", "e"), ("í", "i"), ("ú", "u"), ("ñ", "n")]:
        b = b.replace(old, new)
    return b


def _zone_from_source_url(source_url: str | None) -> bool:
    """Si el aviso viene de una búsqueda VL o Palermo, damos por válida la zona."""
    if not source_url:
        return False
    u = source_url.lower()
    if "vicente-lopez" in u or "vicente_lopez" in u:
        return True
    if "palermo" in u:
        return True
    return False


def _barrio_permitted(barrio: str) -> bool:
    """Barrio en lista Vicente López o Palermo corredor norte."""
    b = _norm_barrio(barrio)
    if not b:
        return False
    allowed_norm = [_norm_barrio(a) for a in config.BARRIOS_VICENTE_LOPEZ + config.BARRIOS_PALERMO_CORREDOR_NORTE]
    for allowed in allowed_norm:
        if allowed in b or b in allowed:
            return True
    return False


def _get_price_value_currency(record: dict) -> tuple[int | None, str | None]:
    """Precio del alquiler: de ficha o de listado (tarjeta usa POSTING_CARD_PRICE_*)."""
    if record.get("precio_value") is not None and record.get("precio_currency"):
        return record["precio_value"], record["precio_currency"]
    if record.get("POSTING_CARD_PRICE_value") is not None and record.get("POSTING_CARD_PRICE_currency"):
        return record["POSTING_CARD_PRICE_value"], record["POSTING_CARD_PRICE_currency"]
    raw = record.get("alquiler_texto") or record.get("price_raw") or ""
    if not raw:
        return None, None
    return parse_currency(raw)


def passes_price(record: dict) -> bool:
    """Alquiler <= 1000 USD o <= 1.450.000 ARS."""
    value, currency = _get_price_value_currency(record)
    if value is None:
        return False
    if currency == "USD":
        return value <= config.MAX_USD
    if currency == "ARS":
        return value <= config.MAX_ARS
    return False


def passes_zone(record: dict) -> bool:
    """Barrio en listas permitidas, o zona inferida desde la URL de búsqueda (ej. vicente-lopez, palermo)."""
    if _barrio_permitted(record.get("barrio") or ""):
        return True
    return _zone_from_source_url(record.get("_source_url"))


def passes_ambientes(record: dict) -> bool:
    """Al menos 2 ambientes."""
    a = record.get("ambientes")
    if a is None:
        return False
    try:
        return int(a) >= 2
    except (TypeError, ValueError):
        return False


def passes_terraza(record: dict) -> bool:
    """m² totales > m² cubiertos y diferencia >= DELTA_MIN_TERRAZA."""
    tot = record.get("m2_totales")
    cub = record.get("m2_cubiertos")
    if tot is None or cub is None:
        return False
    try:
        t, c = int(tot), int(cub)
        return t > c and (t - c) >= config.DELTA_MIN_TERRAZA
    except (TypeError, ValueError):
        return False


def passes_toilete(record: dict) -> bool:
    """Tiene toilete (campo de ficha)."""
    return bool(record.get("tiene_toilete"))


def passes_all_hard_filters(record: dict) -> bool:
    """Aplica todos los filtros duros. El record debe tener datos de listado + ficha mergeados."""
    return (
        passes_price(record)
        and passes_zone(record)
        and passes_ambientes(record)
        and passes_terraza(record)
        and passes_toilete(record)
    )
