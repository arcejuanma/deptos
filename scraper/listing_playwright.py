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
        # Configurar user agent y viewport para parecer navegador real
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.set_extra_http_headers({
            'Accept-Language': 'es-AR,es;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        
        # Navegar con timeout más largo y esperar solo a que cargue el DOM
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)  # Esperar a que cargue el contenido dinámico
        
        # Intentar esperar a que aparezcan las tarjetas
        try:
            page.wait_for_selector("[data-posting-type], [data-to-posting]", timeout=10000)
        except:
            pass  # Continuar aunque no aparezcan, puede que ya estén en el HTML
        
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
