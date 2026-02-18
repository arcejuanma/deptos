#!/usr/bin/env python3
"""
Bot de alquileres ZonaProp: scrape → filtros duros → Supabase (dedup) → Telegram.
Ejecutar en local o en cloud; mismo código. Requiere SUPABASE_*, TELEGRAM_* en env.
Prueba rápida: python run_bot.py --one-page  (solo la primera página de la primera URL)
"""

import os
import sys
import time

import config
import telegram_notify
from scraper.detail import fetch_and_parse_detail
from scraper.filters import passes_all_hard_filters, passes_price
from scraper.listing import scrape_all_listings
import supabase_store

from scraper.session import create_scraper_session


def main():
    one_page = "--one-page" in sys.argv or "-1" in sys.argv
    max_listings = None
    for i, arg in enumerate(sys.argv):
        if arg in ("--max-listings", "-n") and i + 1 < len(sys.argv):
            try:
                max_listings = int(sys.argv[i + 1])
            except ValueError:
                pass
            break
    if one_page:
        search_urls = config.SEARCH_URLS[:1]
        max_pages = 1
        print("Bot alquileres ZonaProp [prueba 1 página]")
    else:
        search_urls = config.SEARCH_URLS
        max_pages = config.MAX_PAGES_PER_URL
        print("Bot alquileres ZonaProp")
    if max_listings:
        print(f"  Límite: {max_listings} avisos en listado")
    print("Scrape → filtros → Supabase → Telegram\n")

    for var in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        if not os.environ.get(var, "").strip():
            print(f"Falta variable de entorno: {var}")
            return

    # Crear scraper con configuración para evitar detección
    session = create_scraper_session()

    # URLs ya en Supabase (notificadas) o en caché reciente → no contar como "nuevos"
    known_urls = supabase_store.get_known_urls(
        include_recent_fichas=True,
        fichas_max_age_hours=config.SKIP_RECENT_FICHAS_HOURS,
    )
    print(f"URLs ya conocidas (Supabase + caché reciente): {len(known_urls)}")

    # 1. Listados con paginación (orden publicado descendente; se omiten known_urls hasta llenar N nuevos)
    print("Scrapeando listados...")
    list_rows = scrape_all_listings(
        session,
        search_urls,
        max_pages,
        config.SLEEP_BETWEEN_PAGES,
        max_listings=max_listings,
        skip_urls=known_urls,
    )
    print(f"  Avisos únicos en listado: {len(list_rows)}")

    # 2. Ficha por aviso y filtros duros (filtro de precio en listado para no pedir ficha de avisos caros)
    from scraper.filters import passes_zone, passes_ambientes, passes_terraza, passes_toilete
    candidates = []
    stats = {"price_ok": 0, "detail_ok": 0, "zone_ok": 0, "amb_ok": 0, "terraza_ok": 0, "toilete_ok": 0}
    for i, row in enumerate(list_rows):
        url = row.get("url")
        if not url:
            continue
        if not passes_price(row):
            continue
        stats["price_ok"] += 1
        # Usar caché de ficha si ya la scrapeamos hace poco (no volver a entrar al detalle)
        detail = supabase_store.get_cached_ficha(url, max_age_hours=24)
        if detail is None:
            detail = fetch_and_parse_detail(session, url)
            time.sleep(config.SLEEP_BETWEEN_DETAILS)
        if not detail:
            continue
        stats["detail_ok"] += 1
        merged = {**row, **{k: v for k, v in detail.items() if v is not None and v != ""}}
        if not merged.get("precio_value") and row.get("alquiler_texto"):
            from zonaprop_scraper import parse_currency
            v, c = parse_currency(row["alquiler_texto"])
            merged["precio_value"], merged["precio_currency"] = v, c
        if not merged.get("price_raw") and row.get("alquiler_texto"):
            merged["price_raw"] = row["alquiler_texto"][:300]
        # Guardar en caché el registro enriquecido (listado + ficha) para tener precio en próximas lecturas
        supabase_store.save_ficha_cache(url, merged)
        if passes_zone(merged):
            stats["zone_ok"] += 1
        if passes_ambientes(merged):
            stats["amb_ok"] += 1
        if passes_terraza(merged):
            stats["terraza_ok"] += 1
        if passes_toilete(merged):
            stats["toilete_ok"] += 1
        if passes_all_hard_filters(merged):
            candidates.append(merged)
        if (i + 1) % 10 == 0:
            print(f"  Procesados {i + 1}/{len(list_rows)}...")

    print(f"  Con precio OK: {stats['price_ok']}, con ficha: {stats['detail_ok']}, zona OK: {stats['zone_ok']}, ambientes OK: {stats['amb_ok']}, terraza OK: {stats['terraza_ok']}, toilete OK: {stats['toilete_ok']}")
    print(f"Candidatos que pasan todos los filtros: {len(candidates)}")
    if not candidates and stats["detail_ok"]:
        print("  (Si hay fichas pero 0 candidatos, suele ser: barrio no matchea, faltan m²/ambientes/toilete en la ficha.)")

    # 3. Por cada candidato: si no está en Supabase → Telegram → insert
    sent = 0
    skipped_supabase = 0
    for rec in candidates:
        if supabase_store.already_notified(rec["url"]):
            skipped_supabase += 1
            continue
        try:
            telegram_notify.send_listing_message(rec)
            supabase_store.mark_as_notified(rec)
            sent += 1
            print(f"  Enviado y guardado en Supabase: {rec.get('titulo', rec['url'])[:60]}...")
        except Exception as e:
            print(f"  Error enviando/guardando {rec['url']}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\nListo. Ya estaban en Supabase: {skipped_supabase}, notificados y guardados nuevos: {sent}.")


if __name__ == "__main__":
    main()
