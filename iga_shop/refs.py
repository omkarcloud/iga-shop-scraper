"""Reference resolvers, link builders and the sort / shopping-mode tables
for /iga-shop/* (igashop.com.au, Metcash's IGA online store, Australia).

ONE param per input (tripadvisor QueryOrIdField convention, never a
sibling `url` / `id` pair). Each resolver turns the raw query value into
the token api.py works with and raises ValueError with a user-facing
message (schema_fields.RefField turns it into a 400):

  product   a SKU ("494526") OR a product link
            (https://www.igashop.com.au/product/<slug>-<sku>) -> the SKU.
            The SKU is the trailing digits of the product path; the slug
            is optional on the site (/product/494526 resolves too).
  store     a store number ("32600"), a postcode ("3065"), a suburb or
            store name ("fitzroy"), OR a store link
            (https://www.igashop.com.au/store/<slug>) -> a StoreRef that
            api.py matches against the cached store list.
  category  a category identifier ("Apples_Pears_and_Bananas"), its slug
            ("apples-pears-and-bananas"), its display name ("Apples, Pears
            and Bananas") OR a category link
            (https://www.igashop.com.au/categories/fruit/apples-pears-and-bananas)
            -> a lookup key api.py matches against the cached category tree.
  recipe    a recipe id (a UUID or a short numeric id like "071026") OR a
            recipe link (https://www.igashop.com.au/recipe/<id>) -> the id.

Identifiers on the site (captured 2026-10-28):
  * product SKU: 3-13 digits ("494526", "1800000080658", "80050030")
  * store number (retailerStoreId): 3-6 digits ("32600", "41524"); every
    store also has a UUID `id` the API never takes as a path param
  * category identifier: Title_Case_With_Underscores; the page slug is the
    same string lower-cased with hyphens ("Fruit_and_Vegetable" ->
    "fruit-and-vegetable"), checked against all 502 category-sitemap URLs
  * recipe id: a UUID or a numeric string
"""
import re
import unicodedata
from urllib.parse import unquote, urlparse

SITE = "https://www.igashop.com.au"
SITE_HOSTS = ("igashop.com.au",)

# The store's shopping modes (the site's own constants, _app chunk).
SHOPPING_MODE_PICKUP = "11111111-1111-1111-1111-111111111111"
SHOPPING_MODE_DELIVERY = "22222222-2222-2222-2222-222222222222"
SHOPPING_MODE_PLANNING = "33333333-3333-3333-3333-333333333333"

# Public sort values -> the storefront's `sort` token (its own sorting
# links: relevance / brand / brand desc / price / price desc).
SORTS = {
    "relevance": "relevance",
    "price_asc": "price",
    "price_desc": "price desc",
    "brand_asc": "brand",
    "brand_desc": "brand desc",
}

# Sitemap link classes for /iga-shop/sitemap/links.
LINK_TYPES = ("all", "categories", "recipes", "specials", "pages")

SKU_RE = re.compile(r"^[0-9]{3,13}$")
STORE_NUMBER_RE = re.compile(r"^[0-9]{3,6}$")
POSTCODE_RE = re.compile(r"^[0-9]{4}$")
RECIPE_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")
CATEGORY_KEY_RE = re.compile(r"^[A-Za-z0-9À-ɏ][A-Za-z0-9À-ɏ _,+&'()./-]{0,120}$")

_PRODUCT_PATH_RE = re.compile(r"/product/(?:[^/?#]*?-)?([0-9]{3,13})(?:[/?#]|$)")
_STORE_PATH_RE = re.compile(r"/store/([^/?#]+)")
_RECIPE_PATH_RE = re.compile(r"/recipe/([A-Za-z0-9-]+)")


_BARE_HOST_RE = re.compile(r"^(?:www\.)?igashop\.com\.au(?:[/?#]|$)", re.I)
_SITE_PATH_RE = re.compile(r"^/(?:product|store|categories|recipe)/", re.I)


def _is_link(value):
    """A full URL, a scheme-less igashop.com.au/... link, or a bare site
    path (/product/..., /store/..., /categories/..., /recipe/...)."""
    return (value.startswith(("http://", "https://", "//"))
            or bool(_BARE_HOST_RE.match(value)) or bool(_SITE_PATH_RE.match(value)))


def _site_url(value, what):
    """A pasted link -> its URL, or ValueError when it is another site's."""
    if value.startswith("//"):
        url = "https:" + value
    elif value.startswith("/"):
        url = SITE + value
    elif _BARE_HOST_RE.match(value):
        url = "https://" + value
    else:
        url = value
    host = (urlparse(url).hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in SITE_HOSTS):
        raise ValueError(f"Must be an igashop.com.au {what} link.")
    return url


