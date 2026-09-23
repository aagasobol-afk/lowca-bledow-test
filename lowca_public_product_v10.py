#!/usr/bin/env python3
"""Łowca Błędów v1.0 — wspólny odczyt publicznych stron produktów."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


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


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    s = str(value).replace("\u00a0", " ").strip()
    s = re.sub(r"[^0-9,\.]", "", s).replace(",", ".")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _availability(value: Any) -> bool | None:
    if value is None:
        return None
    s = str(value).lower()
    if "instock" in s or "available" in s:
        return True
    if "outofstock" in s or "soldout" in s:
        return False
    return None


def _product_jsonld(html: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for item in _walk(data):
            typ = item.get("@type") if isinstance(item, dict) else None
            if typ == "Product" or (isinstance(typ, list) and "Product" in typ):
                return item
    return None


def fetch_public_product(url: str, store: str, timeout: int = 20) -> ProductSnapshot:
    host = urlparse(url).netloc.lower()
    if not host:
        raise ValueError("Nieprawidłowy URL produktu.")

    r = requests.get(
        url,
        timeout=timeout,
        allow_redirects=True,
        headers={
            "User-Agent": "LowcaBledow/1.0 (+public-product-check)",
            "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    if r.status_code in {401, 403, 429}:
        raise RuntimeError(f"{store} odmówił dostępu HTTP {r.status_code}; Łowca nie obchodzi blokady.")
    r.raise_for_status()

    product = _product_jsonld(r.text)
    if not product:
        raise RuntimeError("Nie znaleziono publicznych danych Product JSON-LD.")

    offers = product.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        offers = {}

    price = _decimal(offers.get("price"))
    name = str(product.get("name") or "").strip()
    if price is None or not name:
        raise RuntimeError("Produkt nie ma czytelnej nazwy lub ceny.")

    return ProductSnapshot(
        name=name,
        store=store,
        url=url,
        price=price,
        currency=str(offers.get("priceCurrency") or "PLN"),
        available=_availability(offers.get("availability")),
        sku=str(product.get("sku")) if product.get("sku") else None,
        ean=str(product.get("gtin13") or product.get("gtin")) if (product.get("gtin13") or product.get("gtin")) else None,
    )


def snapshot_dict(snapshot: ProductSnapshot) -> dict[str, Any]:
    d = asdict(snapshot)
    d["price"] = str(d["price"])
    return d
