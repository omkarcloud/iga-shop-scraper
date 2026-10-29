"""IGA Shop transport: plain curl_cffi with browser-impersonated TLS against
the site's own same-origin JSON proxy (https://www.igashop.com.au/api/storefront/*,
which forwards to the Wynshop storefront gateway) and its sitemaps. No
browser, no cookies, no login. Egress: the pod's own IP (config.iga_shop_proxy(),
knob IGA_SHOP_EXIT) — every surface answered 200 direct, datacenter and AU
residential from the pod (probe 2026-10-28, config's "--- iga shop ---"
block). A retryable failure drops the thread's session, so the retry rides
a fresh exit.

Upstream surfaces (all verified 2026-10-28, all anonymous):

  * STORES     GET /stores?search=&take=&skip=         {total, items[store]}
               `search` matches name / suburb / postcode / store number;
               take=1000 returns all 540 stores in one call.
  * NEAR       GET /near/{lat}/{lng}/{km}/{max}/stores?shoppingModeId=
               {items[store]} nearest pickup stores (no distance field).
  * SEARCH     GET /stores/{store}/search?q=&take=&skip=&sort=&f=&misspelling=true
               {count, total, items[], facets, suggestions, pagination}.
               q <= 50 chars; take <= 100 (more answers 0 items); skip < 10000.
  * PRODUCT    GET /stores/{store}/products/{sku}        the full record.
               Unknown SKU (or one not ranged at that store): 404 with
               data "Product X not found"; unknown store: 404 with
               data.detail "Store X not found.".
  * SPECIALS   GET /stores/{store}/promotions/products?take=&skip=&sort=&f=
               same listing shape; needs the x-shopping-mode header.
  * TREE       GET /stores/{store}/categoryHierarchy     the category tree.
  * CATEGORY   GET /stores/{store}/categories/{id}/search?take=&skip=&sort=&f=
               products at any depth ("Grocery" = the whole catalogue).
               An unknown id is a 200 with 0 items, so api.py resolves the
               category against the tree first.
  * OVERVIEW   GET /stores/{store}/categories/{id}/subcategories/search?take=
               one block per child category with its first N products.
  * RECIPES    GET /stores/{store}/recipes?q=&take=&skip=&f=Category:X
  * RECIPE     GET /stores/{store}/recipes/{id}           404 when unknown.
  * SITEMAPS   GET /sitemap_index.xml, /sitemap.xml, /product-sitemap.xml
               (10,000 URLs, capped), /category-sitemap.xml, /recipe-sitemap.xml

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  IgaShopUpstreamError  transport failure / 5xx / non-JSON body  — retryable
  IgaShopBlocked        401 / 403 / 429 / challenge page         — retryable
  IgaShopBadRequest     upstream 400                             — never retried
  IgaShopNotFound       404 (product / recipe / store)           — never retried
"""
import os
import sys
import threading
import time

# Allow direct execution (python iga_shop/fetch.py): flat imports resolve
# like under the server. Idempotent when imported normally.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import egress
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError
from iga_shop.refs import SITE, SHOPPING_MODE_PICKUP

API = SITE + "/api/storefront"
IMPERSONATE = "chrome"
JSON_TIMEOUT = 30
SITEMAP_TIMEOUT = 60      # product-sitemap.xml is 1.4 MB
STORE_LIST_TAKE = 1000    # 540 stores on 2026-10-28; one call for the whole list

_local = threading.local()


class IgaShopUpstreamError(UpstreamError):
    """Transport failure, 5xx or a non-JSON body — retryable."""


class IgaShopBlocked(IgaShopUpstreamError, Blocked):
    """401 / 403 / 429 or a challenge page where JSON was expected — retryable."""


class IgaShopBadRequest(BadRequest):
    """Upstream 400 — never retried."""


class IgaShopNotFound(NotFound):
    """Product / recipe / store does not exist — never retried."""


# ---- sessions -----------------------------------------------------------------------

