import httpx
import uuid
import html as html_lib

VISITOR_ID = str(uuid.uuid4()).replace("-", "")

# API key is publicly embedded in Target's own JavaScript bundle —
# visible in any browser's DevTools under Network → redsky requests.
API_KEY = "ff457966e64d5e877fdbad070f276d18ecec4a01"

# Store IDs: 2923 is a physical Target (St. Louis area, detected from IP).
# pricing_store_id 3991 = Target's online store.
# scheduled_delivery_store_id must be a physical store, not the online store.
STORE_ID = "2923"

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.target.com",
    "Referer": "https://www.target.com/",
}

SEARCH_URL = "https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2"

_proxy_url: str | None = None


def configure(proxy_url: str | None = None):
    """Call once at startup to wire in a proxy. Pass None to disable."""
    global _proxy_url
    _proxy_url = proxy_url


def _make_client() -> httpx.Client:
    kwargs: dict = {"headers": BASE_HEADERS, "timeout": 15}
    if _proxy_url:
        kwargs["proxy"] = _proxy_url
    return httpx.Client(**kwargs)


def _base_params(keyword: str, purchasable_only: bool) -> dict:
    return {
        "keyword": keyword,
        "channel": "WEB",
        "count": "24",
        "default_purchasability_filter": "true" if purchasable_only else "false",
        "offset": "0",
        "page": f"/s?searchTerm={keyword.replace(' ', '+')}",
        "platform": "desktop",
        "visitor_id": VISITOR_ID,
        "key": API_KEY,
        "pricing_store_id": STORE_ID,
        "store_ids": STORE_ID,
        "scheduled_delivery_store_id": STORE_ID,
    }


def _is_pokemon_tcg(name: str, item: dict) -> bool:
    """
    Return True only if this is a Pokemon trading card product sold by Target directly.

    Two checks:
    1. item.fulfillment.is_marketplace — explicit flag Target sets for third-party sellers.
       Filters out resellers listing at inflated prices (e.g. $879 Charizard UPC).
    2. item_type name must be a trading card category, and the product name must contain
       'pokemon'. Filters out action figures, board games, and plushes that appear in
       the same search results.
    """
    # Drop third-party marketplace sellers — Target sets this flag explicitly
    is_marketplace = item.get("item", {}).get("fulfillment", {}).get("is_marketplace", False)
    if is_marketplace:
        return False

    # Must be Pokemon
    if "pokemon" not in name.lower():
        return False

    # Must be a trading card product, not a toy/game/figure
    item_type = (
        item.get("item", {})
            .get("product_classification", {})
            .get("item_type", {})
            .get("name", "")
            .lower()
    )
    card_types = {"collectible trading cards", "trading cards", "card games"}
    if not any(t in item_type for t in card_types):
        return False

    return True


def _parse_products(data: dict) -> list[dict]:
    items = (
        data.get("data", {})
            .get("search", {})
            .get("products", [])
    )
    products = []
    for item in items:
        tcin = item.get("tcin", "")
        if not tcin:
            continue
        raw_title = (
            item.get("item", {})
                .get("product_description", {})
                .get("title", "Unknown Product")
        )
        name = html_lib.unescape(raw_title)

        if not _is_pokemon_tcg(name, item):
            continue

        slug = name.lower().replace(" ", "-")[:60]
        price = item.get("price", {}).get("formatted_current_price", "N/A")
        url = f"https://www.target.com/p/{slug}/-/A-{tcin}"
        products.append({"tcin": tcin, "name": name, "url": url, "price": price})
    return products


def search_all(keyword: str) -> list[dict]:
    """
    Search including out-of-stock items. Used by the discovery loop to
    find new TCINs regardless of availability.
    Returns list of dicts: tcin, name, url, price
    """
    try:
        with _make_client() as client:
            resp = client.get(SEARCH_URL, params=_base_params(keyword, purchasable_only=False))
            resp.raise_for_status()
            return _parse_products(resp.json())
    except Exception as e:
        print(f"[target] search_all error for '{keyword}': {e}")
        return []


def search_purchasable(keyword: str) -> list[dict]:
    """
    Search only items currently available to buy.
    Returns list of dicts (tcin, name, url, price) — same shape as search_all.
    The stock check loop uses this to both detect availability AND seed new TCINs
    that only appear under filter=true (Target surfaces different results per filter).
    """
    try:
        with _make_client() as client:
            resp = client.get(SEARCH_URL, params=_base_params(keyword, purchasable_only=True))
            resp.raise_for_status()
            return _parse_products(resp.json())
    except Exception as e:
        print(f"[target] search_purchasable error for '{keyword}': {e}")
        return []
