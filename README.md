# Bot de búsqueda de alquileres (ZonaProp + Telegram + Supabase)

Scraper que busca departamentos y PHs en Vicente López y Palermo (corredor norte), aplica filtros duros (zona, ambientes, terraza, toilete, precio) y envía por Telegram los avisos que pasan. **Supabase** guarda las URLs ya notificadas para no enviar dos veces la misma publicación.

## Requisitos

- Python 3.10+
- Cuenta en [Supabase](https://supabase.com)
- Bot de Telegram (token + Chat ID)

## Instalación

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Configuración

### 1. Telegram

1. **Crear el bot**: En Telegram, abrí [@BotFather](https://t.me/BotFather), enviá `/newbot`, seguí los pasos y guardá el **token** que te da.
2. **Obtener Chat ID**: Enviá un mensaje a tu bot (o agregalo a un grupo y escribí algo). Luego en el navegador abrí:
   ```
   https://api.telegram.org/bot8237983360:AAH_lQ_Ycprh2Rx9wqxz0u9kq-oam2-4-Uo/getUpdates
   ```
   En la respuesta JSON buscá `"chat":{"id": ...}`. Ese número es tu **Chat ID**.

### 2. Supabase

1. Creá un proyecto en [supabase.com](https://supabase.com).
2. En el SQL Editor ejecutá:

```sql
create table if not exists publicaciones (
  url text primary key,
  notified_at timestamptz not null default now(),
  titulo text,
  price_raw text,
  barrio text,
  ambientes int,
  m2_cubiertos int,
  m2_totales int
);

-- Caché de fichas para no volver a scrapear el detalle de avisos ya vistos (válida 24 h)
create table if not exists fichas_cache (
  url text primary key,
  scraped_at timestamptz not null default now(),
  titulo text,
  barrio text,
  ambientes int,
  m2_cubiertos int,
  m2_totales int,
  tiene_toilete boolean default false,
  price_raw text,
  precio_value int,
  precio_currency text
);
```

3. En **Settings → API** copiá la **Project URL** y una **service_role** key (o **anon** si habilitás RLS con política de insert/select para esa tabla). La key con más permisos suele ser **service_role** para uso server-side.

### 3. Variables de entorno

Definí estas variables antes de ejecutar el bot (o en un `.env` y cargalas con `dotenv` si lo agregás):

- `SUPABASE_URL` – URL del proyecto (ej. `https://xxxx.supabase.co`)
- `SUPABASE_SERVICE_KEY` – Key service_role (o anon si configuraste RLS)
- `TELEGRAM_BOT_TOKEN` – Token del bot de Telegram
- `TELEGRAM_CHAT_ID` – Tu Chat ID (número)

Ejemplo en la terminal (Linux/macOS):

```bash


```

 Done! Congratulations on your new bot. You will find it at t.me/prop_finder12bot. You can now add a description, about section and profile picture for your bot, see /help for a list of commands. By the way, when you've finished creating your cool bot, ping our Bot Support if you want a better username for it. Just make sure the bot is fully operational before you do this.

Use this token to access the HTTP API:

Keep your token secure and store it safely, it can be used by anyone to control your bot.

For a description of the Bot API, see this page: https://core.telegram.org/bots/api

## Uso

### Corrida local (mismo código que en la nube)

Sirve para probar el flujo y para la **carga inicial de avisos sin gastar minutos de cloud**:

```bash
.venv/bin/python run_bot.py
```

**Prueba con una sola página** (una URL, página 1; útil para validar sin tardar mucho):

```bash
.venv/bin/python run_bot.py --one-page
```

**Probar con un lote de 100 avisos** (deja de pedir páginas al llegar a 100):

```bash
.venv/bin/python run_bot.py --max-listings 100
```

El script:

1. Scrapea los listados configurados en `config.py` (con paginación).
2. Por cada aviso con precio OK, consulta la **caché de fichas** en Supabase (`fichas_cache`): si esa URL ya se scrapeó en las últimas 24 h, usa esos datos y **no vuelve a entrar al detalle**. Si no está en caché, pide la ficha, aplica filtros y guarda el resultado en caché para la próxima corrida.
3. Para cada candidato que pasa todos los filtros, consulta `publicaciones`: si la URL ya fue notificada, no hace nada; si no, envía el mensaje por Telegram y guarda en Supabase.

### Corrida en la nube

El mismo `run_bot.py` se puede ejecutar en un cron (VPS, Oracle Cloud Free Tier), en **GitHub Actions** (schedule diario), **Google Cloud Run + Cloud Scheduler**, etc. Configurá las mismas variables como secrets o env del job.

## Configuración del bot (`config.py`)

- **SEARCH_URLS**: URLs de búsqueda (departamentos/PH, Vicente López y Palermo).
- **MAX_PAGES_PER_URL**: Cantidad de páginas por URL (paginación `-pagina-N.html`).
- **MAX_USD** / **MAX_ARS**: Precio máximo (ej. 1000 USD y 1.450.000 ARS).
- **BARRIOS_VICENTE_LOPEZ** / **BARRIOS_PALERMO_CORREDOR_NORTE**: Barrios permitidos.
- **DELTA_MIN_TERRAZA**: Diferencia mínima (m²) entre superficie total y cubierta para considerar “buena terraza”.

## Scripts auxiliares

- **zonaprop_scraper.py** – Scraper standalone de una URL (una página); guarda CSV.
- **run_local.py** – Solo listado con paginación + filtro de precio; no usa ficha, ni Supabase ni Telegram (útil para pruebas rápidas de listado y precio).

## Consideraciones

- Revisá los términos de uso de ZonaProp antes de hacer scraping intensivo.
- Respetá las pausas entre requests (`SLEEP_BETWEEN_PAGES`, `SLEEP_BETWEEN_DETAILS` en `config.py`).
