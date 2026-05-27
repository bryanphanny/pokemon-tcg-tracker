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


def search_purchasable(keyword: str) -> set[str]:
    """
    Search only items currently available to buy.
    Returns a set of TCINs. Used by the stock check loop to detect
    when a known TCIN flips from unavailable to purchasable.
    """
    try:
        with _make_client() as client:
            resp = client.get(SEARCH_URL, params=_base_params(keyword, purchasable_only=True))
            resp.raise_for_status()
            products = _parse_products(resp.json())
            return {p["tcin"] for p in products}
    except Exception as e:
        print(f"[target] search_purchasable error for '{keyword}': {e}")
        return set()
