"""The /iga-shop/* endpoint functions (route_glue's route_table calls them
with the schema's loaded kwargs). Every endpoint caches its own response
through cache.cached_call keyed on the validated params; two upstream
pages are cached ONCE and sliced by several endpoints (tofler-style):

  * the full store list (540 rows, one call, 24 h) serves stores/details
    and resolves the `store` param of every product / category / recipe
    endpoint (store number -> postcode -> page slug -> name / suburb)
    without an upstream call per request;
  * the category tree per store (24 h) serves categories/list and
    resolves the `category` param of categories/products and
    categories/overview — the storefront answers an unknown category
    with an empty 200, so the tree is what turns it into a 404;
  * the product sitemap (10,000 URLs, 24 h) and the merged non-product
    sitemaps are parsed once and paged in memory.
"""
import config
from cache import cached_call
from iga_shop import cache_config as ttl
from iga_shop import parsers, refs
from iga_shop.fetch import (IgaShopNotFound, fetch_all_stores, fetch_category_overview,
                            fetch_category_products, fetch_category_tree, fetch_nearby_stores,
                            fetch_product, fetch_recipe, fetch_recipes, fetch_search, fetch_sitemap,
                            fetch_specials, fetch_stores)


def _skip(page, limit):
    return (page - 1) * limit


# ---- the shared store list --------------------------------------------------------

def _store_list():
    return cached_call("iga_shop.store_list", {}, lambda: parsers.parse_stores(fetch_all_stores())["results"],
                       ttl.STORE_LIST_CACHE)


def _store_for(lookup):
    """The parsed store record for a resolved `store` value, or NotFound."""
    lookup = lookup or config.IGA_SHOP_DEFAULT_STORE
    store = parsers.match_store(_store_list(), lookup)
    if store is None:
        raise IgaShopNotFound(f"store {lookup!r} not found: give a store number, postcode, suburb, "
                              "name or igashop.com.au store link (see /iga-shop/stores/search)")
    return store


def _store_summary(store):
    address = store.get("address") or {}
    return {
        "number": store.get("number"),
        "name": store.get("name"),
        "suburb": address.get("suburb"),
        "state": address.get("state"),
        "postcode": address.get("postcode"),
        "link": store.get("link"),
    }


def _filters(brand=None, category=None):
    return {"Brand": brand, "Category": category}


# the storefront's sort token (what the schema loads) -> the public value it was given as
_SORT_NAMES = {token: name for name, token in refs.SORTS.items()}


def _sort_name(sort):
    return _SORT_NAMES.get(sort, sort)


# ---- stores/search ---------------------------------------------------------------

def _stores_search(query, page, limit):
    payload = fetch_stores(search=query, take=limit, skip=_skip(page, limit))
    out = parsers.parse_stores(payload, page, limit)
    return {"query": query, **out}


def stores_search(**data):
    return cached_call("iga_shop.stores_search", data, _stores_search, ttl.STORES_CACHE)


# ---- stores/nearby ---------------------------------------------------------------

def _stores_nearby(latitude, longitude, radius_km, limit):
    payload = fetch_nearby_stores(latitude, longitude, radius_km, limit)
    results = parsers.parse_nearby(payload, latitude, longitude)[:limit]
    return {
        "latitude": latitude,
        "longitude": longitude,
        "radius_km": radius_km,
        "count": len(results),
        "results": results,
    }


def stores_nearby(**data):
    return cached_call("iga_shop.stores_nearby", data, _stores_nearby, ttl.STORES_CACHE)


# ---- stores/details ----------------------------------------------------------------

def store_details(store):
    return _store_for(store)


# ---- products/search ----------------------------------------------------------------

def _products_search(query, store, page, limit, sort, brand, category):
    record = _store_for(store)
    payload = fetch_search(record["number"], query, take=limit, skip=_skip(page, limit),
                           sort=sort, filters=_filters(brand, category))
    out = parsers.parse_listing(payload, page, limit)
    return {
        "query": query,
        "link": refs.search_link(query, page),
        "store": _store_summary(record),
        "sort": _sort_name(sort),
        "brand": brand,
        "category": category,
        **out,
    }


def products_search(**data):
    return cached_call("iga_shop.products_search", data, _products_search, ttl.LISTING_CACHE)


# ---- products/details ---------------------------------------------------------------

def _product_details(product, store):
    record = _store_for(store)
    try:
        payload = fetch_product(record["number"], product)
    except IgaShopNotFound:
        raise IgaShopNotFound(f"product {product} not found at store {record['number']} "
                              f"({record.get('name')}); IGA stores range differently, try another store")
    out = parsers.parse_product(payload, product, record["number"])
    out["store"] = _store_summary(record)
    return out


def product_details(**data):
    return cached_call("iga_shop.product_details", data, _product_details, ttl.PRODUCT_CACHE)


# ---- products/specials ----------------------------------------------------------------

def _products_specials(store, page, limit, sort, brand, category):
    record = _store_for(store)
    payload = fetch_specials(record["number"], take=limit, skip=_skip(page, limit),
                             sort=sort, filters=_filters(brand, category))
    out = parsers.parse_listing(payload, page, limit)
    return {
        "link": refs.specials_link(page),
        "store": _store_summary(record),
        "sort": _sort_name(sort),
        "brand": brand,
        "category": category,
        **out,
    }


def products_specials(**data):
    return cached_call("iga_shop.products_specials", data, _products_specials, ttl.LISTING_CACHE)


# ---- the shared category tree ----------------------------------------------------------

