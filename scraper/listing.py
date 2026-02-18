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
    # Agregar referer para parecer navegación real
    headers = {
        'Referer': 'https://www.zonaprop.com.ar/',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-User': '?1',
    }
    r = session.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    
    # Verificar encoding y contenido
    encoding = r.headers.get('Content-Encoding', '').lower()
    print(f"    Content-Type: {r.headers.get('Content-Type', 'N/A')}")
    print(f"    Content-Encoding: {encoding or 'N/A'}")
    
    # Descomprimir manualmente si es necesario (cloudscraper a veces no descomprime Brotli)
    html_text = r.text
    if encoding and ('br' in encoding or 'brotli' in encoding or 'gzip' in encoding):
        # Si el texto no parece HTML válido, intentar descomprimir manualmente
        if not html_text.strip().startswith('<') and len(html_text) > 100:
            print(f"    ⚠️  Contenido comprimido no descomprimido automáticamente, descomprimiendo manualmente...")
            try:
                if 'br' in encoding or 'brotli' in encoding:
                    import brotli
                    html_text = brotli.decompress(r.content).decode('utf-8')
                    print(f"    ✓ Descomprimido con Brotli: {len(html_text)} chars")
                elif 'gzip' in encoding:
                    import gzip
                    html_text = gzip.decompress(r.content).decode('utf-8')
                    print(f"    ✓ Descomprimido con gzip: {len(html_text)} chars")
            except ImportError as e:
                print(f"    ⚠️  Falta librería para descompresión: {e}. Instalar: pip install brotli")
            except Exception as e:
                print(f"    ⚠️  Error descomprimiendo: {e}")
                html_text = r.text  # Fallback al texto original
    
    soup = BeautifulSoup(html_text, "lxml")
    cards = soup.find_all("div", attrs={"data-posting-type": True})
    if not cards:
        cards = soup.select("[data-to-posting]")
    if not cards:
        # Debug: guardar HTML si no encuentra tarjetas
        print(f"  ⚠️  No se encontraron tarjetas en {url}")
        print(f"     Status code: {r.status_code}, Tamaño HTML: {len(r.text)} bytes")
        # Guardar HTML para debug
        debug_file = f"debug_{url.split('/')[-1].replace('.html', '')}.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(r.text)
        print(f"     HTML guardado en {debug_file} para inspección")
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
    
    for base_url in search_urls:
        if max_listings is not None and len(results) >= max_listings:
            break
        base_url = base_url.split("?")[0].rstrip("/")
        if not base_url.endswith(".html"):
            base_url = base_url + ".html"
        
        # Probar primera página con orden, si falla probar sin orden
        use_order = True
        for page in range(1, max_pages_per_url + 1):
            if max_listings is not None and len(results) >= max_listings:
                break
            rows = []
            url = page_url(base_url, page, use_order=use_order)
            try:
                print(f"  Scrapeando: {url}")
                rows = fetch_listing_page(session, url)
                print(f"    Encontrados {len(rows)} avisos en esta página")
            except Exception as e:
                error_msg = str(e)
                print(f"  ⚠️  Error scrapeando {url}: {error_msg}")
                # Si es 403 o 404 en la primera página con orden, probar sin orden
                if page == 1 and use_order and ("403" in error_msg or "404" in error_msg or "Forbidden" in error_msg):
                    print(f"  ⚠️  El orden '-orden-publicado-descendente' no funciona, probando sin orden...")
                    use_order = False
                    url = page_url(base_url, page, use_order=False)
                    try:
                        print(f"  Scrapeando (sin orden): {url}")
                        rows = fetch_listing_page(session, url)
                        print(f"    Encontrados {len(rows)} avisos en esta página")
                    except Exception as e2:
                        print(f"  ⚠️  Error también sin orden: {e2}")
                        # Si sigue siendo 403, intentar con Playwright
                        if "403" in str(e2) or "Forbidden" in str(e2):
                            print(f"  ⚠️  403 persistente, intentando con Playwright (navegador real)...")
                            try:
                                from playwright.sync_api import sync_playwright
                                from scraper.listing_playwright import fetch_listing_page_playwright
                                # Configurar browser para parecer laptop común (macOS Chrome)
                                with sync_playwright() as p:
                                    browser = p.chromium.launch(
                                        headless=True,
                                        args=[
                                            '--disable-blink-features=AutomationControlled',
                                            '--disable-dev-shm-usage',
                                            '--no-sandbox',
                                        ]
                                    )
                                    # Crear contexto con user agent de macOS Chrome
                                    context = browser.new_context(
                                        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                        viewport={'width': 1440, 'height': 900},
                                        locale='es-AR',
                                        timezone_id='America/Argentina/Buenos_Aires',
                                    )
                                    browser_page = context.new_page()
                                    rows = fetch_listing_page_playwright(browser_page, url)
                                    context.close()
                                    browser.close()
                                print(f"    Encontrados {len(rows)} avisos con Playwright")
                            except ImportError:
                                print(f"  ⚠️  Playwright no está instalado. Instalar con: playwright install chromium")
                                rows = []
                            except Exception as e3:
                                print(f"  ⚠️  Error con Playwright: {e3}")
                                rows = []
                        else:
                            rows = []
                else:
                    # Si es 403 en otra página, también intentar Playwright
                    if "403" in error_msg or "Forbidden" in error_msg:
                        print(f"  ⚠️  403 detectado, intentando con Playwright...")
                        try:
                            from playwright.sync_api import sync_playwright
                            from scraper.listing_playwright import fetch_listing_page_playwright
                            # Configurar browser para parecer laptop común (macOS Chrome)
                            with sync_playwright() as p:
                                browser = p.chromium.launch(
                                    headless=True,
                                    args=[
                                        '--disable-blink-features=AutomationControlled',
                                        '--disable-dev-shm-usage',
                                        '--no-sandbox',
                                    ]
                                )
                                context = browser.new_context(
                                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                    viewport={'width': 1440, 'height': 900},
                                    locale='es-AR',
                                    timezone_id='America/Argentina/Buenos_Aires',
                                )
                                browser_page = context.new_page()
                                rows = fetch_listing_page_playwright(browser_page, url)
                                context.close()
                                browser.close()
                            print(f"    Encontrados {len(rows)} avisos con Playwright")
                        except Exception as e_playwright:
                            print(f"  ⚠️  Error con Playwright: {e_playwright}")
                            rows = []
                    else:
                        rows = []
            # Si no encontró avisos y es página 1 con orden, probar sin orden
            if not rows and page == 1 and use_order:
                print(f"  ⚠️  No se encontraron avisos con orden, probando sin orden...")
                use_order = False
                url = page_url(base_url, page, use_order=False)
                try:
                    print(f"  Scrapeando (sin orden): {url}")
                    rows = fetch_listing_page(session, url)
                    print(f"    Encontrados {len(rows)} avisos en esta página")
                except Exception as e2:
                    print(f"  ⚠️  Error también sin orden: {e2}")
                    rows = []
            if not rows:
                print(f"  Sin avisos en página {page}, terminando paginación para {base_url}")
                break
            # Procesar avisos encontrados
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
