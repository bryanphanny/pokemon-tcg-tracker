# Pokemon TCG In-Stock Bot

A 24/7 stock monitoring bot that watches Target's website for Pokemon Trading Card Game products and sends Discord alerts when items become available to purchase.

---

## What It Does

- **Discovers new products automatically** — periodically searches Target for Pokemon TCG keywords and adds any new product to a local database the moment Target lists it, even if it's out of stock
- **Monitors availability continuously** — checks every tracked product every ~45 seconds and alerts the moment something flips from unavailable to purchasable
- **Sends Discord notifications** — two types of alerts:
  - 🔵 Blue embed when a brand new product is spotted on Target (could be days before it goes live)
  - 🟢 Green embed when a tracked product goes in stock, with product name, price, and direct buy link
- **Runs unattended** — designed to run 24/7 on a cloud VM with automatic restart on crash or server reboot

---

## What It Does Not Do

- **No Walmart or Pokemon Center support yet** — Target only for now. The architecture is designed to add new retailers as separate modules
- **No automatic checkout** — this is a notification bot only. It alerts you; you buy manually
- **No in-store stock** — monitors online availability only, not physical store shelves
- **No paginated search** — each keyword returns up to 24 results per scan. Products outside those results won't be tracked unless manually added via `manual_tcins` in config
- **No full Discord bot** — uses a simple one-way webhook. No slash commands or interactive features
- **No web UI or dashboard** — monitoring is done through Discord and the local SQLite database

---

## How It Works

Target's website separates content into two layers:

- **Server-side rendered** — product names, descriptions, images. Baked into the HTML, available via their API
- **Client-side rendered** — real-time availability. Fetched by JavaScript after page load, not available via simple API calls

Because availability isn't accessible through Target's product detail API, the bot uses Target's **search endpoint** as its availability signal. The search API supports a `default_purchasability_filter` flag:

- `filter=false` — returns all products including out-of-stock (used for discovery)
- `filter=true` — returns only products currently available to buy (used for stock checking)

The stock check compares which TCINs (Target's internal product IDs) appear in the purchasable set vs. what was purchasable on the previous check. A TCIN moving into the purchasable set triggers an alert.

```
DISCOVERY (every ~5 min)
  Search Target with filter=false
       │
       └── New TCIN found? → Add to DB → Discord "new product spotted"

STOCK CHECK (every ~45 sec)
  Search Target with filter=true → set of purchasable TCINs
       │
       └── Known TCIN now purchasable? → Discord "in stock" alert
```

The database (`bot.db`) is the memory between runs — it stores every known TCIN, its name, price, last known status, and when it was first discovered.

---

## Tech Stack

| Component | Purpose | Why |
|---|---|---|
| Python 3.12+ | Language | Best ecosystem for HTTP automation and scripting |
| httpx | HTTP client | Makes API calls to Target's Redsky search API |
| APScheduler | Job scheduler | Runs discovery and stock check on different intervals without manual threading |
| SQLite | Database | Zero-setup embedded database, stores to a single file (`bot.db`) |
| PyYAML | Config parsing | Reads `config.yaml` to keep secrets and settings out of code |
| Discord webhooks | Notifications | Simplest possible alerting — a single URL, no bot account required |

---

## Project Structure

```
pokemon_instock_bot/
├── main.py              # Entry point — starts scheduler, runs both loops
├── target_client.py     # Target Redsky API client (search_all, search_purchasable)
├── db.py                # SQLite database layer (all reads and writes)
├── notifier.py          # Discord webhook (new product + in-stock alerts)
├── config.yaml          # Settings — webhook URL, keywords, intervals, proxy toggle
└── requirements.txt     # Python dependencies
```

Each file has a single responsibility. Adding a new retailer means adding a new `walmart_client.py` and wiring it into `main.py` — nothing else changes.

---

## Setup

**1. Install dependencies**

```bash
pip3 install -r requirements.txt
```

**2. Create a Discord webhook**

In any Discord server you own:
- Right-click a channel → Edit Channel → Integrations → Webhooks → New Webhook
- Copy the webhook URL

**3. Configure the bot**

Edit `config.yaml`:

```yaml
discord:
  webhook_url: "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"

target:
  search_keywords:
    - "pokemon booster pack"
    - "pokemon tcg"
  discovery_interval_seconds: 300
  stock_check_interval_seconds: 45

jitter:
  spread_seconds: 15
  between_requests: 2.0

proxy:
  enabled: false
  url: "http://user:pass@proxy.provider.com:10000"

manual_tcins: []   # optionally seed known TCINs here
```

**4. Run locally**

```bash
python3 main.py
```

You'll see timestamped log output showing every discovery scan and stock check.

---

## Deployment (Cloud VM)

For 24/7 operation, deploy to a Linux VPS (DigitalOcean, AWS EC2, Hetzner, etc.).

**1. Upload code to server**

```bash
git clone https://github.com/yourusername/pokemon_instock_bot.git
cd pokemon_instock_bot
pip3 install -r requirements.txt
nano config.yaml   # paste your webhook URL
```

**2. Create a systemd service** so the bot starts on boot and restarts on crash

```bash
nano /etc/systemd/system/pokemon-bot.service
```

```ini
[Unit]
Description=Pokemon TCG In-Stock Bot
After=network.target

[Service]
WorkingDirectory=/root/pokemon_instock_bot
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable pokemon-bot
systemctl start pokemon-bot
journalctl -u pokemon-bot -f   # watch live logs
```

**Optional: Enable proxy**

If Target starts rate limiting your server's IP, set `proxy.enabled: true` in `config.yaml` and add a residential proxy URL. No code changes needed.

---

## Limitations and Known Behavior

- **Target's API is internal and undocumented.** It can change without notice. The `key` parameter and endpoint structure may need updating if Target changes their frontend architecture
- **Store ID is hardcoded to a St. Louis area store (2923)** for `scheduled_delivery_store_id`. This affects search ranking but not online availability results
- **Rate limiting** — aggressive testing (many requests in a short window) will trigger a temporary IP block. Normal operation at 45-second intervals does not
- **Search result ceiling** — if more than 24 Pokemon products are in stock simultaneously, the excess won't appear in a single search page. Pagination support is a planned improvement

---

## Planned Improvements

- [ ] Paginate search results to capture more than 24 products per keyword
- [ ] Add Walmart support (`walmart_client.py`)
- [ ] Add Pokemon Center support (`pokemoncenter_client.py`)
- [ ] Add full Discord bot with slash commands (`/watchlist`, `/addtcin`, `/status`)
- [ ] Add product image thumbnails to Discord embeds
- [ ] Web dashboard to view tracked products and alert history
