"""Offline tests for the IGA Shop parsers, reference resolvers and value
helpers.

    python -m pytest iga_shop/test_parsers.py -q

Fixtures are real www.igashop.com.au storefront payloads captured
2026-10-28 (iga_shop/fixtures/, store 32600 unless named otherwise). No
network.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iga_shop import parsers as P, refs  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f) if name.endswith(".json") else f.read()


@pytest.fixture(scope="module")
def tree():
    return P.parse_category_tree(fixture("category_hierarchy.json"))


@pytest.fixture(scope="module")
def flat(tree):
    return P.flatten_categories(tree)


# ---- refs -------------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("494526", "494526"),
    (" 1800000080658 ", "1800000080658"),
    ("https://www.igashop.com.au/product/arnotts-tim-tam-chocolate-original-308953", "308953"),
    ("igashop.com.au/product/-196-double-lemon-190000007880?x=1", "190000007880"),
    ("/product/a2-milk-full-cream-milk-726347", "726347"),
])
def test_resolve_product(value, expected):
    assert refs.resolve_product(value) == expected


@pytest.mark.parametrize("value", ["", "milk", "12", "https://example.com/product/x-123456",
                                   "https://www.igashop.com.au/categories/fruit"])
def test_resolve_product_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_product(value)


@pytest.mark.parametrize("value,expected", [
    ("32600", "32600"),
    ("3065", "3065"),
    (" Fitzroy ", "Fitzroy"),
    ("IGA Local Grocer Fitzroy", "IGA Local Grocer Fitzroy"),
    ("https://www.igashop.com.au/store/iga-local-grocer-fitzroy", "iga-local-grocer-fitzroy"),
])
def test_resolve_store(value, expected):
    assert refs.resolve_store(value) == expected


@pytest.mark.parametrize("value", ["", "https://example.com/store/x", "https://www.igashop.com.au/product/x-123456"])
def test_resolve_store_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_store(value)


@pytest.mark.parametrize("value,expected", [
    ("Apples_Pears_and_Bananas", "applespearsandbananas"),
    ("apples-pears-and-bananas", "applespearsandbananas"),
    ("Apples, Pears and Bananas", "applespearsandbananas"),
    ("grocery", "grocery"),
    ("fruit/apples-pears-and-bananas", "fruit/applespearsandbananas"),
    ("https://www.igashop.com.au/categories/fruit/apples-pears-and-bananas", "fruit/applespearsandbananas"),
    ("https://www.igashop.com.au/categories/baby/12-months/1", "baby/12months"),
    ("https://www.igashop.com.au/categories/fruit-and-vegetable", "fruitandvegetable"),
])
def test_resolve_category(value, expected):
    assert refs.resolve_category(value) == expected


@pytest.mark.parametrize("value", ["", "https://www.igashop.com.au/product/x-123456", "https://example.com/categories/fruit"])
def test_resolve_category_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_category(value)


@pytest.mark.parametrize("value,expected", [
    ("071026", "071026"),
    ("5f7c6f29-6e77-4b82-92bc-5a0ad46f0a5c", "5f7c6f29-6e77-4b82-92bc-5a0ad46f0a5c"),
    ("https://www.igashop.com.au/recipe/5f7c6f29-6e77-4b82-92bc-5a0ad46f0a5c", "5f7c6f29-6e77-4b82-92bc-5a0ad46f0a5c"),
    ("https://www.igashop.com.au/recipe/071026", "071026"),
])
def test_resolve_recipe(value, expected):
    assert refs.resolve_recipe(value) == expected


@pytest.mark.parametrize("value", ["", "pavlova!", "https://www.igashop.com.au/recipes/Dinner"])
def test_resolve_recipe_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_recipe(value)


def test_links():
    assert refs.product_link("308953", "Arnott's Tim Tam Chocolate Original") == \
        "https://www.igashop.com.au/product/arnotts-tim-tam-chocolate-original-308953"
    assert refs.store_link("IGA Local Grocer Fitzroy") == "https://www.igashop.com.au/store/iga-local-grocer-fitzroy"
    assert refs.category_link("Apples_Pears_and_Bananas", "Fruit") == \
        "https://www.igashop.com.au/categories/fruit/apples-pears-and-bananas"
    assert refs.category_link("Fruit_and_Vegetable") == "https://www.igashop.com.au/categories/fruit-and-vegetable"
    assert refs.recipe_link("071026") == "https://www.igashop.com.au/recipe/071026"
    assert refs.search_link("tim tam") == "https://www.igashop.com.au/search?q=tim%20tam"
    assert refs.search_link("tim tam", 2) == "https://www.igashop.com.au/search/2?q=tim%20tam"
    assert refs.specials_link(1) == "https://www.igashop.com.au/specials"
    assert refs.specials_link(3) == "https://www.igashop.com.au/specials/3"


# ---- value helpers --------------------------------------------------------------------------

def test_value_helpers():
    assert P.to_float("$4.50") == 4.5
    assert P.to_float("1,234.5") == 1234.5
    assert P.to_float(None) is None and P.to_float(True) is None
    assert P.to_int("12") == 12 and P.to_int(3.0) == 3 and P.to_int("x") is None
    assert P.iso_date("28/10/2026") == "2026-10-28"
    assert P.iso_date("2026-10-20T13:00:00Z") == "2026-10-20T13:00:00Z"
    assert P.iso_date("") is None
    assert P.unit_price("$3.50/l") == {"amount": 3.5, "per": "l", "is_average": False, "text": "$3.50/l"}
    assert P.unit_price("$1.06 avg/ea") == {"amount": 1.06, "per": "ea", "is_average": True, "text": "$1.06 avg/ea"}
    assert P.unit_price("$2.25/100g")["per"] == "100g"
    assert P.unit_price(None) is None
    assert P.html_to_text("<p>One&nbsp;two</p><p>Three<br>Four</p>") == "One two\nThree\nFour"
    assert P.html_to_steps("<ol><li>Cut.</li><li>Whip <b>cream</b>.</li></ol>") == ["Cut.", "Whip cream."]
    assert P.html_to_steps("line one<br>line two") == ["line one", "line two"]


def test_parse_description_trailers():
    out = P.parse_description("<p>Nice biscuits.</p><p>Country of Origin: Made in Australia</p>"
                              "<p>Allergen may be present: Gluten| Milk</p><p>Contains: Soy</p>")
    assert out == {"text": "Nice biscuits.", "country_of_origin": "Made in Australia",
                   "allergens_may_be_present": "Gluten| Milk", "contains": "Soy"}
    assert P.parse_description(None) == {"text": None, "country_of_origin": None,
                                         "allergens_may_be_present": None, "contains": None}


# ---- stores ------------------------------------------------------------------------------------

def test_parse_stores_fitzroy():
    out = P.parse_stores(fixture("stores_search_fitzroy.json"), 1, 20)
    assert out["pagination"] == {"page": 1, "items_per_page": 20, "total_pages": 1, "total_count": 3}
    store = out["results"][0]
    assert store["number"] == "41524"
    assert store["name"] == "IGA Local Grocer Fitzroy"
    assert store["slug"] == "iga-local-grocer-fitzroy"
    assert store["link"] == "https://www.igashop.com.au/store/iga-local-grocer-fitzroy"
    assert store["address"] == {"line1": "424 - 428 Brunswick Street", "line2": None, "line3": None,
                                "suburb": "Fitzroy", "state": "VIC", "postcode": "3065", "country": "Australia"}
    assert store["phone"] == "(03) 9419 5288"
    assert store["location"] == {"latitude": -37.79425, "longitude": 144.97949}
    assert store["has_delivery"] is True and store["has_pickup"] is True and store["is_active"] is True
    assert store["timezone"] == "Australia/Melbourne"
    assert store["opening_hours"]["text"].startswith("Monday to Thursday")
    assert "metadata" not in store and "_links" not in store


def test_parse_stores_postcode_and_number():
    by_postcode = P.parse_stores(fixture("stores_search_3065.json"))
    assert by_postcode["results"] and all(s["address"]["postcode"] == "3065" for s in by_postcode["results"])
    by_number = P.parse_stores(fixture("stores_search_by_number.json"))
    assert by_number["results"][0]["number"] == "32600"
    assert by_number["results"][0]["name"] == "Ashcroft's IGA Erskine Park"


def test_parse_stores_all_and_match():
    stores = P.parse_stores(fixture("stores_all.json"))["results"]
    assert len(stores) >= 500
    assert all(s["number"] and s["name"] for s in stores)
    assert P.match_store(stores, "32600")["name"] == "Ashcroft's IGA Erskine Park"
    assert P.match_store(stores, "3065")["address"]["postcode"] == "3065"
    assert P.match_store(stores, "fitzroy")["name"] == "IGA Local Grocer Fitzroy"
    assert P.match_store(stores, "iga-local-grocer-fitzroy")["number"] == "41524"
    assert P.match_store(stores, "IGA Local Grocer Fitzroy")["number"] == "41524"
    assert P.match_store(stores, "nowhere-ville-xyz") is None
    assert P.match_store(stores, "") is None


def test_parse_nearby_melbourne():
    out = P.parse_nearby(fixture("stores_nearby_melbourne.json"), -37.8, 144.98)
    assert len(out) == 5
    assert out[0]["name"] == "IGA Local Grocer Fitzroy"
    assert out[0]["distance_km"] == pytest.approx(0.64, abs=0.01)
    assert [s["distance_km"] for s in out] == sorted(s["distance_km"] for s in out)


def test_haversine():
    assert P.haversine_km(0, 0, 0, 0) == 0
    assert P.haversine_km(-37.8, 144.98, -33.87, 151.21) == pytest.approx(713.5, abs=5)
    assert P.haversine_km(None, 1, 2, 3) is None


# ---- listings ------------------------------------------------------------------------------------

def test_parse_listing_search_milk():
    out = P.parse_listing(fixture("search_milk.json"), 1, 20)
    assert out["pagination"] == {"page": 1, "items_per_page": 20, "total_pages": 108, "total_count": 2154}
    assert len(out["results"]) == 20
    item = out["results"][0]
    assert item["sku"] == "726347"
    assert item["name"] == "A2 Milk Full Cream Milk"
    assert item["brand"] == "A2 Milk"
    assert item["link"] == "https://www.igashop.com.au/product/a2-milk-full-cream-milk-726347"
    assert item["image"].startswith("https://cdn.metcash.media/")
    assert item["size"] == {"value": 3.0, "unit": "l", "label": "Litre"}
    assert item["is_available"] is True
    assert item["pricing"]["price"] == 10.5
    assert item["pricing"]["currency"] == "AUD"
    assert item["pricing"]["is_on_special"] is False
    assert item["pricing"]["unit_price"]["amount"] == 3.5
    assert item["pricing"]["sold_by"] == "each"
    assert item["category"]["id"] and item["categories"]
    assert all(c["id"] != "Grocery" for c in item["categories"])
    assert item["category"]["link"] is None or item["category"]["link"].startswith("https://www.igashop.com.au/categories/") \
        if "link" in item["category"] else True
    assert out["facets"]["brands"][0] == {"name": "Cadbury", "count": 137}
    assert out["facets"]["categories"]
    assert out["suggestions"] is None
    for key in ("metadata", "_links", "isFavorite", "siteId"):
        assert key not in item


def test_parse_listing_misspelled_and_empty():
    out = P.parse_listing(fixture("search_misspelled.json"), 1, 20)
    assert out["suggestions"]["was_corrected"] is True
    assert out["suggestions"]["original_query"] and out["suggestions"]["performed_query"]
    assert out["suggestions"]["original_query"] != out["suggestions"]["performed_query"]
    empty = P.parse_listing(fixture("search_no_results.json"), 1, 20)
    assert empty["results"] == []
    assert empty["pagination"]["total_count"] == 0
    assert empty["pagination"]["total_pages"] == 1


def test_parse_listing_specials():
    out = P.parse_listing(fixture("specials_page1.json"), 1, 20)
    assert out["pagination"]["total_count"] > 100
    assert out["results"]
    for item in out["results"]:
        pricing = item["pricing"]
        assert pricing["is_on_special"] is True
        assert pricing["price"] is not None
        assert pricing["special"] and pricing["special"]["price"] == pricing["price"]
        assert pricing["special"]["starts_at"] and pricing["special"]["ends_at"]
        if pricing["was_price"]:
            assert pricing["saving"] == pytest.approx(pricing["was_price"] - pricing["price"], abs=0.01)
            assert 0 < pricing["saving_percent"] < 100


def test_parse_listing_category_and_unknown():
    out = P.parse_listing(fixture("category_fruit_search.json"), 1, 20)
    assert out["pagination"]["total_count"] > 0
    assert all(any(c["id"] == "Fruit" for c in i["categories"]) for i in out["results"])
    unknown = P.parse_listing(fixture("category_unknown_search.json"), 1, 20)
    assert unknown["results"] == [] and unknown["pagination"]["total_count"] == 0


def test_parse_listing_item_garbage():
    assert P.parse_listing_item(None) is None
    assert P.parse_listing({}, 1, 20)["results"] == []


# ---- product record -----------------------------------------------------------------------------

def test_parse_product_on_special():
    out = P.parse_product(fixture("product_308953_on_special.json"), "308953", "32600")
    assert out["sku"] == "308953"
    assert out["name"] == "Arnott's Tim Tam Chocolate Original"
    assert out["brand"] == "Arnott's"
    assert out["link"] == "https://www.igashop.com.au/product/arnotts-tim-tam-chocolate-original-308953"
    assert len(out["images"]) == 3 and out["image"] == out["images"][0]
    assert out["size"] == {"value": 200.0, "unit": "g", "label": "Gram"}
    pricing = out["pricing"]
    assert pricing["price"] == 4.5 and pricing["was_price"] == 6.0
    assert pricing["saving"] == 1.5 and pricing["saving_percent"] == 25
    assert pricing["is_on_special"] is True
    assert pricing["special"] == {"label": "25% Off", "price": 4.5, "starts_at": "2026-10-28",
                                  "ends_at": "2026-11-04", "is_active": True}
    assert pricing["unit_price"]["text"] == "$2.25/100g"
    assert out["country_of_origin"] == "Made in Australia"
    assert out["allergens_may_be_present"] == "Gluten| Milk| Soy| Wheat"
    assert "Country of Origin" not in out["description"]
    assert out["ingredients"].startswith("Milk Chocolate (38%)")
    panels = out["nutrition"]["panels"]
    assert panels and panels[0]["basis"] == "Per 100g / Per 100mL"
    energy = next(n for n in panels[0]["nutrients"] if n["name"] == "Energy")
    assert energy == {"name": "Energy", "value": 2190.0, "unit": "kJ", "daily_value_percent": None, "is_trace": False}
    assert out["category"]["name"] and out["categories"]
    assert out["store"] == {"number": "32600"}
    for key in ("metadata", "_links", "isFavorite", "taxDetails"):
        assert key not in out


def test_parse_product_regular():
    out = P.parse_product(fixture("product_494526.json"), "494526", "32600")
    assert out["sku"] == "494526"
    assert out["pricing"]["price"] > 0
    assert out["pricing"]["was_price"] is None
    assert out["pricing"]["is_on_special"] is False
    assert out["pricing"]["special"] is None
    assert out["is_available"] is True
    assert out["link"].endswith("-494526")


def test_parse_product_not_found_body():
    payload = fixture("product_not_found.json")
    assert "not found" in P.clean(payload.get("data") if isinstance(payload.get("data"), str) else "") .lower() \
        or payload.get("statusCode") == 404


# ---- categories ---------------------------------------------------------------------------------

def test_parse_category_tree(tree, flat):
    assert len(tree) >= 10
    assert all(n["depth"] == 1 and n["link"].startswith("https://www.igashop.com.au/categories/") for n in tree)
    fruit_veg = next(n for n in tree if n["id"] == "Fruit_and_Vegetable")
    assert fruit_veg["name"] == "Fruit and Vegetable"
    assert fruit_veg["slug"] == "fruit-and-vegetable"
    assert fruit_veg["children_count"] == len(fruit_veg["children"]) > 0
    fruit = next(n for n in fruit_veg["children"] if n["id"] == "Fruit")
    assert fruit["link"] == "https://www.igashop.com.au/categories/fruit-and-vegetable/fruit"
    apples = next(n for n in fruit["children"] if n["id"] == "Apples_Pears_and_Bananas")
    assert apples["link"] == "https://www.igashop.com.au/categories/fruit/apples-pears-and-bananas"
    assert apples["depth"] == 3
    assert flat[0]["id"] == "Grocery" and flat[0]["depth"] == 0
    assert len(flat) > 400
    assert all("children" not in row for row in flat)
    assert all(n["id"] != "Grocery" for n in tree)


def test_find_category(flat):
    assert P.find_category(flat, "applespearsandbananas")["id"] == "Apples_Pears_and_Bananas"
    assert P.find_category(flat, "fruit/applespearsandbananas")["parent_id"] == "Fruit"
    assert P.find_category(flat, "fruitandvegetable")["id"] == "Fruit_and_Vegetable"
    assert P.find_category(flat, "grocery")["id"] == "Grocery"
    # a parent that does not own the leaf still resolves to the leaf
    assert P.find_category(flat, "nonsense/applespearsandbananas")["id"] == "Apples_Pears_and_Bananas"
    assert P.find_category(flat, "nosuchcategory") is None
    assert P.find_category(flat, "") is None


@pytest.mark.parametrize("name,expected", [
    ("12+ Months", "12_Months"),                   # "+" in the display name
    ("Nappies 18 Months (10+kgs)", "Nappies_18_Months"),
    ("Rosé", "Rose_Food"),                          # accented display name
    ("Soju / Shochu", "Soju_and_Shochu"),           # a slash that is not a parent/leaf path
])
def test_display_names_from_the_tree_resolve(flat, name, expected):
    assert P.find_category(flat, refs.resolve_category(name))["id"] == expected


def test_pagination_window_cap():
    assert P.pagination(1, 20, 2154, window=10000)["total_pages"] == 108
    assert P.pagination(1, 20, 30000, window=10000)["total_pages"] == 500
    assert P.pagination(1, 30, 30000, window=10000)["total_pages"] == 334
    assert P.pagination(1, 100, 30000, window=10000)["total_pages"] == 100
    assert P.pagination(1, 100, 30000)["total_pages"] == 300
    assert P.parse_listing({"items": [], "total": 30000}, 1, 20)["pagination"]["total_pages"] == 500


def test_category_overview_of_grocery_links_departments_flat():
    out = P.parse_category_overview({"retailerCategoryId": "Grocery", "title": "Grocery", "total": 1,
                                     "subCategories": {"Fruit and Vegetable": {
                                         "retailerCategoryId": "Fruit_and_Vegetable", "total": 1, "items": []}}})
    assert out["subcategories"][0]["link"] == "https://www.igashop.com.au/categories/fruit-and-vegetable"


def test_category_sitemap_links_resolve_against_tree(flat):
    """Every category link in the category sitemap resolves to a node of
    this store's tree except those the store does not range."""
    links = [u["link"] for u in P.parse_sitemap_urls(fixture("category_sitemap.xml"))]
    assert len(links) > 400
    unmatched = [u for u in links if P.find_category(flat, refs.resolve_category(u)) is None]
    assert len(unmatched) < 20, unmatched