def slugify(text):
    """The site's own slug rule as far as it is known (checked on 8 store
    pages 2026-10-28): ASCII-fold, drop apostrophes, "&" -> "and", every
    other run of non-alphanumerics -> "-"."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = text.lower().replace("&", " and ")
    text = re.sub(r"['\u2019]", "", text)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


# ---- product ------------------------------------------------------------------

def resolve_product(value):
    """Bare SKU or a product link -> the SKU."""
    value = (value or "").strip()
    if SKU_RE.match(value):
        return value
    if _is_link(value):
        url = _site_url(value, "product")
        match = _PRODUCT_PATH_RE.search(urlparse(url).path)
        if match:
            return match.group(1)
        raise ValueError("Must be an igashop.com.au product link "
                         "(https://www.igashop.com.au/product/<name>-<sku>).")
    raise ValueError("Must be a product SKU (e.g. 494526) or an igashop.com.au product link.")


def product_link(sku, name=None):
    slug = slugify(name) if name else ""
    return f"{SITE}/product/{slug + '-' if slug else ''}{sku}"


# ---- store -------------------------------------------------------------------

def resolve_store(value):
    """Store number / postcode / suburb / name / store link -> the lookup
    string api._store_for matches against the cached store list, in this
    order: store number, postcode, page slug, then a case-insensitive
    name / suburb match. A link collapses to its slug; a plain string
    keeps the cache key readable."""
    value = (value or "").strip()
    if not value:
        raise ValueError("Must not be empty.")
    if _is_link(value):
        url = _site_url(value, "store")
        match = _STORE_PATH_RE.search(urlparse(url).path)
        if match:
            return slugify(unquote(match.group(1)))
        raise ValueError("Must be an igashop.com.au store link "
                         "(https://www.igashop.com.au/store/<name>).")
    if len(value) > 80:
        raise ValueError("Store name is too long (80 characters at most).")
    return value


def store_link(name):
    return f"{SITE}/store/{slugify(name)}"


# ---- category ------------------------------------------------------------------

def category_slug(identifier):
    """Category identifier -> its page slug ("Fruit_and_Vegetable" ->
    "fruit-and-vegetable")."""
    return (identifier or "").lower().replace("_", "-")


def category_link(identifier, parent_identifier=None):
    """The category page: /categories/<slug> for a department,
    /categories/<parent slug>/<slug> below (the site nests one level only:
    a leaf links under its direct parent, as in the category sitemap)."""
    slug = category_slug(identifier)
    if parent_identifier:
        return f"{SITE}/categories/{category_slug(parent_identifier)}/{slug}"
    return f"{SITE}/categories/{slug}"


def category_key(value):
    """The comparison key for a category: identifier, slug and display name
    all fold to the same lower-case alphanumeric string
    ("Apples_Pears_and_Bananas" / "apples-pears-and-bananas" / "Apples,
    Pears and Bananas" -> "applespearsandbananas")."""
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    text = text.lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", text)


def _category_path_keys(path):
    """'/categories/fruit/apples-pears-and-bananas/2' -> 'fruit/applespearsandbananas'
    (parent key / leaf key; a trailing page number is dropped)."""
    segments = [unquote(s) for s in path.split("/categories/", 1)[1].split("/") if s]
    if segments and segments[-1].isdigit() and len(segments) > 1:
        segments = segments[:-1]
    keys = [category_key(s) for s in segments if category_key(s)]
    if not keys:
        raise ValueError("Must be an igashop.com.au category link "
                         "(https://www.igashop.com.au/categories/<department>/<category>).")
    return "/".join(keys[-2:])


def resolve_category(value):
    """Identifier / slug / display name / category link -> lookup key
    (api._category_for matches it against the cached tree): the folded
    leaf key, prefixed by the folded parent key when a link or a
    "parent/child" path names one ("fruit/applespearsandbananas"), so a
    name shared by two parents (meat/beef vs frozen-meat/beef) resolves to
    the right node."""
    value = (value or "").strip()
    if not value:
        raise ValueError("Must not be empty.")
    if _is_link(value):
        url = _site_url(value, "category")
        path = urlparse(url).path
        if "/categories/" not in path:
            raise ValueError("Must be an igashop.com.au category link "
                             "(https://www.igashop.com.au/categories/<department>/<category>).")
        return _category_path_keys(path)
    if not CATEGORY_KEY_RE.match(value):
        raise ValueError("Must be a category identifier (Apples_Pears_and_Bananas), its slug "
                         "(apples-pears-and-bananas), its name, or an igashop.com.au category link.")
    if "/" in value:
        return _category_path_keys("/categories/" + value.strip("/"))
    if not category_key(value):
        raise ValueError("Must be a category identifier (Apples_Pears_and_Bananas), its slug "
                         "(apples-pears-and-bananas), its name, or an igashop.com.au category link.")
    return category_key(value)


# ---- recipe --------------------------------------------------------------------

def resolve_recipe(value):
    """Bare recipe id or a recipe link -> the id."""
    value = (value or "").strip()
    if _is_link(value):
        url = _site_url(value, "recipe")
        match = _RECIPE_PATH_RE.search(urlparse(url).path)
        if match:
            return match.group(1)
        raise ValueError("Must be an igashop.com.au recipe link "
                         "(https://www.igashop.com.au/recipe/<id>).")
    if RECIPE_ID_RE.match(value):
        return value
    raise ValueError("Must be a recipe id (a UUID or a short numeric id) or an "
                     "igashop.com.au recipe link.")


def recipe_link(recipe_id):
    return f"{SITE}/recipe/{recipe_id}"


# ---- listing pages ---------------------------------------------------------------

def search_link(query, page=1):
    from urllib.parse import quote
    return f"{SITE}/search/{page}?q={quote(query)}" if page > 1 else f"{SITE}/search?q={quote(query)}"


def specials_link(page=1):
    return f"{SITE}/specials/{page}" if page > 1 else f"{SITE}/specials"
