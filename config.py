"""
Configuración del bot de alquileres ZonaProp.
"""

# Precio máximo: 1000 USD o equivalente 1.450.000 ARS
MAX_USD = 1000
MAX_ARS = 1_450_000

# Paginación: formato de ZonaProp es -pagina-N antes de .html
# Página 1: .../departamentos-alquiler-vicente-lopez.html
# Página 2: .../departamentos-alquiler-vicente-lopez-pagina-2.html
MAX_PAGES_PER_URL = 5  # para prueba local; subir después

# URLs de búsqueda (departamentos y PH, Vicente López y Palermo)
SEARCH_URLS = [
    "https://www.zonaprop.com.ar/departamentos-alquiler-vicente-lopez.html",
    "https://www.zonaprop.com.ar/ph-alquiler-vicente-lopez.html",
    "https://www.zonaprop.com.ar/departamentos-alquiler-palermo.html",
    "https://www.zonaprop.com.ar/ph-alquiler-palermo.html",
]

# Barrios permitidos (filtro post-scrape con ficha)
BARRIOS_VICENTE_LOPEZ = [
    "florida", "olivos", "la lucila", "vicente lópez", "munro",
    "villa adelina", "carapachay", "villa martelli", "florida oeste",
    "lomas de florida",
]
BARRIOS_PALERMO_CORREDOR_NORTE = [
    "palermo chico", "palermo hollywood", "palermo soho", "palermo",
    "las cañitas", "palermo viejo", "palermo nuevo", "botánico",
]

# Terraza: diferencia mínima entre m² totales y cubiertos (m²)
DELTA_MIN_TERRAZA = 5

# Pausa entre requests (segundos)
SLEEP_BETWEEN_PAGES = 2
SLEEP_BETWEEN_DETAILS = 1

# Horas atrás para considerar una ficha en caché como "ya vista" (evitar re-scrapear los mismos 100)
SKIP_RECENT_FICHAS_HOURS = 24