def test_parse_category_overview():
    out = P.parse_category_overview(fixture("category_fruit_subcategories.json"))
    assert out["id"] == "Fruit" and out["name"] == "Fruit"
    assert out["total_count"] > 0
    assert out["subcategories_count"] == len(out["subcategories"]) > 3
    block = out["subcategories"][0]
    assert block["id"] == "Apples_Pears_and_Bananas"
    assert block["link"] == "https://www.igashop.com.au/categories/fruit/apples-pears-and-bananas"
    assert block["total_count"] >= len(block["products"]) > 0
    assert block["products"][0]["sku"] and block["products"][0]["pricing"]["price"]


# ---- recipes --------------------------------------------------------------------------------------

def test_parse_recipes_search():
    out = P.parse_recipes(fixture("recipes_search_chicken.json"), 1, 20)
    assert out["pagination"] == {"page": 1, "items_per_page": 20, "total_pages": 4, "total_count": 74}
    assert len(out["results"]) == 20
    card = out["results"][0]
    assert card["id"] == "071026"
    assert card["link"] == "https://www.igashop.com.au/recipe/071026"
    assert card["name"] and card["short_description"] and card["image"]
    assert isinstance(card["prep_time_minutes"], int)
    assert {"name": "Dinner", "count": 67} in out["categories"]
    none = P.parse_recipes(fixture("recipes_none.json"), 1, 20)
    assert none["results"] == [] and none["pagination"]["total_count"] == 0


