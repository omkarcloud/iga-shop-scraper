"""Raw igashop.com.au JSON / XML -> clean dicts (pure functions, no I/O).

Fixtures (iga_shop/fixtures/, captured 2026-10-28 from store 32600 unless
named otherwise): stores_search_*.json, stores_nearby_melbourne.json,
product_494526.json (regular price), product_308953_on_special.json (TPR
markdown, nutrition panel, ingredients), product_not_found.json,
search_milk.json, search_misspelled.json (a replaced query),
search_no_results.json, specials_page1.json, category_hierarchy.json,
category_fruit_search.json, category_fruit_subcategories.json,
category_unknown_search.json, recipes_search_chicken.json, recipes_none.json,
recipe_pavlova.json, recipe_not_found.json, sitemap_index.xml, sitemap.xml,
category_sitemap.xml, recipe_sitemap.xml, product_sitemap_head.xml (the
first 60 of 10,000 product URLs).

Conventions: snake_case, `link` for URLs, booleans as questions, prices as
numbers with a separate `currency` ("AUD"), dates ISO, null for anything
absent. Internal noise is dropped: `metadata` (correlation ids), `_links`,
`isFavorite` / `isPastPurchased` (per-login flags, always false
anonymously), `taxDetails` (always empty), `siteId` / `categoryHierarchyId`
(platform ids), `took`, `isRestrictedExtended`, `facetHeaders`, `priority`
(recipe sort weight), `isConfigurable` (always false).
"""
import html as html_lib
import math
import re
from datetime import datetime

import config
from iga_shop import refs

CURRENCY = "AUD"

