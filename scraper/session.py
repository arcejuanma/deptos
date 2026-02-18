"""
Configuración compartida de cloudscraper para evitar detección como bot.
"""

import time
import cloudscraper


def create_scraper_session():
    """
    Crea una sesión de cloudscraper configurada para parecer un navegador real.
    Usa Chrome en Windows para evitar detección.
    Establece cookies iniciales visitando la página principal primero.
    """
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        },
        delay=15,  # Delay inicial más largo para resolver desafíos anti-bot
    )
    
    # Headers adicionales para parecer navegador real
    scraper.headers.update({
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'es-AR,es;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    })
    
    # Establecer cookies iniciales visitando la página principal
    try:
        print("  Estableciendo sesión con ZonaProp...")
        scraper.get('https://www.zonaprop.com.ar/', timeout=30)
        time.sleep(3)  # Esperar un poco después de la primera request
        print("  ✓ Sesión establecida")
    except Exception as e:
        print(f"  ⚠️  Advertencia al establecer sesión inicial: {e}")
        # Continuar de todas formas
    
    return scraper