def test_parse_recipe_pavlova():
    out = P.parse_recipe(fixture("recipe_pavlova.json"))
    assert out["id"] == "5f7c6f29-6e77-4b82-92bc-5a0ad46f0a5c"
    assert out["name"] == "Mini Aussie Day Pavlovas"
    assert out["link"] == "https://www.igashop.com.au/recipe/5f7c6f29-6e77-4b82-92bc-5a0ad46f0a5c"
    assert len(out["directions"]) == 4 and out["directions"][0].startswith("Cut the flesh")
    assert all("<" not in d for d in out["directions"])
    assert out["ingredients_count"] == 4
    assert out["ingredients"][0]["products"][0]["sku"]
    assert out["categories"] == ["Desserts", "Entertaining"]
    assert out["prep_time_minutes"] == 10 and out["cook_time_minutes"] == 0 and out["total_time_minutes"] == 10
    assert out["servings"] == 12
    assert out["images"]["gallery"] and out["images"]["featured"]
    assert out["is_active"] is True
    assert "metadata" not in out and "_links" not in out


def test_parse_recipe_not_found_body():
    payload = fixture("recipe_not_found.json")
    assert payload.get("statusCode") == 404 or "not found" in json.dumps(payload).lower()


# ---- sitemaps --------------------------------------------------------------------------------------