def _category_tree(store_number):
    return cached_call("iga_shop.category_tree", {"store": store_number},
                       lambda store: parsers.parse_category_tree(fetch_category_tree(store)),
                       ttl.CATEGORY_TREE_CACHE)


def _category_for(key, store_number):
    """The flattened tree node for a resolved `category` key, or NotFound."""
    node = parsers.find_category(parsers.flatten_categories(_category_tree(store_number)), key)
    if node is None:
        raise IgaShopNotFound(f"category {key!r} not found at store {store_number}; "
                              "see /iga-shop/categories/list for the identifiers")
    return node


def _count_nodes(tree):
    return sum(1 + _count_nodes(n.get("children") or []) for n in tree)


def categories_list(store):
    record = _store_for(store)
    tree = _category_tree(record["number"])
    return {
        "store": _store_summary(record),
        "departments_count": len(tree),
        "categories_count": _count_nodes(tree),
        "results": tree,
    }


# ---- categories/products -----------------------------------------------------------------

def _category_products(category, store, page, limit, sort, brand):
    record = _store_for(store)
    node = _category_for(category, record["number"])
    payload = fetch_category_products(record["number"], node["id"], take=limit,
                                      skip=_skip(page, limit), sort=sort, filters=_filters(brand))
    out = parsers.parse_listing(payload, page, limit)
    return {
        "category": node,
        "store": _store_summary(record),
        "sort": _sort_name(sort),
        "brand": brand,
        **out,
    }


def category_products(**data):
    return cached_call("iga_shop.category_products", data, _category_products, ttl.LISTING_CACHE)


# ---- categories/overview --------------------------------------------------------------------

def _category_overview(category, store, limit):
    record = _store_for(store)
    node = _category_for(category, record["number"])
    payload = fetch_category_overview(record["number"], node["id"], take=limit)
    out = parsers.parse_category_overview(payload)
    out["category"] = node
    out["store"] = _store_summary(record)
    return out


def category_overview(**data):
    return cached_call("iga_shop.category_overview", data, _category_overview, ttl.CATEGORY_OVERVIEW_CACHE)


# ---- recipes/search ----------------------------------------------------------------------------

def _recipes_search(query, category, store, page, limit):
    record = _store_for(store)
    payload = fetch_recipes(record["number"], query=query, take=limit, skip=_skip(page, limit),
                            category=category)
    out = parsers.parse_recipes(payload, page, limit)
    return {"query": query, "category": category, "store": _store_summary(record), **out}


def recipes_search(**data):
    return cached_call("iga_shop.recipes_search", data, _recipes_search, ttl.RECIPES_CACHE)


# ---- recipes/details ----------------------------------------------------------------------------

def _recipe_details(recipe, store):
    record = _store_for(store)
    try:
        payload = fetch_recipe(record["number"], recipe)
    except IgaShopNotFound:
        raise IgaShopNotFound(f"recipe {recipe} not found (see /iga-shop/recipes/search)")
    out = parsers.parse_recipe(payload, recipe)
    out["store"] = _store_summary(record)
    return out


def recipe_details(**data):
    return cached_call("iga_shop.recipe_details", data, _recipe_details, ttl.RECIPES_CACHE)


# ---- sitemap/products -----------------------------------------------------------------------------

PRODUCT_SITEMAP_CAP = 10000   # the site emits exactly 10,000 product URLs (2026-10-28), not the full range


def _product_sitemap():
    return cached_call("iga_shop.sitemap_products_all", {},
                       lambda: parsers.parse_product_sitemap(fetch_sitemap("product-sitemap.xml")),
                       ttl.SITEMAP_CACHE)


def sitemap_products(page, limit):
    rows = _product_sitemap()
    start = _skip(page, limit)
    return {
        "sitemap": f"{refs.SITE}/product-sitemap.xml",
        "is_capped": len(rows) >= PRODUCT_SITEMAP_CAP,
        "note": (f"the site publishes at most {PRODUCT_SITEMAP_CAP} product URLs in its sitemap; "
                 "/iga-shop/categories/products?category=grocery walks the whole range of a store")
        if len(rows) >= PRODUCT_SITEMAP_CAP else None,
        "results": rows[start:start + limit],
        "pagination": parsers.pagination(page, limit, len(rows)),
    }


# ---- sitemap/links ---------------------------------------------------------------------------------

def _sitemap_links_all():
    def build():
        index = parsers.parse_sitemap_index(fetch_sitemap("sitemap_index.xml"))
        names = [u.rsplit("/", 1)[-1] for u in index]
        # The dedicated sitemaps first so their canonical links win over
        # sitemap.xml's "/1" page-one variants of the same pages.
        known = ("category-sitemap.xml", "recipe-sitemap.xml", "sitemap.xml")
        sources = [n for n in known if n in names] or list(known)
        merged = parsers.merge_sitemap_links(
            [(name, parsers.parse_sitemap_urls(fetch_sitemap(name))) for name in sources])
        return {"sitemaps": index, "links": merged}
    return cached_call("iga_shop.sitemap_links_all", {}, build, ttl.SITEMAP_CACHE)


def sitemap_links(type, page, limit):
    data = _sitemap_links_all()
    classes = parsers.LINK_TYPE_CLASSES.get(type)
    rows = [r for r in data["links"] if classes is None or r["type"] in classes]
    start = _skip(page, limit)
    counts = {}
    for row in data["links"]:
        counts[row["type"]] = counts.get(row["type"], 0) + 1
    return {
        "type": type,
        "sitemaps": data["sitemaps"],
        "counts_by_type": counts,
        "results": rows[start:start + limit],
        "pagination": parsers.pagination(page, limit, len(rows)),
    }
