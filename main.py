"""Use the scraper straight from Python — no server needed.

    python main.py

Every call is validated by the same schema the API uses and returns the same
records; results are written to output/*.json.
"""
import json
import os

from schema_fields import load_query
from iga_shop import api, schemas

os.makedirs("output", exist_ok=True)


def run(schema_cls, fn, **params):
    data, error = load_query(schema_cls, {k: str(v) for k, v in params.items()})
    if error:
        raise ValueError(error)
    return fn(**data)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


if __name__ == "__main__":
    # a SKU or any igashop.com.au product link; prices are per store
    save("product_308953.json", run(schemas.ProductSchema, api.product_details, product="308953", store="bondi"))

    # 20 products per page, with brand / category facets and sorting
    save("search_tim_tam.json", run(schemas.ProductsSearchSchema, api.products_search, query="tim tam"))

    # the IGA stores closest to the Sydney Opera House
    save("stores_near_sydney_opera_house.json", run(schemas.StoresNearbySchema, api.stores_nearby,
                                                    latitude=-33.8568, longitude=151.2153))