def _headers(proxy):
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": egress.accept_language(proxy),
        "x-shopping-mode": SHOPPING_MODE_PICKUP,
        "referer": SITE + "/",
    }


def _session():
    """One curl_cffi session per cheroot worker thread (a curl handle must
    never be shared across threads); keep-alive, chrome TLS, one sticky exit."""
    sess = getattr(_local, "session", None)
    if sess is None:
        from curl_cffi import requests as curl_requests
        proxy = config.iga_shop_proxy()
        sess = curl_requests.Session(impersonate=IMPERSONATE)
        if proxy:
            sess.proxies = {"http": proxy, "https": proxy}
        sess.headers.update(_headers(proxy))
        _local.session = sess
    return sess


def _drop_session():
    """Close the thread's session so a poisoned connection (or exit) dies."""
    sess = getattr(_local, "session", None)
    _local.session = None
    if sess is not None:
        try:
            sess.close()
        except Exception:
            pass


def _retrying(fn):
    """Run fn() under the shared retry policy (IgaShopUpstreamError only;
    NotFound / BadRequest surface immediately)."""
    last = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            return fn()
        except IgaShopUpstreamError as e:
            last = e
            _drop_session()
            if attempt < config.MAX_RETRIES:
                time.sleep(config.RETRY_BACKOFF * attempt)
    raise last


# ---- response classification ----------------------------------------------------------

def _error_detail(payload):
    """The storefront's error body: {"statusCode", "message", "data"} where
    data is a string ("Product 000000 not found") or a problem+json object
    ({"detail": "Store 99999 not found."})."""
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data")
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, dict):
        return str(data.get("detail") or data.get("title") or "").strip()
    return str(payload.get("message") or "").strip()


def _classify(resp, label):
    """HTTP status -> error taxonomy; returns the decoded JSON for a 200."""
    status = resp.status_code
    if status in (401, 403, 429):
        raise IgaShopBlocked(f"HTTP {status} for {label}")
    if status >= 500:
        raise IgaShopUpstreamError(f"HTTP {status} for {label}")
    try:
        payload = resp.json()
    except Exception:
        head = (resp.text or "")[:200].replace("\n", " ")
        if status == 404:
            raise IgaShopNotFound(f"{label} not found")
        raise IgaShopBlocked(f"non-JSON response ({status}) for {label}: {head}")
    if status == 404:
        detail = _error_detail(payload)
        raise IgaShopNotFound(detail.rstrip(".") if detail else f"{label} not found")
    if status == 400:
        raise IgaShopBadRequest(_error_detail(payload) or f"HTTP 400 for {label}")
    if status != 200:
        raise IgaShopUpstreamError(f"HTTP {status} for {label}")
    return payload


def _get_json(path, params=None, label=None):
    label = label or path
    params = {k: v for k, v in (params or {}).items() if v not in (None, "", [])}

    def once():
        try:
            resp = _session().get(API + path, params=params, timeout=JSON_TIMEOUT)
        except Exception as e:
            raise IgaShopUpstreamError(f"request failed: {type(e).__name__}: {e}")
        return _classify(resp, label)
    return _retrying(once)


def _facet_params(filters):
    """{"Brand": "Pauls", "Category": "Full Cream"} -> the repeated `f`
    query values the storefront takes (f=Brand:Pauls&f=Category:Full Cream)."""
    return [f"{name}:{value}" for name, value in (filters or {}).items() if value]


# ---- stores ------------------------------------------------------------------------

def fetch_stores(search=None, take=20, skip=0):
    """GET /stores -> {total, items[store]}; `search` matches name, suburb,
    postcode, state and store number."""
    return _get_json("/stores", {"search": search, "take": take, "skip": skip}, "store search")


def fetch_all_stores():
    """Every store in one call (the list is 540 rows, ~400 KB)."""
    return _get_json("/stores", {"take": STORE_LIST_TAKE, "skip": 0}, "store list")


