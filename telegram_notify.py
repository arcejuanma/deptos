"""
Envío de mensaje por Telegram con el link a la publicación.
Requiere TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID.
"""

import os

import requests


def send_listing_message(record: dict) -> None:
    """
    Envía un mensaje por Telegram con título, precio y link al aviso.
    record debe tener 'url'; opcional: titulo, price_raw o precio.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")

    title = (record.get("titulo") or "Aviso ZonaProp")[:200]
    price = record.get("price_raw") or record.get("precio") or "Consultar"
    if isinstance(price, (int, float)):
        price = str(price)
    url = record.get("url", "")
    text = f"{title}\n\nPrecio: {price}\n\n{url}"
    # Opcional: HTML para link clickeable
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": False,
    }
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
