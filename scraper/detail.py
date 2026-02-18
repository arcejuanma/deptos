"""
Scrape de la ficha de detalle de un aviso ZonaProp.
Extrae barrio, ambientes, m² cubiertos/totales, toilete, título, precio.
"""

import re

from bs4 import BeautifulSoup

BASE = "https://www.zonaprop.com.ar"


def _norm(s: str | None) -> str:
    if s is None:
        return ""
    return (s or "").strip().lower()


def parse_detail_html(html: str, url: str = "") -> dict:
    """
    Parsea el HTML de una ficha de detalle.
    Devuelve dict con: url, titulo, barrio, ambientes, m2_cubiertos, m2_totales, tiene_toilete, precio_value, precio_currency, price_raw.
    """
    soup = BeautifulSoup(html, "lxml")
    out = {"url": url, "titulo": "", "barrio": "", "ambientes": None, "m2_cubiertos": None, "m2_totales": None, "tiene_toilete": False, "precio_value": None, "precio_currency": None, "price_raw": ""}

    # Título: h1 o data-qa / title
    h1 = soup.find("h1")
    if h1:
        out["titulo"] = _norm(h1.get_text())[:500]
    for el in soup.select("[data-qa*='title'], [data-qa*='TITLE']"):
        if el.get_text().strip():
            out["titulo"] = el.get_text().strip()[:500]
            break

    # Ubicación/barrio: breadcrumb, o texto que contenga barrio conocido
    for el in soup.select("[data-qa*='location'], [data-qa*='LOCATION'], .location, .breadcrumb a, a[href*='-alquiler-']"):
        t = el.get_text().strip()
        if t and len(t) < 100 and not t.startswith("http"):
            out["barrio"] = t
            break
    if not out["barrio"]:
        # Último link de breadcrumb suele ser barrio
        bread = soup.select(".breadcrumb a, [class*='breadcrumb'] a")
        if bread:
            out["barrio"] = bread[-1].get_text().strip() if bread else ""

    # Superficie: buscar "cubiertos" / "total" / "m²" en labels (ZonaProp usa m², m2, etc.)
    body_text = soup.get_text(" ", strip=True)
    body_lower = body_text.lower()
    for pattern, key in [
        (r"(\d+[\d.]*)\s*m[²2]\s*cubiertos?", "m2_cubiertos"),
        (r"superficie\s*cubierta[:\s]*(\d+[\d.]*)", "m2_cubiertos"),
        (r"cubierta[:\s]*(\d+[\d.]*)\s*m", "m2_cubiertos"),
        (r"(\d+[\d.]*)\s*m[²2]\s*totales?", "m2_totales"),
        (r"superficie\s*total[:\s]*(\d+[\d.]*)", "m2_totales"),
        (r"total[:\s]*(\d+[\d.]*)\s*m", "m2_totales"),
    ]:
        m = re.search(pattern, body_lower, re.I)
        if m and out.get(key) is None:
            try:
                n = int(float(m.group(1).replace(".", "").replace(",", ".")))
                if 1 <= n <= 2000:
                    out[key] = n
            except (ValueError, TypeError):
                pass
    # Fallback: todos los "X m²" de la página; si hay dos valores, mayor = total, menor = cubiertos
    all_m2 = re.findall(r"(\d+)\s*m[²2]", body_lower)
    if all_m2:
        nums = sorted(
            set(int(x.replace(".", "").replace(",", "")) for x in all_m2 if x.replace(".", "").replace(",", "").isdigit()),
            reverse=True,
        )
        nums = [n for n in nums if 1 <= n <= 2000]
        if out.get("m2_totales") is None and nums:
            out["m2_totales"] = nums[0]
        if out.get("m2_cubiertos") is None and len(nums) >= 2:
            out["m2_cubiertos"] = nums[1]
        elif out.get("m2_cubiertos") is None and len(nums) == 1:
            out["m2_cubiertos"] = nums[0]

    # Ambientes: "3 ambientes", "Ambientes: 3"
    m = re.search(r"ambientes?[:\s]*(\d+)", body_text, re.I)
    if m:
        out["ambientes"] = int(m.group(1))
    if out["ambientes"] is None:
        m = re.search(r"(\d+)\s*amb", body_text, re.I)
        if m:
            out["ambientes"] = int(m.group(1))

    # Toilete: mención explícita (varias formas en avisos)
    out["tiene_toilete"] = bool(
        re.search(
            r"toilete?|toilet\b|baño\s+de\s+recepci[oó]n|medio\s+baño|baño\s+de\s+visitas|toilettes?",
            body_text,
            re.I,
        )
    )

    # Precio en ficha
    for el in soup.select("[data-qa*='price'], [data-qa*='PRICE'], .price"):
        t = el.get_text().strip()
        if t and ("USD" in t.upper() or "$" in t or "ARS" in t.upper()):
            out["price_raw"] = t[:200]
            nums = re.findall(r"[\d.\s]+", t)
            if nums:
                raw_num = nums[0].replace(".", "").replace(" ", "").strip()
                if raw_num.isdigit():
                    out["precio_value"] = int(raw_num)
            if "USD" in t.upper() or "U$S" in t:
                out["precio_currency"] = "USD"
            elif "ARS" in t.upper() or "$" in t:
                out["precio_currency"] = out["precio_currency"] or "ARS"
            break

    return out


def fetch_and_parse_detail(session, detail_url: str) -> dict | None:
    """Obtiene la ficha y la parsea. Devuelve dict enriquecido o None si falla."""
    try:
        r = session.get(detail_url)
        r.raise_for_status()
        data = parse_detail_html(r.text, detail_url)
        return data
    except Exception as e:
        error_msg = str(e)
        # Si es 403, intentar con Playwright
        if "403" in error_msg or "Forbidden" in error_msg:
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
                    )
                    context = browser.new_context(
                        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        viewport={'width': 1440, 'height': 900},
                        locale='es-AR',
                    )
                    page = context.new_page()
                    page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
                    import time
                    time.sleep(3)  # Esperar contenido dinámico
                    html = page.content()
                    context.close()
                    browser.close()
                data = parse_detail_html(html, detail_url)
                return data
            except Exception as e_playwright:
                # Si Playwright también falla, retornar None
                return None
        return None