def fetch_nearby_stores(latitude, longitude, within_km=100, max_results=10):
    """GET /near/... -> {items[store]} ordered nearest first (pickup mode;
    the planning mode lists the same stores)."""
    path = f"/near/{latitude}/{longitude}/{int(within_km)}/{int(max_results)}/stores"
    return _get_json(path, {"shoppingModeId": SHOPPING_MODE_PICKUP}, "nearby stores")


# ---- products ------------------------------------------------------------------------

def fetch_search(store, query, take=20, skip=0, sort=None, filters=None):
    """GET /stores/{store}/search -> the listing payload."""
    params = {"q": query[:50], "take": take, "skip": skip, "sort": sort,
              "misspelling": "true", "f": _facet_params(filters)}
    return _get_json(f"/stores/{store}/search", params, f"product search {query!r}")


def fetch_product(store, sku):
    """GET /stores/{store}/products/{sku} -> the full product record."""
    return _get_json(f"/stores/{store}/products/{sku}", None, f"product {sku}")


def fetch_specials(store, take=20, skip=0, sort=None, filters=None):
    """GET /stores/{store}/promotions/products -> the listing payload of
    everything on promotion at the store."""
    params = {"take": take, "skip": skip, "sort": sort, "f": _facet_params(filters)}
    return _get_json(f"/stores/{store}/promotions/products", params, "specials")


# ---- categories ------------------------------------------------------------------------

def fetch_category_tree(store):
    """GET /stores/{store}/categoryHierarchy -> the nested tree."""
    return _get_json(f"/stores/{store}/categoryHierarchy", None, "category tree")


def fetch_category_products(store, category_id, take=20, skip=0, sort=None, filters=None):
    """GET /stores/{store}/categories/{id}/search -> the listing payload."""
    params = {"take": take, "skip": skip, "sort": sort, "misspelling": "true",
              "f": _facet_params(filters)}
    return _get_json(f"/stores/{store}/categories/{category_id}/search", params,
                     f"category {category_id}")


def fetch_category_overview(store, category_id, take=18):
    """GET /stores/{store}/categories/{id}/subcategories/search -> one block
    per child category with its first `take` products."""
    return _get_json(f"/stores/{store}/categories/{category_id}/subcategories/search",
                     {"take": take}, f"category overview {category_id}")


# ---- recipes -----------------------------------------------------------------------------

def fetch_recipes(store, query=None, take=20, skip=0, category=None):
    """GET /stores/{store}/recipes -> {filters, count, total, items[card]}."""
    params = {"q": query, "take": take, "skip": skip,
              "f": _facet_params({"Category": category})}
    return _get_json(f"/stores/{store}/recipes", params, "recipe search")


def fetch_recipe(store, recipe_id):
    """GET /stores/{store}/recipes/{id} -> the full recipe."""
    return _get_json(f"/stores/{store}/recipes/{recipe_id}", None, f"recipe {recipe_id}")


# ---- sitemaps ----------------------------------------------------------------------------

SITEMAPS = ("sitemap_index.xml", "sitemap.xml", "product-sitemap.xml",
            "category-sitemap.xml", "recipe-sitemap.xml")


def fetch_sitemap(name):
    """GET /<name>.xml -> the XML text."""
    if name not in SITEMAPS:
        raise ValueError(f"unknown sitemap {name!r}")

    def once():
        try:
            resp = _session().get(f"{SITE}/{name}", timeout=SITEMAP_TIMEOUT,
                                  headers={"accept": "application/xml,text/xml,*/*;q=0.8"})
        except Exception as e:
            raise IgaShopUpstreamError(f"request failed: {type(e).__name__}: {e}")
        if resp.status_code in (401, 403, 429):
            raise IgaShopBlocked(f"HTTP {resp.status_code} for {name}")
        if resp.status_code == 404:
            raise IgaShopNotFound(f"{name} not found")
        if resp.status_code != 200:
            raise IgaShopUpstreamError(f"HTTP {resp.status_code} for {name}")
        text = resp.text or ""
        if "<urlset" not in text and "<sitemapindex" not in text:
            raise IgaShopBlocked(f"non-XML body for {name}: {text[:120]!r}")
        return text
    return _retrying(once)
