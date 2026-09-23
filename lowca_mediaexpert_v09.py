#!/usr/bin/env python3
"""Łowca Błędów v0.9 - adapter publicznej strony produktu Media Expert.

Czyta wyłącznie publiczną stronę produktu i dane strukturalne JSON-LD.
Nie omija CAPTCHA, Cloudflare ani innych zabezpieczeń.
Jeśli sklep zwróci blokadę, adapter kończy pracę zamiast ją obchodzić.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

import requests


@dataclass
class ProductSnapshot:
    name: str
    store: str
    url: str
    price: Decimal
    currency: str
    available: bool | None
    sku: str | None
    ean: str | None


def _walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _price(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).replace("\xa0", " ").replace(" ", "").replace(",", ".")
    text = re.sub(r"[^0-9.]", "", text)
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _available(value: Any) -> bool | None:
    if value is None:
        return None
    text = str(value).lower()
    if "instock" in text or "available" in text:
        return True
    if "outofstock" in text or "soldout" in text:
        return False
    return None


def _first_product_jsonld(html: str) -> dict[str, Any] | None:
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.I | re.S,
    )
    for raw in scripts:
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        for item in _walk_json(data):
            typ = item.get("@type")
            if typ == "Product" or (isinstance(typ, list) and "Product" in typ):
                return item
    return None


def fetch_mediaexpert_product(url: str, timeout: int = 20) -> ProductSnapshot:
    parsed = urlparse(url)
    if parsed.netloc.lower() not in {"www.mediaexpert.pl", "mediaexpert.pl"}:
        raise ValueError("URL nie należy do Media Expert.")

    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "LowcaBledow/0.9 (+public-product-check)"},
    )

    if response.status_code in {401, 403, 429}:
        raise RuntimeError(
            f"Media Expert odmówił dostępu HTTP {response.status_code}; "
            "Łowca nie obchodzi tej blokady."
        )
    response.raise_for_status()

    product = _first_product_jsonld(response.text)
    if not product:
        raise RuntimeError("Nie znaleziono publicznego JSON-LD typu Product.")

    offers = product.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        offers = {}

    price = _price(offers.get("price"))
    if price is None:
        raise RuntimeError("Nie znaleziono ceny produktu w danych strukturalnych.")

    name = str(product.get("name") or "").strip()
    if not name:
        raise RuntimeError("Nie znaleziono nazwy produktu.")

    availability = _available(offers.get("availability"))
    sku = product.get("sku")
    ean = product.get("gtin13") or product.get("gtin") or product.get("gtin13")

    return ProductSnapshot(
        name=name,
        store="Media Expert",
        url=url,
        price=price,
        currency=str(offers.get("priceCurrency") or "PLN"),
        available=availability,
        sku=str(sku) if sku else None,
        ean=str(ean) if ean else None,
    )


def snapshot_dict(snapshot: ProductSnapshot) -> dict[str, Any]:
    data = asdict(snapshot)
    data["price"] = str(data["price"])
    return data


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("Użycie: python lowca_mediaexpert_v09.py <URL_produktu>")

    snapshot = fetch_mediaexpert_product(sys.argv[1])
    print(json.dumps(snapshot_dict(snapshot), ensure_ascii=False, indent=2))
