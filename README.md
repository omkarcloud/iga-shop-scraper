# 🛒 IGA Shop Scraper

IGA Shop Scraper is a **free and open-source** scraper that gets you **unlimited** detailed IGA Shop data for free.

## ✨ What Can I Get?

- 🛒 **Full details on 13,000+ grocery products** — price, was-price, unit price, nutrition, ingredients, allergens & aisle
- 🔥 **3,000+ live specials & 490+ categories** — sale price, % off, deal end date; filter by brand, sort by price
- 🏪 **All 540 IGA stores** — address, phone, email, opening hours, coordinates & per-store prices
- 🍰 **460+ recipes** — step-by-step directions, servings, cook times & ingredients linked to IGA products

## 🎥 Example: A Full IGA Shop Product

```json
{
  "sku": "308953",
  "name": "Arnott's Tim Tam Chocolate Original",
  "brand": "Arnott's",
  "link": "https://www.igashop.com.au/product/arnotts-tim-tam-chocolate-original-308953",
  "images": [
    "https://cdn.metcash.media/image/upload/w_1500,h_1500,c_pad,b_auto/igashop/images/308953.jpg",
    "https://cdn.metcash.media/image/upload/w_1500,h_1500,c_pad,b_auto/igashop/images/308953_1.jpg"
  ],
  "size": { "value": 200.0, "unit": "g", "label": "Gram" },
  "is_available": true,
  "pricing": {
    "price": 4.5,
    "was_price": 6.0,
    "currency": "AUD",
    "saving": 1.5,
    "saving_percent": 25,
    "special": { "label": "25% Off", "price": 4.5, "starts_at": "2026-10-28", "ends_at": "2026-11-04", "is_active": true },
    "unit_price": { "amount": 2.25, "per": "100g", "text": "$2.25/100g" }
  },
  "description": "Find your moment of indulgence with Arnott’s Tim Tam Original Chocolate Biscuits. Made with irresistible real chocolate, these biscuits are the perfect way to indulge in the afternoon or unwind at the end of a long day. It’s easy to see why Tim Tam is Australia’s most-loved chocolate biscuit. What more could you wish for?",
  "country_of_origin": "Made in Australia",
  "allergens_may_be_present": "Gluten| Milk| Soy| Wheat",
  "nutrition": {
    "panels": [
      {
        "basis": "Per 100g / Per 100mL",
        "nutrients": [
          { "name": "Energy", "value": 2190.0, "unit": "kJ" },
          { "name": "Protein", "value": 4.6, "unit": "g" },
          { "name": "Total Sugars", "value": 46.0, "unit": "g" }
        ]
      }
    ]
  },
  "category": { "id": "Biscuits_and_Cookies", "name": "Biscuits and Cookies", "breadcrumb": "Grocery/Pantry/Snacks/Biscuits and Cookies" },
  "store_location": { "aisle": "1", "bay": "32", "shelf": "0", "section": "Biscuits and Cookies" },
  "store": { "number": "32600", "name": "Ashcroft's IGA Erskine Park", "suburb": "Erskine Park", "state": "NSW", "postcode": "2759" }
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free IGA Shop Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/iga-shop-scraper
cd iga-shop-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/products/details?product=308953"
```

```json
{
  "sku": "308953",
  "name": "Arnott's Tim Tam Chocolate Original",
  "brand": "Arnott's",
  "link": "https://www.igashop.com.au/product/arnotts-tim-tam-chocolate-original-308953",
  "size": { "value": 200.0, "unit": "g", "label": "Gram" },
  "is_available": true,
  "pricing": {
    "price": 4.5,
    "was_price": 6.0,
    "currency": "AUD",
    "saving": 1.5,
    "saving_percent": 25,
    "is_on_special": true,
    "unit_price": { "amount": 2.25, "per": "100g", "text": "$2.25/100g" }
  },
  "country_of_origin": "Made in Australia",
  "allergens_may_be_present": "Gluten| Milk| Soy| Wheat",
  "category": { "id": "Biscuits_and_Cookies", "name": "Biscuits and Cookies", "breadcrumb": "Grocery/Pantry/Snacks/Biscuits and Cookies" },
  "store_location": { "aisle": "1", "bay": "32", "shelf": "0", "section": "Biscuits and Cookies" },
  "store": { "number": "32600", "name": "Ashcroft's IGA Erskine Park", "state": "NSW" }
}
```

All 13 endpoints are now live at `http://localhost:8000`.

## 📚 Endpoints

13 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Product Details | `/products/details` | Price, special, nutrition, ingredients, allergens and aisle in one call |
| Search Products | `/products/search` | Up to 100 per page, filtered by brand or category, sortable by price |
| Specials | `/products/specials` | Every product on special: sale price, % off, deal end date |
| Categories | `/categories/list` | The full category tree with IDs, slugs and links |
| Category Products | `/categories/products` | Every product in any category, or the whole catalogue |
| Category Overview | `/categories/overview` | Each subcategory's product count and first products in one call |
| Search Stores | `/stores/search` | All 540 stores, searchable by name, suburb, postcode or state |
| Nearby Stores | `/stores/nearby` | The closest stores to any point, with distance |
| Store Details | `/stores/details` | Address, phone, email, opening hours, delivery and pickup |
| Search Recipes | `/recipes/search` | 460+ recipes by keyword or category, with cook times |
| Recipe Details | `/recipes/details` | Directions, servings and ingredients linked to IGA products |
| Product Sitemap | `/sitemap/products` | Up to 10,000 product links with SKU and name |
| Site Links | `/sitemap/links` | Every category, recipe, specials and content page link |

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-iga-shop-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-iga-shop-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-iga-shop-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/products/details",
    params={"product": "308953"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about IGA Shop Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://api.whatsapp.com/send?phone=918178804274&text=I%20need%20help%20using%20the%20IGA%20Shop%20Scraper%20API.)

[![Ask Us by Email about IGA Shop Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20IGA%20Shop%20Scraper%20API&body=I%20need%20help%20using%20the%20IGA%20Shop%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper-api) — live product details, SKU variants, stock & shipping
- [**Booking Scraper**](https://www.omkar.cloud/tools/booking-scraper) — Booking.com hotels: prices, ratings, rooms & amenities
- [**Etsy Scraper**](https://www.omkar.cloud/tools/etsy-scraper) — Etsy products: prices, discounts, shops & variations

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/iga-shop-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/iga-shop-scraper)
