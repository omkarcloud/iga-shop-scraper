"""Marshmallow request schemas for every /iga-shop/* route.

ONE param per input (tripadvisor QueryOrIdField convention, never a sibling
`url` / `id` pair), resolved by iga_shop/refs.py:

    product    a SKU (494526) OR a product link
    store      a store number (32600), a postcode (3065), a suburb or store
               name (fitzroy) OR a store link; defaults to the site's own
               anonymous store (config.IGA_SHOP_DEFAULT_STORE)
    category   a category identifier (Apples_Pears_and_Bananas), its slug,
               its name OR a category link; "grocery" is the whole catalogue
    recipe     a recipe id OR a recipe link

Listing pages take `page` + `limit` (the storefront's take <= 100 and a
10,000-row window: page * limit must stay inside it).
"""
from marshmallow import ValidationError, fields, validate, validates_schema

import config
from schema_fields import BaseSchema, ChoiceField, LimitField, PageField, QueryField, RefField, StrippedString
from iga_shop import refs

MAX_LIMIT = config.IGA_SHOP_MAX_TAKE          # 100
MAX_PAGE = config.IGA_SHOP_MAX_SKIP // 10     # 1000 pages of 10; checked against limit below
DEFAULT_LIMIT = 20


def _max_length(n):
    """validate.Length(max=n) that tolerates the None StrippedString returns
    for an empty value (marshmallow runs validators on it; len(None) is a 500)."""
    def check(value):
        if value is not None and len(value) > n:
            raise ValidationError(f"Longer than maximum length {n}.")
    return check


class ProductRefField(RefField):
    resolver = staticmethod(refs.resolve_product)


class StoreRefField(RefField):
    resolver = staticmethod(refs.resolve_store)

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        if not kwargs["required"]:
            kwargs.setdefault("load_default", config.IGA_SHOP_DEFAULT_STORE)
        kwargs.setdefault("metadata", {
            "description": "store number (32600), postcode (3065), suburb or store name "
                           "(fitzroy), or an igashop.com.au store link; prices and specials "
                           f"are per store; default {config.IGA_SHOP_DEFAULT_STORE} "
                           "(Ashcroft's IGA Erskine Park NSW, the site's own anonymous store)"})
        super().__init__(**kwargs)


class CategoryRefField(RefField):
    resolver = staticmethod(refs.resolve_category)


class RecipeRefField(RefField):
    resolver = staticmethod(refs.resolve_recipe)


class SortField(ChoiceField):
    def __init__(self, **kwargs):
        kwargs.setdefault("load_default", "relevance")
        kwargs.setdefault("metadata", {
            "description": "relevance (default), price_asc, price_desc, brand_asc, brand_desc"})
        super().__init__(refs.SORTS, **kwargs)


class BrandFilterField(StrippedString):
    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        kwargs.setdefault("validate", _max_length(80))
        kwargs.setdefault("metadata", {
            "description": "only this brand, as the site spells it (Pauls, Arnott's); the "
                           "response's facets.brands lists the brands of the result set"})
        super().__init__(**kwargs)


class CategoryFilterField(StrippedString):
    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        kwargs.setdefault("validate", _max_length(120))
        kwargs.setdefault("metadata", {
            "description": "only this category, by display name (Full Cream, Chocolate Bars); "
                           "the response's facets.categories lists what the result set spans"})
        super().__init__(**kwargs)


class _Paged(BaseSchema):
    page = PageField(max_page=MAX_PAGE, metadata={"description": "1-based page"})
    limit = LimitField(default=DEFAULT_LIMIT, max_size=MAX_LIMIT,
                       metadata={"description": f"results per page (default {DEFAULT_LIMIT}, max {MAX_LIMIT})"})

    @validates_schema
    def _inside_the_window(self, data, **kwargs):
        page, limit = data.get("page", 1), data.get("limit", DEFAULT_LIMIT)
        if (page - 1) * limit >= config.IGA_SHOP_MAX_SKIP:
            raise ValidationError(
                f"page {page} x limit {limit} is past the storefront's {config.IGA_SHOP_MAX_SKIP}-row "
                "window; narrow the query instead.", "page")


