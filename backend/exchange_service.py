"""Retrieve validated PHP reference exchange rates from Frankfurter.

Uses only Python's standard library. No account or API key is required.
Inventory records are never sent to the provider: requests contain a currency pair.
"""

import argparse
import json
import threading
import time
from datetime import date
from decimal import Decimal
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SUPPORTED_CURRENCIES = ("USD", "EUR", "SGD", "JPY", "GBP")
API_BASE = "https://api.frankfurter.dev/v2/rate/php"
MAX_RESPONSE_BYTES = 65536


class ExchangeService:
    """Cache successful pair quotes for 15 minutes within this process."""

    def __init__(self, fetcher=None, clock=time.monotonic):
        self.fetcher = fetcher or fetch_exchange_rate
        self.clock = clock
        self.cache = {}
        self.lock = threading.Lock()

    def get_quote(self, target="USD"):
        if (
            not isinstance(target, str)
            or target.strip().upper() not in SUPPORTED_CURRENCIES
        ):
            raise ValueError("Choose USD, EUR, SGD, JPY, or GBP.")
        target = target.strip().upper()
        with self.lock:
            saved = self.cache.get(target)
            if saved is not None and self.clock() - saved[0] < 900:
                return {**saved[1], "cached": True}
            quote = self.fetcher(target)
            self.cache[target] = (self.clock(), dict(quote))
            return {**quote, "cached": False}


def fetch_exchange_rate(target="USD"):
    """Return provider, base, quote, decimal-string rate, and observation date.

    Raise ValueError for unsupported input before making a request. Raise
    RuntimeError for unavailable service or invalid provider data. The caller
    should show that message to the operator without stopping inventory work.
    """
    if not isinstance(target, str):
        raise ValueError("Choose USD, EUR, SGD, JPY, or GBP.")
    target = target.strip().upper()
    if target not in SUPPORTED_CURRENCIES:
        raise ValueError("Choose USD, EUR, SGD, JPY, or GBP.")

    request = Request(
        f"{API_BASE}/{target.lower()}",
        headers={
            "Accept": "application/json",
            "User-Agent": "CS0053Inventory/1.0 (educational project)",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"Exchange service returned HTTP {response.status}. Try again later."
                )
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        status = error.code
        error.close()
        if status == 429:
            message = "Too many exchange requests. Wait before trying again."
        else:
            message = f"Exchange service returned HTTP {status}. Try again later."
        raise RuntimeError(message) from error
    except (URLError, OSError, TimeoutError, HTTPException) as error:
        raise RuntimeError(
            "Cannot connect to the exchange service. Check your internet and retry."
        ) from error

    try:
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("Response exceeds size limit")
        # Parse JSON numbers directly as Decimal to preserve the returned precision.
        data = json.loads(raw, parse_float=Decimal)
        if not isinstance(data, dict):
            raise ValueError("Expected an object")
        if data.get("base") != "PHP" or data.get("quote") != target:
            raise ValueError("Unexpected currency pair")
        rate = data.get("rate")
        if isinstance(rate, bool) or not isinstance(rate, (int, Decimal)):
            raise ValueError("Expected a numeric rate")
        rate = Decimal(rate)
        if not rate.is_finite() or not 0 < rate < 1000000:
            raise ValueError("Invalid rate")
        observed = data.get("date")
        if (
            not isinstance(observed, str)
            or date.fromisoformat(observed).isoformat() != observed
        ):
            raise ValueError("Invalid observation date")
        return {
            "base": "PHP",
            "quote": target,
            "rate": str(rate),
            "date": observed,
            "provider": "Frankfurter",
        }
    except (ValueError, TypeError, UnicodeError) as error:
        raise RuntimeError(
            "Exchange service returned invalid data. Try again later."
        ) from error


def main():
    """Provide a real terminal action for checking the external API connection."""
    parser = argparse.ArgumentParser(
        description="Fetch a PHP exchange rate from Frankfurter"
    )
    parser.add_argument("--target", default="USD", help="USD, EUR, SGD, JPY, or GBP")
    args = parser.parse_args()
    try:
        result = fetch_exchange_rate(args.target)
    except (ValueError, RuntimeError) as error:
        print(f"Error: {error}")
        return 1
    print(f"Provider: {result['provider']}")
    print(f"Rate date: {result['date']}")
    print(f"1 PHP = {result['rate']} {result['quote']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
