"""Offline tests for the /iga-shop/* request schemas.

    python -m pytest iga_shop/test_schemas.py -q
"""
import os
import sys

import pytest
from marshmallow import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from iga_shop import schemas  # noqa: E402

DEFAULT_STORE = config.IGA_SHOP_DEFAULT_STORE


def test_stores_search_schema():
    assert schemas.StoresSearchSchema().load({}) == {"query": None, "page": 1, "limit": 20}
    assert schemas.StoresSearchSchema().load({"query": " fitzroy ", "page": "2", "limit": "50"}) == \
        {"query": "fitzroy", "page": 2, "limit": 50}
    with pytest.raises(ValidationError):
        schemas.StoresSearchSchema().load({"limit": "101"})
    with pytest.raises(ValidationError):
        schemas.StoresSearchSchema().load({"page": "0"})
    with pytest.raises(ValidationError):
        schemas.StoresSearchSchema().load({"query": "x" * 81})


def test_stores_nearby_schema():
    loaded = schemas.StoresNearbySchema().load({"latitude": "-37.8", "longitude": "144.98"})
    assert loaded == {"latitude": -37.8, "longitude": 144.98, "radius_km": 100, "limit": 10}
    assert schemas.StoresNearbySchema().load(
        {"latitude": "-37.8", "longitude": "144.98", "radius_km": "25", "limit": "3"})["radius_km"] == 25
    with pytest.raises(ValidationError):
        schemas.StoresNearbySchema().load({"latitude": "-37.8"})
    with pytest.raises(ValidationError):
        schemas.StoresNearbySchema().load({"latitude": "91", "longitude": "0"})
    with pytest.raises(ValidationError):
        schemas.StoresNearbySchema().load({"latitude": "0", "longitude": "0", "limit": "51"})


def test_store_schema_accepts_every_form():
    load = schemas.StoreSchema().load
    assert load({"store": "32600"}) == {"store": "32600"}
    assert load({"store": "3065"}) == {"store": "3065"}
    assert load({"store": " Fitzroy "}) == {"store": "Fitzroy"}
    assert load({"store": "https://www.igashop.com.au/store/iga-local-grocer-fitzroy"}) == \
        {"store": "iga-local-grocer-fitzroy"}
    with pytest.raises(ValidationError):
        load({})
    with pytest.raises(ValidationError):
        load({"store": "https://example.com/store/x"})
    with pytest.raises(ValidationError):
        load({"store": "32600", "store_id": "32600"})


def test_products_search_schema():
    loaded = schemas.ProductsSearchSchema().load({"query": " milk "})
    assert loaded == {"query": "milk", "store": DEFAULT_STORE, "page": 1, "limit": 20,
                      "sort": "relevance", "brand": None, "category": None}
    loaded = schemas.ProductsSearchSchema().load(
        {"query": "milk", "store": "fitzroy", "sort": "price_asc", "brand": "Pauls",
         "category": "Full Cream", "page": "3", "limit": "100"})
    assert loaded["sort"] == "price" and loaded["store"] == "fitzroy"
    assert loaded["brand"] == "Pauls" and loaded["category"] == "Full Cream"
    assert loaded["page"] == 3 and loaded["limit"] == 100
    with pytest.raises(ValidationError):
        schemas.ProductsSearchSchema().load({})
    with pytest.raises(ValidationError):
        schemas.ProductsSearchSchema().load({"query": "milk", "sort": "cheapest"})
    with pytest.raises(ValidationError):
        schemas.ProductsSearchSchema().load({"query": "milk", "limit": "101"})
    with pytest.raises(ValidationError):
        schemas.ProductsSearchSchema().load({"query": "x" * 51})


def test_paged_window():
    assert schemas.ProductsSearchSchema().load({"query": "milk", "page": "100", "limit": "100"})["page"] == 100
    with pytest.raises(ValidationError):
        schemas.ProductsSearchSchema().load({"query": "milk", "page": "101", "limit": "100"})
    with pytest.raises(ValidationError):
        schemas.SpecialsSchema().load({"page": "501", "limit": "20"})


def test_product_schema():
    load = schemas.ProductSchema().load
    assert load({"product": "494526"}) == {"product": "494526", "store": DEFAULT_STORE}
    assert load({"product": "https://www.igashop.com.au/product/arnotts-tim-tam-chocolate-original-308953",
                 "store": "41524"}) == {"product": "308953", "store": "41524"}
    with pytest.raises(ValidationError):
        load({})
    with pytest.raises(ValidationError):
        load({"product": "tim tam"})
    with pytest.raises(ValidationError):
        load({"product": "494526", "sku": "494526"})