# ---- stores -------------------------------------------------------------------

class StoresSearchSchema(_Paged):
    query = QueryField(required=False, load_default=None, max_length=80, validate=_max_length(80), metadata={
        "description": "store name, suburb, postcode, state (VIC) or store number; omit for every store"})


class StoresNearbySchema(BaseSchema):
    latitude = fields.Float(required=True, validate=validate.Range(min=-90, max=90),
                            metadata={"description": "latitude of the point to search around"})
    longitude = fields.Float(required=True, validate=validate.Range(min=-180, max=180),
                             metadata={"description": "longitude of the point to search around"})
    radius_km = fields.Integer(load_default=100, validate=validate.Range(min=1, max=1000), strict=False,
                               metadata={"description": "search radius in km (default 100)"})
    limit = LimitField(default=10, max_size=50, metadata={"description": "stores to return (default 10, max 50)"})


class StoreSchema(BaseSchema):
    store = StoreRefField(required=True, metadata={
        "description": "store number (32600), postcode (3065), suburb or store name (fitzroy), "
                       "or an igashop.com.au store link"})


# ---- products ------------------------------------------------------------------

class ProductsSearchSchema(_Paged):
    query = QueryField(max_length=50, metadata={
        "description": "what you would type in the site's search box (the storefront reads the first 50 characters)"})
    store = StoreRefField()
    sort = SortField()
    brand = BrandFilterField()
    category = CategoryFilterField()


class ProductSchema(BaseSchema):
    product = ProductRefField(metadata={
        "description": "product SKU (494526) or an igashop.com.au product link"})
    store = StoreRefField()


class SpecialsSchema(_Paged):
    store = StoreRefField()
    sort = SortField()
    brand = BrandFilterField()
    category = CategoryFilterField()


# ---- categories ------------------------------------------------------------------

class CategoriesSchema(BaseSchema):
    store = StoreRefField()


class CategoryProductsSchema(_Paged):
    category = CategoryRefField(metadata={
        "description": "category identifier (Apples_Pears_and_Bananas), its slug "
                       "(apples-pears-and-bananas), its name, or an igashop.com.au category link; "
                       "grocery = the whole catalogue"})
    store = StoreRefField()
    sort = SortField()
    brand = BrandFilterField()


class CategoryOverviewSchema(BaseSchema):
    category = CategoryRefField(metadata={
        "description": "category identifier, slug, name or link whose subcategories to preview"})
    store = StoreRefField()
    limit = LimitField(default=6, max_size=MAX_LIMIT, metadata={
        "description": "products per subcategory (default 6, max 100)"})


# ---- recipes ----------------------------------------------------------------------

class RecipesSearchSchema(_Paged):
    query = QueryField(required=False, load_default=None, max_length=80, validate=_max_length(80), metadata={
        "description": "recipe keyword (chicken, pavlova); omit for every recipe"})
    category = StrippedString(required=False, load_default=None, validate=_max_length(60), metadata={
        "description": "recipe category by name (Dinner, Lunch, Entertaining, Desserts, Winter...); "
                       "the response's categories lists them with counts"})
    store = StoreRefField()


class RecipeSchema(BaseSchema):
    recipe = RecipeRefField(metadata={
        "description": "recipe id (a UUID or a short numeric id) or an igashop.com.au recipe link"})
    store = StoreRefField()


# ---- sitemaps -----------------------------------------------------------------------

class SitemapProductsSchema(BaseSchema):
    page = PageField(max_page=10000, metadata={"description": "1-based page"})
    limit = LimitField(default=100, max_size=1000, metadata={
        "description": "product links per page (default 100, max 1000)"})


class SitemapLinksSchema(BaseSchema):
    type = ChoiceField(list(refs.LINK_TYPES), load_default="all", metadata={
        "description": "all (default), categories, recipes, specials or pages"})
    page = PageField(max_page=10000, metadata={"description": "1-based page"})
    limit = LimitField(default=100, max_size=1000, metadata={
        "description": "links per page (default 100, max 1000)"})
