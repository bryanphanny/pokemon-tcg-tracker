import httpx
from datetime import datetime


def send_stock_alert(webhook_url: str, product: dict):
    """Fire a Discord embed when a product flips to in-stock."""
    embed = {
        "title": "🟢 IN STOCK — Target",
        "description": product["name"],
        "color": 0x00C851,  # green
        "fields": [
            {"name": "Price", "value": product["price"], "inline": True},
            {"name": "TCIN", "value": product["tcin"], "inline": True},
        ],
        "url": product["url"],
        "footer": {"text": f"Detected at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"},
    }
    _post(webhook_url, content="@everyone", embeds=[embed])


def send_new_product_alert(webhook_url: str, product: dict):
    """Fire a Discord embed when a brand new TCIN is discovered."""
    embed = {
        "title": "🔍 New Product Spotted — Target",
        "description": product["name"],
        "color": 0x2196F3,  # blue
        "fields": [
            {"name": "Price", "value": product["price"], "inline": True},
            {"name": "Status", "value": product["status"], "inline": True},
            {"name": "TCIN", "value": product["tcin"], "inline": True},
        ],
        "url": product["url"],
        "footer": {"text": f"Added to watchlist at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"},
    }
    _post(webhook_url, embeds=[embed])


def _post(webhook_url: str, embeds: list, content: str | None = None):
    if not webhook_url or webhook_url == "PASTE_YOUR_DISCORD_WEBHOOK_URL_HERE":
        print("[discord] no webhook configured — skipping notification")
        return

    payload: dict = {"embeds": embeds}
    if content:
        payload["content"] = content

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(webhook_url, json=payload)
            resp.raise_for_status()
    except Exception as e:
        print(f"[discord] failed to send notification: {e}")
