#!/usr/bin/env python3
"""
Scraper de ZonaProp (zonaprop.com.ar).
Usa cloudscraper para evitar bloqueos anti-bot.
Uso: python zonaprop_scraper.py [url_busqueda]
Ejemplo: python zonaprop_scraper.py https://www.zonaprop.com.ar/departamentos-alquiler.html
"""

import re
import sys
import time
from urllib.parse import urljoin

import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup

URL_DEFAULT = "https://www.zonaprop.com.ar/departamentos-alquiler.html"
BASE = "https://www.zonaprop.com.ar"


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else URL_DEFAULT
    # Normalizar: quitar parámetros y asegurar .html
    base_url = url.split("?")[0].rstrip("/")
    if not base_url.endswith(".html"):
        base_url = base_url + ".html"

    print(f"Scrapeando: {base_url}")
    print("(ZonaProp puede bloquear requests; cloudscraper ayuda a evitarlo.)\n")

    scraper = cloudscraper.create_scraper()
    session = scraper

    def get_html(page_url: str) -> str:
        r = session.get(page_url)
        r.raise_for_status()
        return r.text

    # Primera página para ver estructura y total
    html = get_html(base_url)
    soup = BeautifulSoup(html, "lxml")

    # Tarjetas de avisos: atributo data-posting-type (o clases típicas por si cambian)
    cards = soup.find_all("div", attrs={"data-posting-type": True})
    if not cards:
        # Fallback: buscar por data-to-posting (link al aviso)
        cards = soup.select("[data-to-posting]")
    if not cards:
        # Guardar HTML para debug
        with open("zonaprop_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("No se encontraron tarjetas de propiedades. Guardado zonaprop_debug.html para revisar.")
        return

    print(f"En esta página: {len(cards)} avisos.\n")

    estates = []
    for node in cards:
        row = parse_card(node)
        if row:
            estates.append(row)

    if not estates:
        print("No se pudieron extraer datos de las tarjetas. Revisar selectores.")
        return

    # Opcional: más páginas (descomentar y usar con cuidado para no abusar)
    # for num in range(2, 6):
    #     time.sleep(2)
    #     page_url = base_url.replace(".html", f"-pagina-{num}.html")
    #     html = get_html(page_url)
    #     soup = BeautifulSoup(html, "lxml")
    #     for node in soup.find_all("div", attrs={"data-posting-type": True}):
    #         row = parse_card(node)
    #         if row:
    #             estates.append(row)

    df = pd.DataFrame(estates)
    out = "zonaprop_resultado.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"Guardados {len(estates)} avisos en {out}")


def parse_card(node) -> dict | None:
    """Extrae datos de un nodo tarjeta (BeautifulSoup)."""
    row = {}

    # URL del aviso
    href = node.get("data-to-posting")
    if href:
        row["url"] = urljoin(BASE, href) if not href.startswith("http") else href
    else:
        a = node.select_one("a[href*='/inmuebles-']")
        if a and a.get("href"):
            row["url"] = urljoin(BASE, a["href"])

    # Elementos con data-qa (precio, ubicación, descripción, etc.)
    for div in node.find_all("div", attrs={"data-qa": True}):
        qa = div.get("data-qa")
        text = (div.get_text() or "").strip().replace("\n", " ").replace("\t", " ")
        if not qa:
            continue
        if "PRICE" in qa or qa == "expensas":
            value, currency = parse_currency(text)
            row[f"{qa}_value"] = value
            row[f"{qa}_currency"] = currency
        else:
            row[qa] = text[:500] if text else ""

    # Precio como texto por si no viene en data-qa
    price_el = node.select_one("[data-qa='POSTING_CARD_PRICE'], .price, [class*='Price']")
    if price_el:
        raw = price_el.get_text().strip()[:200]
        row["price_raw"] = raw
        # Intentar separar alquiler y expensas (ej: "$ 750.000$ 150.000 Expensas")
        parts = re.split(r"\s*Expensas?\s*", raw, flags=re.I)
        if len(parts) >= 1 and parts[0]:
            row["alquiler_texto"] = parts[0].strip()
        if len(parts) >= 2 and parts[1]:
            row["expensas_texto"] = parts[1].strip()

    return row if row else None


def parse_currency(text: str) -> tuple:
    """Extrae número y moneda de un string de precio."""
    try:
        numbers = re.findall(r"[\d.\s]+", text)
        num_str = (numbers[0] if numbers else "").replace(".", "").replace(" ", "").strip()
        value = int(num_str) if num_str.isdigit() else None
        currency = None
        if "USD" in text.upper() or "U$S" in text:
            currency = "USD"
        elif "ARS" in text.upper() or "$" in text:
            currency = "ARS"
        return value, currency
    except Exception:
        return None, None


if __name__ == "__main__":
    main()
