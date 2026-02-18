"""
Configuración compartida de cloudscraper para evitar detección como bot.
"""

import cloudscraper


def create_scraper_session():
    """
    Crea una sesión de cloudscraper configurada para parecer un navegador real.
    Usa Chrome en Windows para evitar detección.
    """
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        },
        delay=10,  # Delay inicial para resolver desafíos anti-bot
    )
    
    # Headers adicionales para parecer navegador real
    scraper.headers.update({
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://www.zonaprop.com.ar/',
    })
    
    return scraper
