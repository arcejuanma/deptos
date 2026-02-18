"""
Scrape del listado ZonaProp usando Playwright (navegador real) como fallback.
Se usa cuando cloudscraper falla con 403.
"""

import time
from bs4 import BeautifulSoup

from zonaprop_scraper import parse_card


def fetch_listing_page_playwright(page, url: str) -> list[dict]:
    """
    Obtiene HTML de una página de listado usando Playwright (navegador real).
    Útil cuando cloudscraper es bloqueado con 403.
    """
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(2)  # Esperar un poco más para que cargue el contenido dinámico
        html = page.content()
        soup = BeautifulSoup(html, "lxml")
        cards = soup.find_all("div", attrs={"data-posting-type": True})
        if not cards:
            cards = soup.select("[data-to-posting]")
        if not cards:
            print(f"  ⚠️  No se encontraron tarjetas en {url}")
            print(f"     Tamaño HTML: {len(html)} bytes")
        out = []
        for node in cards:
            row = parse_card(node)
            if row and row.get("url"):
                out.append(row)
        return out
    except Exception as e:
        print(f"  ⚠️  Error con Playwright en {url}: {e}")
        return []
