"""
Persistencia en Supabase: consultar si una URL ya fue notificada e insertar tras enviar por Telegram.
Caché de fichas scrapeadas para no volver a entrar al detalle de avisos ya vistos.
"""

import os
from datetime import datetime, timezone, timedelta

TABLE = "publicaciones"
TABLE_FICHAS_CACHE = "fichas_cache"


def _canonical_url(url: str) -> str:
    """Misma publicación puede tener distinta query; usamos URL sin query como clave."""
    if not url:
        return url
    return url.split("?")[0].rstrip("/")


def _client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY")
    return create_client(url, key)


def get_known_urls(
    include_recent_fichas: bool = True,
    fichas_max_age_hours: int = 24,
) -> set[str]:
    """
    URLs ya en publicaciones (notificadas) y, opcionalmente, en fichas_cache recientes.
    Sirve para que el scraper pida más páginas hasta juntar N avisos "nuevos".
    """
    known = set()
    try:
        client = _client()
        r = client.table(TABLE).select("url").execute()
        if r.data:
            for row in r.data:
                u = row.get("url")
                if u:
                    known.add(_canonical_url(u))
        if include_recent_fichas and fichas_max_age_hours > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=fichas_max_age_hours)).isoformat().replace("+00:00", "Z")
            r2 = client.table(TABLE_FICHAS_CACHE).select("url").gte("scraped_at", cutoff).execute()
            if r2.data:
                for row in r2.data:
                    u = row.get("url")
                    if u:
                        known.add(_canonical_url(u))
    except Exception:
        pass
    return known


def already_notified(url: str) -> bool:
    """True si la URL ya está en la tabla (ya se envió por Telegram)."""
    url = _canonical_url(url)
    try:
        client = _client()
        r = client.table(TABLE).select("url").eq("url", url).limit(1).execute()
        return bool(r.data and len(r.data) > 0)
    except Exception:
        return False


def mark_as_notified(record: dict) -> None:
    """
    Inserta la publicación en Supabase después de notificar por Telegram.
    record debe tener al menos 'url'. Opcional: titulo, precio, barrio, ambientes, m2_cubiertos, m2_totales, price_raw.
    """
    try:
        client = _client()
        row = {
            "url": _canonical_url(record["url"]),
            "notified_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        for key in ("titulo", "barrio", "price_raw"):
            v = record.get(key)
            if v is not None and v != "":
                row[key] = str(v)[:500]
        for key in ("ambientes", "m2_cubiertos", "m2_totales"):
            v = record.get(key)
            if v is not None:
                try:
                    row[key] = int(v)
                except (TypeError, ValueError):
                    pass
        # Solo columnas que existen en la tabla (ver README); no insertar "precio" si no está en el schema
        client.table(TABLE).insert(row).execute()
    except Exception as e:
        raise RuntimeError(f"Error insertando en Supabase: {e}") from e


# --- Caché de fichas (evitar re-entrar al detalle de avisos ya scrapeados) ---

def get_cached_ficha(url: str, max_age_hours: int = 24) -> dict | None:
    """
    Si tenemos la ficha de esta URL guardada y es reciente (max_age_hours), la devuelve.
    Devuelve un dict con las mismas keys que parse_detail_html (url, titulo, barrio, ambientes, etc.).
    """
    url = _canonical_url(url)
    try:
        client = _client()
        r = client.table(TABLE_FICHAS_CACHE).select("*").eq("url", url).limit(1).execute()
        if not r.data or len(r.data) == 0:
            return None
        row = r.data[0]
        scraped_at = row.get("scraped_at")
        if not scraped_at:
            return None
        if isinstance(scraped_at, str):
            scraped_at = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
        if scraped_at.tzinfo is None:
            scraped_at = scraped_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - scraped_at > timedelta(hours=max_age_hours):
            return None
        # Reconstruir el dict "detail" para el pipeline
        out = {"url": url, "titulo": row.get("titulo") or "", "barrio": row.get("barrio") or ""}
        for key in ("ambientes", "m2_cubiertos", "m2_totales", "precio_value"):
            out[key] = row.get(key)
        out["tiene_toilete"] = bool(row.get("tiene_toilete"))
        out["price_raw"] = row.get("price_raw") or ""
        out["precio_currency"] = row.get("precio_currency")
        return out
    except Exception:
        return None


def save_ficha_cache(url: str, detail: dict) -> None:
    """Guarda la ficha parseada para esta URL y no tener que scrapear de nuevo en las próximas horas."""
    url = _canonical_url(url)
    try:
        client = _client()
        # Precio: ficha a veces no trae; si pasamos merged, puede venir del listado (alquiler_texto)
        price_raw = (detail.get("price_raw") or detail.get("alquiler_texto") or "")[:300]
        precio_value = detail.get("precio_value")
        precio_currency = detail.get("precio_currency")
        row = {
            "url": url,
            "scraped_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "titulo": (detail.get("titulo") or "")[:500],
            "barrio": (detail.get("barrio") or "")[:200],
            "ambientes": detail.get("ambientes"),
            "m2_cubiertos": detail.get("m2_cubiertos"),
            "m2_totales": detail.get("m2_totales"),
            "tiene_toilete": bool(detail.get("tiene_toilete")),
            "price_raw": price_raw,
            "precio_value": precio_value,
            "precio_currency": precio_currency,
        }
        client.table(TABLE_FICHAS_CACHE).upsert(row, on_conflict="url").execute()
    except Exception:
        pass  # no fallar el flujo si la caché falla
