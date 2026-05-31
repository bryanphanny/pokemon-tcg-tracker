import yaml
import time
import random
import logging
from apscheduler.schedulers.blocking import BlockingScheduler

import db
import target_client as target
import notifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def load_config() -> dict:
    with open("config.yaml") as f:
        return yaml.safe_load(f)


# ─── Loop 1: Discovery ────────────────────────────────────────────────────────
# Runs every 5 minutes.
# Searches Target with purchasability OFF so we find everything including
# out-of-stock items. Any TCIN we haven't seen before gets added to the DB
# and gets a "new product spotted" Discord ping.

def discovery_loop(config: dict):
    webhook = config["discord"]["webhook_url"]
    keywords = config["target"]["search_keywords"]

    log.info("[discovery] scanning for new products...")

    for keyword in keywords:
        products = target.search_all(keyword)
        log.info(f"[discovery] '{keyword}' returned {len(products)} products")

        for product in products:
            if not db.is_known(product["tcin"]):
                log.info(f"[discovery] NEW: {product['name']} (TCIN {product['tcin']})")
                db.upsert_product(
                    tcin=product["tcin"],
                    name=product["name"],
                    url=product["url"],
                    price=product["price"],
                    status="UNKNOWN",
                )
                notifier.send_new_product_alert(webhook, {**product, "status": "UNKNOWN"})
            else:
                db.upsert_product(
                    tcin=product["tcin"],
                    name=product["name"],
                    url=product["url"],
                    price=product["price"],
                    status=db.get_last_status(product["tcin"]) or "UNKNOWN",
                )

        time.sleep(random.uniform(1, config["jitter"]["between_requests"]))

    log.info("[discovery] scan complete")


# ─── Loop 2: Stock Check ──────────────────────────────────────────────────────
# Runs every 45 seconds.
#
# How availability works on Target's API:
# The search endpoint has a `default_purchasability_filter` flag.
# filter=false → all products (including OOS)
# filter=true  → only products currently available to buy
#
# The stock check runs the same keywords with filter=true and gets back
# a set of TCINs that are currently purchasable. It then compares each
# known TCIN against that set and alerts when one moves into it.

def stock_check_loop(config: dict):
    webhook = config["discord"]["webhook_url"]
    keywords = config["target"]["search_keywords"]

    # Collect all currently purchasable products across all keywords.
    # search_purchasable returns full product dicts, not just TCINs, because
    # Target's filter=true results overlap only partially with filter=false results —
    # items that only surface under filter=true would never be discovered otherwise.
    purchasable_products: dict[str, dict] = {}
    for keyword in keywords:
        for product in target.search_purchasable(keyword):
            purchasable_products[product["tcin"]] = product
        time.sleep(random.uniform(1, config["jitter"]["between_requests"]))

    purchasable_tcins = set(purchasable_products.keys())
    log.info(f"[stock] {len(purchasable_tcins)} purchasable TCINs found across all keywords")

    # Seed any purchasable TCIN that discovery never found (filter mismatch).
    # These are in-stock right now so alert immediately as "in stock".
    known_tcins = set(db.get_all_tcins())
    for tcin, product in purchasable_products.items():
        if tcin not in known_tcins:
            log.info(f"[stock] 🟢 NEW + IN STOCK (only visible via filter=true): {product['name']} (TCIN {tcin})")
            db.upsert_product(
                tcin=tcin,
                name=product["name"],
                url=product["url"],
                price=product["price"],
                status="IN_STOCK",
            )
            notifier.send_stock_alert(webhook, product | {"tcin": tcin})
            known_tcins.add(tcin)

    # Check every known TCIN against the purchasable set
    for tcin in known_tcins:
        previous_status = db.get_last_status(tcin)
        current_status = "IN_STOCK" if tcin in purchasable_tcins else "NOT_PURCHASABLE"

        if current_status != previous_status:
            db.upsert_product(
                tcin=tcin,
                name=db.get_name(tcin) or tcin,
                url=f"https://www.target.com/p/-/A-{tcin}",
                price=db.get_price(tcin) or "N/A",
                status=current_status,
            )

            if current_status == "IN_STOCK":
                log.info(f"[stock] 🟢 IN STOCK: {db.get_name(tcin)} (TCIN {tcin})")
                notifier.send_stock_alert(webhook, {
                    "tcin": tcin,
                    "name": db.get_name(tcin) or tcin,
                    "price": db.get_price(tcin) or "N/A",
                    "url": f"https://www.target.com/p/-/A-{tcin}",
                })
            else:
                log.info(f"[stock] 🔴 went out of stock: {db.get_name(tcin)} (TCIN {tcin})")
        else:
            log.info(f"[stock] {tcin}: {current_status}")


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    config = load_config()

    db.initialize()

    for tcin in config.get("manual_tcins", []):
        if tcin and not db.is_known(tcin):
            log.info(f"[init] seeding manual TCIN: {tcin}")
            db.upsert_product(tcin=tcin, name="(manual entry)", url=f"https://www.target.com/p/-/A-{tcin}", price="N/A", status="UNKNOWN")

    proxy_cfg = config.get("proxy", {})
    proxy_url = proxy_cfg.get("url") if proxy_cfg.get("enabled") else None
    if proxy_url:
        log.info(f"[init] proxy enabled: {proxy_url.split('@')[-1]}")
    target.configure(proxy_url=proxy_url)

    discovery_interval = config["target"]["discovery_interval_seconds"]
    stock_interval = config["target"]["stock_check_interval_seconds"]
    jitter_spread = config["jitter"]["spread_seconds"]

    scheduler = BlockingScheduler()
    scheduler.add_job(
        discovery_loop, "interval", seconds=discovery_interval,
        jitter=jitter_spread, args=[config],
        next_run_time=__import__("datetime").datetime.now()
    )
    scheduler.add_job(
        stock_check_loop, "interval", seconds=stock_interval,
        jitter=jitter_spread, args=[config]
    )

    log.info(f"[init] discovery every {discovery_interval}s ±{jitter_spread}s, stock check every {stock_interval}s ±{jitter_spread}s")
    log.info("Ctrl+C to stop.")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        log.info("Bot stopped.")


if __name__ == "__main__":
    main()
