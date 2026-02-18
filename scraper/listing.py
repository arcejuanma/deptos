"""
Scrape del listado ZonaProp con paginación.
Obtiene URLs y datos de tarjeta (precio, etc.) por aviso.
"""

import time
from urllib.parse import urljoin

import cloudscraper
from bs4 import BeautifulSoup

from zonaprop_scraper import parse_card

BASE = "https://www.zonaprop.com.ar"


def canonical_listing_url(url: str) -> str:
    """
    Misma publicación puede aparecer con distinta query (?n_src=..., n_pills=..., n_pg=...).
    Devolvemos la URL sin query para deduplicar por aviso real.
    """
    if not url:
        return url
    return url.split("?")[0].rstrip("/")


def page_url(base: str, page: int, use_order: bool = True) -> str:
    """URL de la página N. ZonaProp: orden publicado descendente (si funciona), luego -pagina-N antes de .html."""
    base = base.split("?")[0].rstrip("/")
    if not base.endswith(".html"):
        base = base + ".html"
    if use_order:
        base_with_order = base.replace(".html", "-orden-publicado-descendente.html")
    else:
        base_with_order = base
    if page == 1:
        return base_with_order
    return base_with_order.replace(".html", f"-pagina-{page}.html")


def fetch_listing_page(session: cloudscraper.CloudScraper, url: str) -> list[dict]:
    """Obtiene HTML de una página de listado y devuelve lista de dicts por card (con url, precio, etc.)."""
    r = session.get(url)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    cards = soup.find_all("div", attrs={"data-posting-type": True})
    if not cards:
        cards = soup.select("[data-to-posting]")
    if not cards:
        # Debug: guardar HTML si no encuentra tarjetas
        print(f"  ⚠️  No se encontraron tarjetas en {url}")
        print(f"     Status code: {r.status_code}, Tamaño HTML: {len(r.text)} bytes")
    out = []
    for node in cards:
        row = parse_card(node)
        if row and row.get("url"):
            out.append(row)
    return out


def scrape_all_listings(
    session: cloudscraper.CloudScraper,
    search_urls: list[str],
    max_pages_per_url: int,
    sleep_between_pages: float = 2,
    max_listings: int | None = None,
    skip_urls: set[str] | None = None,
) -> list[dict]:
    """
    Scrapea todas las URLs de búsqueda con paginación.
    Devuelve lista de avisos (dict con url y datos de tarjeta); deduplica por url.
    Si max_listings está definido, deja de pedir páginas al llegar a ese número de avisos únicos.
    Si skip_urls está definido, no se agregan avisos cuya URL está en ese conjunto; se siguen
    pidiendo páginas hasta reunir max_listings avisos "nuevos" o agotar páginas.
    """
    seen = set()
    results = []
    use_order = True  # Intentar con orden primero
    
    for base_url in search_urls:
        if max_listings is not None and len(results) >= max_listings:
            break
        base_url = base_url.split("?")[0].rstrip("/")
        if not base_url.endswith(".html"):
            base_url = base_url + ".html"
        
        # Probar primera página con orden, si falla probar sin orden
        first_page_failed = False
        for page in range(1, max_pages_per_url + 1):
            if max_listings is not None and len(results) >= max_listings:
                break
            url = page_url(base_url, page, use_order=use_order)
            try:
                print(f"  Scrapeando: {url}")
                rows = fetch_listing_page(session, url)
                print(f"    Encontrados {len(rows)} avisos en esta página")
                # Si la primera página falló con orden pero funciona sin orden, seguir sin orden
                if page == 1 and first_page_failed and len(rows) > 0:
                    print(f"  ✓ Orden sin '-orden-publicado-descendente' funciona, continuando sin orden")
                    use_order = False
            except Exception as e:
                error_msg = str(e)
                print(f"  ⚠️  Error scrapeando {url}: {error_msg}")
                # Si es 403 o 404 en la primera página con orden, probar sin orden
                if page == 1 and use_order and ("403" in error_msg or "404" in error_msg or "Forbidden" in error_msg):
                    print(f"  ⚠️  El orden '-orden-publicado-descendente' no funciona, probando sin orden...")
                    use_order = False
                    first_page_failed = True
                    url = page_url(base_url, page, use_order=False)
                    try:
                        print(f"  Scrapeando (sin orden): {url}")
                        rows = fetch_listing_page(session, url)
                        print(f"    Encontrados {len(rows)} avisos en esta página")
                    except Exception as e2:
                        print(f"  ⚠️  Error también sin orden: {e2}")
                        break
                else:
                    break
            if not rows:
                print(f"  Sin avisos en página {page}, terminando paginación para {base_url}")
                break
            for row in rows:
                if max_listings is not None and len(results) >= max_listings:
                    break
                u = row.get("url")
                if not u:
                    continue
                canonical = canonical_listing_url(u)
                if skip_urls is not None and canonical in skip_urls:
                    continue
                if canonical in seen:
                    continue
                seen.add(canonical)
                row["url"] = canonical  # una sola URL por aviso (sin query de tracking)
                row["_source_url"] = base_url  # para inferir zona si la ficha no trae barrio
                results.append(row)
            time.sleep(sleep_between_pages)
    return results
