#!/usr/bin/env python3
"""
Carga inicial de anuncios: scrape con paginación + filtro de precio.
Sin ficha detalle ni Telegram/Supabase. Solo listado paginado y precio <= 1000 USD o 1.450.000 ARS.
Uso: python run_local.py
"""

import time
from urllib.parse import urljoin

import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup

import config
from zonaprop_scraper import parse_card, parse_currency

BASE = "https://www.zonaprop.com.ar"


def page_url(base: str, page: int) -> str:
    """URL de la página N. Paginación ZonaProp: -pagina-N antes de .html."""
    base = base.split("?")[0].rstrip("/")
    if not base.endswith(".html"):
        base = base + ".html"
    if page == 1:
        return base
    # insertar -pagina-N antes de .html
    return base.replace(".html", f"-pagina-{page}.html")


def get_price_value_currency(row: dict) -> tuple[int | None, str | None]:
    """Obtiene (valor numérico, moneda) del alquiler para filtrar. ARS o USD."""
    if row.get("POSTING_CARD_PRICE_value") is not None and row.get("POSTING_CARD_PRICE_currency"):
        return row["POSTING_CARD_PRICE_value"], row["POSTING_CARD_PRICE_currency"]
    raw = row.get("alquiler_texto") or row.get("price_raw") or ""
    if not raw:
        return None, None
    return parse_currency(raw)


def passes_price_filter(row: dict) -> bool:
    """Precio <= 1000 USD o <= 1.450.000 ARS."""
    value, currency = get_price_value_currency(row)
    if value is None:
        return False
    if currency == "USD":
        return value <= config.MAX_USD
    if currency == "ARS":
        return value <= config.MAX_ARS
    return False


def main():
    print("Carga inicial: listado con paginación + filtro de precio")
    print(f"Precio máx: {config.MAX_USD} USD o {config.MAX_ARS:,} ARS")
    print(f"Páginas por URL: {config.MAX_PAGES_PER_URL}")
    print(f"URLs: {len(config.SEARCH_URLS)}\n")

    session = cloudscraper.create_scraper()
    seen_urls = set()
    all_rows = []

    for base_url in config.SEARCH_URLS:
        base_url = base_url.split("?")[0].rstrip("/")
        if not base_url.endswith(".html"):
            base_url = base_url + ".html"
        for page in range(1, config.MAX_PAGES_PER_URL + 1):
            url = page_url(base_url, page)
            print(f"  {url}")
            try:
                r = session.get(url)
                r.raise_for_status()
                html = r.text
            except Exception as e:
                print(f"    Error: {e}")
                continue
            soup = BeautifulSoup(html, "lxml")
            cards = soup.find_all("div", attrs={"data-posting-type": True})
            if not cards:
                cards = soup.select("[data-to-posting]")
            if not cards:
                print(f"    Sin tarjetas (¿última página?)")
                break
            for node in cards:
                row = parse_card(node)
                if not row or not row.get("url"):
                    continue
                if row["url"] in seen_urls:
                    continue
                seen_urls.add(row["url"])
                if not passes_price_filter(row):
                    continue
                row["_source_url"] = base_url
                row["_page"] = page
                all_rows.append(row)
            time.sleep(config.SLEEP_BETWEEN_PAGES)

    df = pd.DataFrame(all_rows)
    out = "zonaprop_carga_inicial.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nAvisos que pasan filtro de precio: {len(all_rows)}")
    print(f"Guardado en {out}")


if __name__ == "__main__":
    main()