def test_parse_sitemap_index():
    out = P.parse_sitemap_index(fixture("sitemap_index.xml"))
    assert out == ["https://www.igashop.com.au/sitemap.xml", "https://www.igashop.com.au/product-sitemap.xml",
                   "https://www.igashop.com.au/category-sitemap.xml", "https://www.igashop.com.au/recipe-sitemap.xml"]


def test_parse_product_sitemap():
    out = P.parse_product_sitemap(fixture("product_sitemap_head.xml"))
    assert len(out) == 60
    assert out[0] == {"sku": "1800000080658", "slug": "happy-donut-company-donut-caramel-flavoured-iced",
                      "name": "happy donut company donut caramel flavoured iced",
                      "link": "https://www.igashop.com.au/product/happy-donut-company-donut-caramel-flavoured-iced-1800000080658"}
    assert all(r["sku"] and r["sku"].isdigit() for r in out)
    assert all(refs.resolve_product(r["link"]) == r["sku"] for r in out)


def test_parse_sitemap_urls_and_merge():
    cats = P.parse_sitemap_urls(fixture("category_sitemap.xml"))
    main = P.parse_sitemap_urls(fixture("sitemap.xml"))
    assert len(cats) > 400
    assert cats[0]["link"] == "https://www.igashop.com.au/categories/fruit-and-vegetable"
    assert cats[0] == {"link": cats[0]["link"], "last_modified": None, "change_frequency": None, "priority": 0.7}
    assert main[0]["last_modified"] and main[0]["change_frequency"] == "daily"
    recipes = P.parse_sitemap_urls(fixture("recipe_sitemap.xml"))
    assert all(r["link"].startswith("https://www.igashop.com.au/recipe") for r in recipes)
    assert sum(r["link"].startswith("https://www.igashop.com.au/recipe/") for r in recipes) > 400
    merged = P.merge_sitemap_links([("category-sitemap.xml", cats), ("recipe-sitemap.xml", recipes),
                                    ("sitemap.xml", main)])
    links = [m["link"] for m in merged]
    assert len(links) == len(set(links))
    assert not any(l.endswith("/1") for l in links)
    types = {m["type"] for m in merged}
    assert {"category", "recipe", "recipes_list", "specials", "page", "home"} <= types
    assert next(m for m in merged if m["type"] == "home")["link"] == "https://www.igashop.com.au"
    assert all(m["sitemap"] in ("category-sitemap.xml", "recipe-sitemap.xml", "sitemap.xml") for m in merged)
    for kind, classes in P.LINK_TYPE_CLASSES.items():
        assert classes is None or set(classes) <= types


@pytest.mark.parametrize("link,expected", [
    ("https://www.igashop.com.au", "home"),
    ("https://www.igashop.com.au/", "home"),
    ("https://www.igashop.com.au/categories/fruit/apples", "category"),
    ("https://www.igashop.com.au/recipe/071026", "recipe"),
    ("https://www.igashop.com.au/recipes/Dinner/2", "recipes_list"),
    ("https://www.igashop.com.au/recipe", "recipes_list"),
    ("https://www.igashop.com.au/specials/3", "specials"),
    ("https://www.igashop.com.au/about-us", "page"),
])
def test_classify_link(link, expected):
    assert P.classify_link(link) == expected