def test_specials_schema():
    assert schemas.SpecialsSchema().load({}) == {"store": DEFAULT_STORE, "page": 1, "limit": 20,
                                                 "sort": "relevance", "brand": None, "category": None}
    assert schemas.SpecialsSchema().load({"sort": "brand_desc"})["sort"] == "brand desc"


def test_categories_schema():
    assert schemas.CategoriesSchema().load({}) == {"store": DEFAULT_STORE}
    assert schemas.CategoriesSchema().load({"store": "3065"}) == {"store": "3065"}


def test_category_products_schema():
    load = schemas.CategoryProductsSchema().load
    loaded = load({"category": "Apples_Pears_and_Bananas"})
    assert loaded == {"category": "applespearsandbananas", "store": DEFAULT_STORE, "page": 1, "limit": 20,
                      "sort": "relevance", "brand": None}
    assert load({"category": "https://www.igashop.com.au/categories/fruit/apples-pears-and-bananas"})["category"] == \
        "fruit/applespearsandbananas"
    assert load({"category": "grocery", "sort": "price_desc", "brand": "Pauls"})["sort"] == "price desc"
    with pytest.raises(ValidationError):
        load({})
    with pytest.raises(ValidationError):
        load({"category": "https://www.igashop.com.au/product/x-123456"})
    with pytest.raises(ValidationError):
        load({"category": "fruit", "category_id": "fruit"})


def test_category_overview_schema():
    load = schemas.CategoryOverviewSchema().load
    assert load({"category": "fruit"}) == {"category": "fruit", "store": DEFAULT_STORE, "limit": 6}
    assert load({"category": "fruit", "limit": "100"})["limit"] == 100
    with pytest.raises(ValidationError):
        load({"category": "fruit", "limit": "101"})


def test_recipes_search_schema():
    load = schemas.RecipesSearchSchema().load
    assert load({}) == {"query": None, "category": None, "store": DEFAULT_STORE, "page": 1, "limit": 20}
    assert load({"query": " chicken ", "category": "Dinner"})["query"] == "chicken"
    with pytest.raises(ValidationError):
        load({"category": "x" * 61})
    # an empty optional string is None, not a len(None) TypeError (a 500)
    assert load({"category": ""})["category"] is None
    assert load({"query": "  "})["query"] is None
    assert schemas.StoresSearchSchema().load({"query": ""})["query"] is None
    assert schemas.ProductsSearchSchema().load({"query": "milk", "brand": "", "category": " "})["brand"] is None
    assert schemas.SpecialsSchema().load({"brand": ""})["category"] is None
    with pytest.raises(ValidationError):
        schemas.ProductsSearchSchema().load({"query": "milk", "brand": "x" * 81})


def test_recipe_schema():
    load = schemas.RecipeSchema().load
    assert load({"recipe": "071026"}) == {"recipe": "071026", "store": DEFAULT_STORE}
    assert load({"recipe": "https://www.igashop.com.au/recipe/5f7c6f29-6e77-4b82-92bc-5a0ad46f0a5c"})["recipe"] == \
        "5f7c6f29-6e77-4b82-92bc-5a0ad46f0a5c"
    with pytest.raises(ValidationError):
        load({})
    with pytest.raises(ValidationError):
        load({"recipe": "https://www.igashop.com.au/recipes/Dinner"})


def test_sitemap_schemas():
    assert schemas.SitemapProductsSchema().load({}) == {"page": 1, "limit": 100}
    assert schemas.SitemapProductsSchema().load({"page": "7", "limit": "1000"}) == {"page": 7, "limit": 1000}
    with pytest.raises(ValidationError):
        schemas.SitemapProductsSchema().load({"limit": "1001"})
    assert schemas.SitemapLinksSchema().load({}) == {"type": "all", "page": 1, "limit": 100}
    assert schemas.SitemapLinksSchema().load({"type": "categories"})["type"] == "categories"
    with pytest.raises(ValidationError):
        schemas.SitemapLinksSchema().load({"type": "products"})
    with pytest.raises(ValidationError):
        schemas.SitemapLinksSchema().load({"type": "all", "extra": "1"})
