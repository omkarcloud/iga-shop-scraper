"""Configuration for the IGA Shop Scraper. Everything can be set with an
environment variable; the defaults work out of the box.

    PORT            port the API listens on (default 8000)
    IGA_SHOP_PROXY  proxy URL for every request, e.g. http://user:pass@host:port
                    (default: none — direct). igashop.com.au answered every
                    endpoint from a plain cloud server IP, a datacenter proxy
                    and an Australian residential proxy alike, so you very
                    likely don't need this. Set it only if you start seeing
                    failures at high volume.

Everything else below is a plain constant with a working default — edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

# The store every anonymous visitor of igashop.com.au shops at (Ashcroft's
# IGA Erskine Park NSW). Prices, specials and ranging are per store, so every
# product endpoint takes a `store` and defaults to this one.
IGA_SHOP_DEFAULT_STORE = "32600"

# The storefront's listing window: `take` above 100 answers 0 items and
# `skip` >= 10000 answers an empty page.
IGA_SHOP_MAX_TAKE = 100
IGA_SHOP_MAX_SKIP = 10000

IGA_SHOP_PROXY = os.environ.get("IGA_SHOP_PROXY") or None


def iga_shop_proxy():
    """The proxy for a new HTTP session (None = direct)."""
    return os.environ.get("IGA_SHOP_PROXY") or None