_TAG_RE = re.compile(r"<[^>]+>")
_BREAK_RE = re.compile(r"<\s*(?:br\s*/?|/p|/li|/div|/h[1-6]|/tr)\s*>", re.I)
_LI_RE = re.compile(r"<li[^>]*>(.*?)</li>", re.I | re.S)
_MONEY_RE = re.compile(r"-?\$?\s*(-?[0-9][0-9,]*(?:\.[0-9]+)?)")
_UNIT_PRICE_RE = re.compile(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(avg)?\s*/?\s*([A-Za-z0-9 ]*)$")
_ORIGIN_RE = re.compile(r"Country of Origin:?\s*(.+?)\s*$", re.I)
_ALLERGEN_RE = re.compile(r"Allergen(?:s)? may be present:?\s*(.+?)\s*$", re.I)
_CONTAINS_RE = re.compile(r"^Contains:?\s*(.+?)\s*$", re.I)
_SKU_FROM_PATH_RE = re.compile(r"/product/(?:(.*?)-)?([0-9]{3,13})$")
_UK_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


# ---- value helpers ---------------------------------------------------------------------

def clean(value):
    """Strings trimmed; "" -> None; everything else passed through."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def to_float(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = _MONEY_RE.search(value)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                return None
    return None


def to_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def html_to_text(value):
    """HTML fragment -> plain text with one newline per block / <br>."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = _BREAK_RE.sub("\n", value)
    text = _TAG_RE.sub("", text)
    text = html_lib.unescape(text).replace("\xa0", " ")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return text or None


def html_to_steps(value):
    """An <ol>/<ul> of steps -> list of plain strings; any other HTML ->
    one item per line."""
    if not isinstance(value, str) or not value.strip():
        return []
    items = _LI_RE.findall(value)
    if items:
        steps = [html_to_text(item) for item in items]
    else:
        steps = (html_to_text(value) or "").split("\n")
    return [s for s in steps if s]


def iso_date(value):
    """'28/10/2026' (the product tprInfo dates, d/m/yyyy) -> '2026-10-28';
    ISO strings pass through trimmed; anything else -> None."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    match = _UK_DATE_RE.match(value)
    if match:
        day, month, year = (int(g) for g in match.groups())
        try:
            return datetime(year, month, day).date().isoformat()
        except ValueError:
            return None
    return value


def unit_price(text):
    """'$3.50/l' -> {amount 3.5, per 'l', is_average False, text}; '$1.06
    avg/ea' marks the per-item average of a weighed line."""
    text = clean(text)
    if not text:
        return None
    match = _UNIT_PRICE_RE.match(text)
    if not match:
        return {"amount": to_float(text), "per": None, "is_average": "avg" in text.lower(), "text": text}
    amount, avg, per = match.groups()
    return {
        "amount": to_float(amount),
        "per": clean(per),
        "is_average": bool(avg),
        "text": text,
    }


def measure(value):
    """The storefront's unit objects ({abbreviation, label, size, type}) ->
    {value, unit, label}: unitOfSize 3 l -> {3, "l", "Litre"}."""
    if not isinstance(value, dict):
        return None
    return {
        "value": to_float(value.get("size")),
        "unit": clean(value.get("abbreviation")) or clean(value.get("type")),
        "label": clean(value.get("label")),
    }


# ---- description -----------------------------------------------------------------------------

def parse_description(raw):
    """The HTML description carries a few labelled trailers ("Country of
    Origin: Made in Netherlands", "Allergen may be present: Milk",
    "Contains: Soy"): split them out, keep the prose as text."""
    text = html_to_text(raw)
    origin = allergens = contains = None
    prose = []
    for line in (text or "").split("\n"):
        match = _ORIGIN_RE.match(line)
        if match and origin is None:
            origin = clean(match.group(1))
            continue
        match = _ALLERGEN_RE.match(line)
        if match and allergens is None:
            allergens = clean(match.group(1))
            continue
        match = _CONTAINS_RE.match(line)
        if match and contains is None:
            contains = clean(match.group(1))
            continue
        prose.append(line)
    return {
        "text": "\n".join(prose).strip() or None,
        "country_of_origin": origin,
        "allergens_may_be_present": allergens,
        "contains": contains,
    }


# ---- category breadcrumbs --------------------------------------------------------------------

def _category_ref(entry):
    if not isinstance(entry, dict):
        return None
    identifier = clean(entry.get("retailerId"))
    return {
        "id": identifier,
        "name": clean(entry.get("category")),
        "breadcrumb": clean((entry.get("categoryBreadcrumb") or "").strip("/")),
        "slug": refs.category_slug(identifier) if identifier else None,
    }


def _categories(raw):
    """categories[] (root first) -> list of refs minus the "Grocery" root."""
    out = []
    for entry in raw if isinstance(raw, list) else []:
        ref = _category_ref(entry)
        if ref and ref["id"] and ref["id"] != "Grocery":
            out.append(ref)
    return out


def _default_category(raw, breadcrumbs):
    """defaultCategory is a list of refs on listings and a bare name on the
    product record; fall back to the deepest breadcrumb."""
    if isinstance(raw, list) and raw:
        ref = _category_ref(raw[0])
        if ref and ref["id"]:
            return ref
    if isinstance(raw, str) and raw.strip():
        for ref in reversed(breadcrumbs):
            if ref["name"] == raw.strip():
                return ref
        return {"id": None, "name": raw.strip(), "breadcrumb": None, "slug": None}
    return breadcrumbs[-1] if breadcrumbs else None


# ---- promotions / pricing --------------------------------------------------------------------

def _special(item):
    """The active temporary price reduction: listings carry tprPrice[]
    (ISO datetimes), the product record tprInfo {} (d/m/yyyy)."""
    tpr = item.get("tprPrice")
    if isinstance(tpr, list) and tpr:
        active = next((t for t in tpr if isinstance(t, dict) and t.get("active")), None)
        entry = active or (tpr[0] if isinstance(tpr[0], dict) else None)
        if entry:
            return {
                "label": clean(entry.get("label")),
                "price": to_float(entry.get("markdown")) if entry.get("markdown") is not None
                else to_float(entry.get("wholePrice")),
                "starts_at": clean(entry.get("effectiveFrom")),
                "ends_at": clean(entry.get("effectiveUntil")),
                "is_active": bool(entry.get("active", True)),
            }
    info = item.get("tprInfo")
    if isinstance(info, dict) and info:
        return {
            "label": clean(info.get("label")),
            "price": to_float(info.get("markdown")),
            "starts_at": iso_date(info.get("effectiveFrom")),
            "ends_at": iso_date(info.get("effectiveUntil")),
            "is_active": True,
        }
    return None


def _messages(raw):
    """shoppingRuleMessages {blocking: [], information: [{header, detail}]}
    -> flat list; the product record carries the same shape or null."""
    out = []
    if not isinstance(raw, dict):
        return out
    for kind in ("blocking", "information"):
        for entry in raw.get(kind) or []:
            if isinstance(entry, dict):
                out.append({
                    "type": kind,
                    "title": clean(entry.get("header")),
                    "text": clean(entry.get("detail")),
                })
    return out


def _attributes(raw):
    """attributes {"Alcohol Restricted": true, ...} -> the flag plus the
    rest as-is (snake_case keys)."""
    attrs = raw if isinstance(raw, dict) else {}
    other = {re.sub(r"[^a-z0-9]+", "_", k.lower()).strip("_"): v
             for k, v in attrs.items() if k != "Alcohol Restricted"}
    return bool(attrs.get("Alcohol Restricted")), (other or None)


def _pricing(item):
    price = to_float(item.get("priceNumeric"))
    if price is None:
        price = to_float(item.get("wholePrice"))
    if price is None:
        price = to_float(item.get("price"))
    was = to_float(item.get("wasPriceNumeric"))
    if was is None:
        was = to_float(item.get("wasWholePrice"))
    if was is None:
        was = to_float(item.get("wasPrice"))
    special = _special(item)
    label = clean(item.get("priceLabel"))
    is_special = bool(special) or was is not None or item.get("priceSource") == "tpr"
    saving = round(was - price, 2) if (was is not None and price is not None and was > price) else None
    return {
        "price": price,
        "was_price": was,
        "currency": CURRENCY,
        "saving": saving,
        "saving_percent": round(saving / was * 100) if (saving and was) else None,
        "label": label,
        "is_on_special": is_special,
        "special": special,
        "unit_price": unit_price(item.get("pricePerUnit") or item.get("unitPrice")),
        "sold_by": (clean(item.get("sellBy")) or "").lower() or None,
        "has_loyalty_discount": bool(item.get("hasLoyaltyDiscount")) if "hasLoyaltyDiscount" in item else None,
        "promotions": item.get("promotions") or [],
        "promotion_info": item.get("promotionInfo") or [],
        "points_promotions": item.get("pointsBasedPromotions") or [],
    }


def _image(raw):
    """image / primaryImage {cell, default, details, template, zoom} are the
    same Cloudinary URL on every size (2026-10-28): keep one."""
    if isinstance(raw, dict):
        return clean(raw.get("default") or raw.get("details") or raw.get("zoom") or raw.get("cell"))
    return clean(raw) if isinstance(raw, str) else None


# ---- listing item ------------------------------------------------------------------------------

def parse_listing_item(item):
    """One product of a search / specials / category / recipe-ingredient
    listing -> the card."""
    if not isinstance(item, dict):
        return None
    sku = clean(item.get("sku")) or clean(item.get("productId"))
    name = clean(item.get("name"))
    breadcrumbs = _categories(item.get("categories"))
    is_alcohol, attributes = _attributes(item.get("attributes"))
    description = parse_description(item.get("description"))
    return {
        "sku": sku,
        "name": name,
        "brand": clean(item.get("brand")),
        "link": refs.product_link(sku, name) if sku else None,
        "image": _image(item.get("image")),
        "size": measure(item.get("unitOfSize")),
        "is_available": bool(item.get("available")) if "available" in item else None,
        "is_alcohol_restricted": is_alcohol,
        "pricing": _pricing(item),
        "description": description["text"],
        "country_of_origin": description["country_of_origin"],
        "allergens_may_be_present": description["allergens_may_be_present"],
        "category": _default_category(item.get("defaultCategory"), breadcrumbs),
        "categories": breadcrumbs,
        "attributes": attributes,
        "messages": _messages(item.get("shoppingRuleMessages")),
        "promotions_count": to_int(item.get("totalNumberOfPromotions")),
    }


def _facets(raw):
    """facets {"Brand": [{value, count}], ...} -> {brands, categories,
    dietary, on_sale, other} each a list of {name, count}."""
    facets = raw if isinstance(raw, dict) else {}

    def rows(key):
        return [{"name": clean(f.get("value")), "count": to_int(f.get("count"))}
                for f in facets.get(key) or [] if isinstance(f, dict) and clean(f.get("value"))]
    return {
        "brands": rows("Brand"),
        "categories": rows("Category"),
        "dietary": rows("Dietary"),
        "on_sale": rows("On Sale"),
        "other": rows("Additional Filters"),
    }


def _suggestions(raw):
    """suggestions {originalQuery, performedQuery, replaced, options}: the
    misspelling corrector ("chese" -> "cheese")."""
    if not isinstance(raw, dict):
        return None
    performed = clean(raw.get("performedQuery"))
    original = clean(raw.get("originalQuery"))
    if not performed and not original and not raw.get("options"):
        return None
    return {
        "original_query": original,
        "performed_query": performed,
        "was_corrected": bool(raw.get("replaced")),
        "options": [clean(o) for o in (raw.get("options") or []) if clean(o)],
    }


def parse_listing(payload, page, limit):
    """A search / specials / category listing payload -> {results,
    facets, suggestions, pagination} (total_count from the storefront's
    `total`; the window stops at 10,000 rows, see config.IGA_SHOP_MAX_SKIP)."""
    payload = payload if isinstance(payload, dict) else {}
    items = [parse_listing_item(i) for i in payload.get("items") or []]
    total = to_int(payload.get("total"))
    return {
        "results": [i for i in items if i],
        "facets": _facets(payload.get("facets")),
        "suggestions": _suggestions(payload.get("suggestions")),
        "pagination": pagination(page, limit, total, window=config.IGA_SHOP_MAX_SKIP),
    }


def pagination(page, limit, total, window=None):
    total_pages = max(1, math.ceil(total / limit)) if total else (1 if total == 0 else None)
    if total_pages and window:
        # the storefront answers an empty page past `window` rows (skip >=
        # config.IGA_SHOP_MAX_SKIP) and the schema rejects those pages, so
        # the last page is the last one whose skip is inside the window
        total_pages = min(total_pages, math.ceil(window / limit))
    block = {"page": page, "items_per_page": limit, "total_pages": total_pages, "total_count": total}
    if total is None:
        block["has_next"] = False
    return block


# ---- product record ----------------------------------------------------------------------------

def _nutrition(raw):
    """nutritionProfiles {"Per 100g / Per 100mL": {"Energy": {size, abbreviation,
    unit, percentDailyValue, traceAmount}, ...}, "Per serve": {...}} ->
    [{basis, nutrients: [{name, value, unit, daily_value_percent, is_trace}]}]."""
    out = []
    for basis, nutrients in (raw.items() if isinstance(raw, dict) else []):
        rows = []
        for name, entry in (nutrients.items() if isinstance(nutrients, dict) else []):
            if not isinstance(entry, dict):
                continue
            rows.append({
                "name": clean(name),
                "value": to_float(entry.get("size")),
                "unit": clean(entry.get("abbreviation")) or clean(entry.get("unit")),
                "daily_value_percent": to_float(entry.get("percentDailyValue")),
                "is_trace": bool(entry.get("traceAmount")),
            })
        out.append({"basis": clean(basis), "nutrients": rows})
    return out


def _images(record):
    primary = _image(record.get("primaryImage"))
    extra = record.get("additionalImages")
    more = []
    if isinstance(extra, dict):
        more = [clean(u) for u in (extra.get("default") or extra.get("details") or []) if clean(u)]
    images = [primary] + [u for u in more if u != primary] if primary else more
    return [u for u in images if u]


def _location(raw):
    if not isinstance(raw, dict):
        return None
    out = {
        "aisle": clean(raw.get("aisle")),
        "bay": clean(raw.get("bay")),
        "shelf": clean(raw.get("shelf")),
        "section": clean(raw.get("section")),
    }
    return out if any(out.values()) else None


def parse_product(record, sku=None, store=None):
    """GET /stores/{store}/products/{sku} -> the full product."""
    record = record if isinstance(record, dict) else {}
    sku = clean(record.get("sku")) or sku
    name = clean(record.get("name"))
    breadcrumbs = _categories(record.get("categories"))
    is_alcohol, attributes = _attributes(record.get("attributes"))
    description = parse_description(record.get("description"))
    images = _images(record)
    ingredients = clean(record.get("ingredients"))
    servings = to_int(record.get("numberOfServings"))
    pricing = _pricing(record)
    return {
        "sku": sku,
        "name": name,
        "brand": clean(record.get("brand")),
        "link": refs.product_link(sku, name) if sku else None,
        "image": images[0] if images else None,
        "images": images,
        "size": measure(record.get("unitsOfSize") or record.get("unitOfSize")),
        "is_available": bool(record.get("available")) if "available" in record else None,
        "is_alcohol_restricted": is_alcohol,
        "pricing": pricing,
        "description": description["text"],
        "country_of_origin": description["country_of_origin"],
        "allergens_may_be_present": description["allergens_may_be_present"],
        "contains": description["contains"],
        "ingredients": ingredients,
        "nutrition": {
            "servings_per_pack": servings if servings else None,
            "serving_size": clean(record.get("servingSize")),
            "panels": _nutrition(record.get("nutritionProfiles")),
        },
        "category": _default_category(record.get("defaultCategory"), breadcrumbs),
        "categories": breadcrumbs,
        "store_location": _location(record.get("location")),
        "weight_increment": to_float(record.get("weightIncrement")),
        "attributes": attributes,
        "extended_attributes": record.get("attributes_ext") or None,
        "messages": _messages(record.get("shoppingRuleMessages")),
        "store": {"number": store} if store else None,
    }


# ---- stores ------------------------------------------------------------------------------------

def _opening_hours(text):
    """'Mon-Fri: 7am–9pm; Sat-Sun: 8am–8pm' -> [{days, hours}] plus the text."""
    text = clean(text)
    if not text:
        return None
    rows = []
    for part in re.split(r"\s*;\s*", text):
        days, sep, hours = part.partition(":")
        if sep and clean(hours):
            rows.append({"days": clean(days), "hours": clean(hours)})
    return {"text": text, "periods": rows}


def parse_store(item, distance_km=None):
    item = item if isinstance(item, dict) else {}
    name = clean(item.get("name"))
    location = item.get("location") if isinstance(item.get("location"), dict) else {}
    modes = [m.lower() for m in (item.get("shoppingModes") or []) if isinstance(m, str)]
    out = {
        "number": clean(item.get("retailerStoreId")),
        "id": clean(item.get("id")),
        "name": name,
        "slug": refs.slugify(name) if name else None,
        "link": refs.store_link(name) if name else None,
        "address": {
            "line1": clean((item.get("addressLine1") or "").rstrip(", ")),
            "line2": clean(item.get("addressLine2")),
            "line3": clean(item.get("addressLine3")),
            "suburb": clean(item.get("city")),
            "state": clean(item.get("countyProvinceState")),
            "postcode": clean(item.get("postCode")),
            "country": clean(item.get("country")),
        },
        "phone": clean(item.get("phone")),
        "email": clean(item.get("email")),
        "opening_hours": _opening_hours(item.get("openingHours")),
        "location": {
            "latitude": to_float(location.get("latitude")),
            "longitude": to_float(location.get("longitude")),
        },
        "shopping_modes": modes,
        "has_delivery": "delivery" in modes,
        "has_pickup": "pickup" in modes,
        "is_active": (clean(item.get("status")) or "").lower() == "active",
        "type": clean(item.get("type")),
        "timezone": clean(item.get("timeZone")),
        "currency": clean(item.get("currency")),
        "languages": [clean(l.get("isoCode")) for l in item.get("languages") or []
                      if isinstance(l, dict) and clean(l.get("isoCode"))],
    }
    if distance_km is not None:
        out["distance_km"] = distance_km
    return out


def parse_stores(payload, page=1, limit=20):
    payload = payload if isinstance(payload, dict) else {}
    total = to_int(payload.get("total"))
    stores = [parse_store(s) for s in payload.get("items") or [] if isinstance(s, dict)]
    if total is None:
        total = len(stores)
    return {"results": stores, "pagination": pagination(page, limit, total)}


def haversine_km(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


def parse_nearby(payload, latitude, longitude):
    """/near/... {items[]} -> stores nearest first with a computed
    straight-line distance (the storefront publishes none)."""
    payload = payload if isinstance(payload, dict) else {}
    out = []
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        loc = item.get("location") if isinstance(item.get("location"), dict) else {}
        distance = haversine_km(latitude, longitude, to_float(loc.get("latitude")), to_float(loc.get("longitude")))
        out.append(parse_store(item, distance_km=distance))
    out.sort(key=lambda s: (s.get("distance_km") is None, s.get("distance_km") or 0))
    return out


def match_store(stores, lookup):
    """The store for a resolved `store` value against the parsed store list:
    store number, then postcode, then page slug, then a case-insensitive
    name / suburb match (number before postcode because 76 of 540 store
    numbers are 4 digits too). None when nothing matches."""
    lookup = (lookup or "").strip()
    if not lookup:
        return None
    low = lookup.lower()
    for store in stores:
        if store.get("number") == lookup:
            return store
    if refs.POSTCODE_RE.match(lookup):
        for store in stores:
            if (store.get("address") or {}).get("postcode") == lookup:
                return store
    slug = refs.slugify(lookup)
    for store in stores:
        if slug and store.get("slug") == slug:
            return store
    for store in stores:
        name = (store.get("name") or "").lower()
        suburb = ((store.get("address") or {}).get("suburb") or "").lower()
        if low == name or low == suburb:
            return store
    for store in stores:
        name = (store.get("name") or "").lower()
        suburb = ((store.get("address") or {}).get("suburb") or "").lower()
        if low in name or low in suburb:
            return store
    return None


# ---- category tree ------------------------------------------------------------------------------

def parse_category_tree(payload):
    """categoryHierarchy {identifier, displayName, children[]} -> the
    departments under the "Grocery" root as nested {id, name, slug, link,
    depth, children}. The platform root ("retailer-prod-v3") and the single
    "Grocery" node are skipped: "Grocery" is the whole catalogue."""
    payload = payload if isinstance(payload, dict) else {}
    nodes = payload.get("children") or []
    grocery = next((n for n in nodes if isinstance(n, dict) and n.get("identifier") == "Grocery"), None)
    departments = grocery.get("children") if grocery else nodes

    def node(raw, parent_id, depth):
        identifier = clean(raw.get("identifier"))
        children = [node(c, identifier, depth + 1) for c in raw.get("children") or [] if isinstance(c, dict)]
        return {
            "id": identifier,
            "name": clean(raw.get("displayName")),
            "slug": refs.category_slug(identifier),
            "link": refs.category_link(identifier, parent_id if depth > 1 else None),
            "depth": depth,
            "children_count": len(children),
            "children": children,
        }
    return [node(d, None, 1) for d in departments if isinstance(d, dict)]


def flatten_categories(tree):
    """Depth-first list of every node with a `parent_id` (and without
    `children`), the "Grocery" catalogue root first."""
    out = [{"id": "Grocery", "name": "All products", "slug": "grocery", "link": None,
            "depth": 0, "parent_id": None, "children_count": len(tree)}]

    def walk(nodes, parent_id):
        for n in nodes:
            row = {k: v for k, v in n.items() if k != "children"}
            row["parent_id"] = parent_id
            out.append(row)
            walk(n.get("children") or [], n.get("id"))
    walk(tree, None)
    return out


def _node_keys(row):
    return {refs.category_key(row.get("id")), refs.category_key(row.get("name")),
            refs.category_key(row.get("slug"))} - {""}


def find_category(flat, key):
    """The flattened node whose identifier / slug / name folds to `key`
    (refs.category_key). A "parent/leaf" key prefers the leaf under that
    parent and falls back to any leaf match; a bare key takes the first
    match in tree order."""
    if not key:
        return None
    parent_key, _, leaf_key = key.rpartition("/")
    by_id = {row.get("id"): row for row in flat}
    fallback = None
    for row in flat:
        if leaf_key not in _node_keys(row):
            continue
        if not parent_key:
            return row
        parent = by_id.get(row.get("parent_id"))
        if parent and parent_key in _node_keys(parent):
            return row
        fallback = fallback or row
    if fallback is None and parent_key:
        # a display name with a slash ("Soju / Shochu") folds whole
        whole = refs.category_key(key)
        fallback = next((row for row in flat if whole in _node_keys(row)), None)
    return fallback


def parse_category_overview(payload):
    """categories/{id}/subcategories/search -> {name, id, total_count,
    subcategories: [{id, name, slug, link, total_count, products}]}."""
    payload = payload if isinstance(payload, dict) else {}
    parent = clean(payload.get("retailerCategoryId"))
    # the departments under "Grocery" link as /categories/<slug>, like the tree
    link_parent = parent if parent != "Grocery" else None
    blocks = []
    subs = payload.get("subCategories")
    for name, block in (subs.items() if isinstance(subs, dict) else []):
        if not isinstance(block, dict):
            continue
        identifier = clean(block.get("retailerCategoryId"))
        products = [parse_listing_item(i) for i in block.get("items") or []]
        blocks.append({
            "id": identifier,
            "name": clean(name),
            "slug": refs.category_slug(identifier) if identifier else None,
            "link": refs.category_link(identifier, link_parent) if identifier else None,
            "total_count": to_int(block.get("total")),
            "products": [p for p in products if p],
        })
    return {
        "id": parent,
        "name": clean(payload.get("title")),
        "total_count": to_int(payload.get("total")),
        "subcategories_count": len(blocks),
        "subcategories": blocks,
    }


# ---- recipes -----------------------------------------------------------------------------------

def _recipe_image(raw):
    if isinstance(raw, dict):
        return clean(raw.get("url"))
    return clean(raw) if isinstance(raw, str) else None


def parse_recipe_card(item):
    item = item if isinstance(item, dict) else {}
    recipe_id = clean(item.get("id"))
    prep = to_int(item.get("preparationTime"))
    cook = to_int(item.get("cookTime"))
    return {
        "id": recipe_id,
        "name": clean(item.get("name")),
        "link": refs.recipe_link(recipe_id) if recipe_id else None,
        "author": clean(item.get("author")),
        "short_description": clean(item.get("shortDescription")),
        "image": _recipe_image(item.get("galleryImage")),
        "badge_image": _recipe_image(item.get("badgeImage")),
        "prep_time_minutes": prep,
        "cook_time_minutes": cook,
        "total_time_minutes": (prep or 0) + (cook or 0) if (prep is not None or cook is not None) else None,
    }


def parse_recipes(payload, page, limit):
    """/recipes -> {results, categories (filter counts), pagination}."""
    payload = payload if isinstance(payload, dict) else {}
    links = (payload.get("filters") or {}).get("_links") if isinstance(payload.get("filters"), dict) else {}
    categories = []
    for key, entry in (links.items() if isinstance(links, dict) else []):
        if isinstance(entry, dict):
            categories.append({"name": clean(entry.get("displayName")) or clean(key),
                               "count": to_int(entry.get("count"))})
    total = to_int(payload.get("total"))
    return {
        "results": [parse_recipe_card(i) for i in payload.get("items") or [] if isinstance(i, dict)],
        "categories": categories,
        "pagination": pagination(page, limit, total, window=config.IGA_SHOP_MAX_SKIP),
    }


def parse_recipe(record, recipe_id=None):
    record = record if isinstance(record, dict) else {}
    recipe_id = clean(record.get("id")) or recipe_id
    tags = record.get("tags") if isinstance(record.get("tags"), dict) else {}
    groups = []
    for group in record.get("ingredients") or []:
        if not isinstance(group, dict):
            continue
        products = [parse_listing_item(i) for i in group.get("items") or []]
        groups.append({
            "name": clean(group.get("name")),
            "quantity": clean(group.get("size")),
            "products": [p for p in products if p],
        })
    prep = to_int(record.get("preparationTime"))
    cook = to_int(record.get("cookTime"))
    meta_keywords = record.get("metaKeywords")
    return {
        "id": recipe_id,
        "name": clean(record.get("name")),
        "link": refs.recipe_link(recipe_id) if recipe_id else None,
        "author": clean(record.get("author")),
        "short_description": clean(record.get("shortDescription")),
        "directions": html_to_steps(record.get("directions")),
        "ingredients": groups,
        "ingredients_count": len(groups),
        "categories": [clean(c) for c in tags.get("category") or [] if clean(c)],
        "tags": {k: v for k, v in tags.items() if k != "category"} or None,
        "prep_time_minutes": prep,
        "cook_time_minutes": cook,
        "total_time_minutes": (prep or 0) + (cook or 0) if (prep is not None or cook is not None) else None,
        "servings": to_int(record.get("servings")),
        "calories": to_float(record.get("calories")),
        "nutritional_info": clean(record.get("nutritionalInfo")) if isinstance(record.get("nutritionalInfo"), str)
        else record.get("nutritionalInfo"),
        "images": {
            "gallery": _recipe_image(record.get("galleryImage")),
            "featured": _recipe_image(record.get("featuredImage")),
            "mobile": _recipe_image(record.get("mobileImage")),
            "badge": _recipe_image(record.get("badgeImage")),
        },
        "video": clean(record.get("embeddedVideo")),
        "is_active": (clean(record.get("status")) or "").lower() == "active",
        "published_from": clean(record.get("start")),
        "published_until": clean(record.get("end")),
        "store_numbers": record.get("storeIds") or None,
        "meta": {
            "title": clean(record.get("metaTitle")),
            "description": clean(record.get("metaDescription")),
            "keywords": [clean(k) for k in meta_keywords if clean(k)] if isinstance(meta_keywords, list) else None,
        },
    }


# ---- sitemaps -------------------------------------------------------------------------------------

_URL_BLOCK_RE = re.compile(r"<url>(.*?)</url>", re.S)
_SITEMAP_BLOCK_RE = re.compile(r"<sitemap>(.*?)</sitemap>", re.S)
_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S)
_LASTMOD_RE = re.compile(r"<lastmod>\s*(.*?)\s*</lastmod>", re.S)
_CHANGEFREQ_RE = re.compile(r"<changefreq>\s*(.*?)\s*</changefreq>", re.S)
_PRIORITY_RE = re.compile(r"<priority>\s*(.*?)\s*</priority>", re.S)


def _tag(regex, block):
    match = regex.search(block)
    return html_lib.unescape(match.group(1)).strip() if match else None


def parse_sitemap_index(xml):
    """sitemap_index.xml -> the child sitemap URLs."""
    return [u for u in (_tag(_LOC_RE, b) for b in _SITEMAP_BLOCK_RE.findall(xml or "")) if u]


def parse_sitemap_urls(xml):
    """A urlset -> [{link, last_modified, change_frequency, priority}]."""
    out = []
    for block in _URL_BLOCK_RE.findall(xml or ""):
        link = _tag(_LOC_RE, block)
        if not link:
            continue
        out.append({
            "link": link,
            "last_modified": _tag(_LASTMOD_RE, block),
            "change_frequency": _tag(_CHANGEFREQ_RE, block),
            "priority": to_float(_tag(_PRIORITY_RE, block)),
        })
    return out


def parse_product_sitemap(xml):
    """product-sitemap.xml -> [{sku, slug, name, link}] (name is the slug
    with its hyphens undone — the sitemap carries no title)."""
    out = []
    for row in parse_sitemap_urls(xml):
        match = _SKU_FROM_PATH_RE.search(row["link"])
        slug = match.group(1) if match else None
        out.append({
            "sku": match.group(2) if match else None,
            "slug": slug or None,
            "name": " ".join(w for w in (slug or "").split("-") if w) or None,
            "link": row["link"],
        })
    return out


def classify_link(link):
    """A non-product sitemap URL -> its class: category / recipe /
    recipes_list / specials / home / page."""
    path = re.sub(r"^https?://[^/]+", "", link or "").rstrip("/")
    if not path:
        return "home"
    if path.startswith("/categories/"):
        return "category"
    if path.startswith("/recipe/"):
        return "recipe"
    if path in ("/recipes", "/recipe") or path.startswith("/recipes/"):
        return "recipes_list"
    if path == "/specials" or path.startswith("/specials/"):
        return "specials"
    return "page"


# Public `type` filter -> the classes it selects.
LINK_TYPE_CLASSES = {
    "all": None,
    "categories": ("category",),
    "recipes": ("recipe", "recipes_list"),
    "specials": ("specials",),
    "pages": ("page", "home"),
}


_PAGE_ONE_RE = re.compile(r"/1$")


def merge_sitemap_links(sitemaps):
    """[(name, [url rows])] -> one deduplicated list (first occurrence
    wins, a later lastmod fills a missing one) with `type` and `sitemap`.
    sitemap.xml lists listing pages as their page 1 (/categories/baby/
    12-months/1, /recipes/1): that is the same page as the bare link, so
    the trailing "/1" folds into it."""
    seen = {}
    for name, rows in sitemaps:
        for row in rows:
            link = _PAGE_ONE_RE.sub("", row["link"].rstrip("/")) or row["link"]
            existing = seen.get(link)
            if existing:
                for key in ("last_modified", "change_frequency", "priority"):
                    if existing.get(key) is None and row.get(key) is not None:
                        existing[key] = row[key]
                continue
            seen[link] = {"link": link, "type": classify_link(link),
                          "last_modified": row.get("last_modified"),
                          "change_frequency": row.get("change_frequency"),
                          "priority": row.get("priority"), "sitemap": name}
    return list(seen.values())
