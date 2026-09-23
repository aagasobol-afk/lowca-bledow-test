#!/usr/bin/env python3
"""Łowca Błędów v0.9 — adapter Media Expert.

Czyta publiczną stronę produktu. Najpierw próbuje JSON-LD Product,
a jeśli sklep go nie publikuje, korzysta z jawnych danych HTML strony.
Nie obchodzi CAPTCHA, Cloudflare ani innych blokad.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Any
from urllib.parse import urlparse

import requests


TEST_URL = (
    "https://www.mediaexpert.pl/foto-i-kamery/aparaty-fotograficzne/"
    "aparaty-z-wymienna-optyka-bezlustrowce/aparat-sony-alpha-ilce-7m4b"
)


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
    text = str(value).replace(" ", " ").replace(" ", "").replace(",", ".")
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


def _plain_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(re.sub(r"s+", " ", text))


def _meta(html: str, name: str) -> str | None:
    pattern = (
        r'<meta[^>]+(?:name|property)=["\']'
        + re.escape(name)
        + r'["\'][^>]+content=["\'](.*?)["\']'
    )
    match = re.search(pattern, html, flags=re.I | re.S)
    return unescape(match.group(1)).strip() if match else None


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


def _html_fallback(html: str) -> tuple[str, Decimal, str | None, str | None, bool | None]:
    text = _plain_text(html)

    title = _meta(html, "og:title")
    if not title:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
        title = unescape(re.sub(r"s+", " ", match.group(1))).strip() if match else None
    if not title:
        raise RuntimeError("Nie znaleziono nazwy produktu.")

    # Format widoczny na stronie Media Expert: 7 999 00 zł.
    prices = re.findall(r"(d[ds.]*)s+(d{2})s*zł", text, flags=re.I)
    parsed = []
    for whole, cents in prices:
        whole = re.sub(r"[s.]", "", whole)
        try:
            parsed.append(Decimal(f"{whole}.{cents}"))
        except InvalidOperation:
            pass
    if not parsed:
        # Fallback for 7 999,00 zł / 7999,00 zł.
        prices2 = re.findall(r"(d[ds.]*)s*[,\.]s*(d{2})s*zł", text, flags=re.I)
        for whole, cents in prices2:
            whole = re.sub(r"[s.]", "", whole)
            parsed.append(Decimal(f"{whole}.{cents}"))
    if not parsed:
        raise RuntimeError("Nie znaleziono ceny w publicznym HTML.")

    code_match = re.search(r"Kod:s*([A-Za-z0-9._-]+)", text, flags=re.I)
    sku = code_match.group(1) if code_match else None

    ean = (
        _meta(html, "product:gtin13")
        or _meta(html, "gtin13")
        or _meta(html, "product:ean")
    )
    available = bool(
        re.search(r"(dostawa|ws+sklepie|us+ciebie|dostępny)", text, flags=re.I)
    )

    return title.split(" | ")[0].strip(), parsed[0], sku, ean, available


def fetch_mediaexpert_product(url: str = TEST_URL, timeout: int = 20) -> ProductSnapshot:
    parsed = urlparse(url)
    if parsed.netloc.lower() not in {"www.mediaexpert.pl", "mediaexpert.pl"}:
        raise ValueError("URL nie należy do Media Expert.")

    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": "LowcaBledow/0.9 (+public-product-check)",
            "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        },
    )

    if response.status_code in {401, 403, 429}:
        raise RuntimeError(
            f"Media Expert odmówił dostępu HTTP {response.status_code}; "
            "Łowca nie obchodzi tej blokady."
        )
    response.raise_for_status()

    product = _first_product_jsonld(response.text)
    if product:
        offers = product.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if not isinstance(offers, dict):
            offers = {}

        price = _price(offers.get("price"))
        name = str(product.get("name") or "").strip()
        if price is not None and name:
            availability = _available(offers.get("availability"))
            return ProductSnapshot(
                name=name,
                store="Media Expert",
                url=url,
                price=price,
                currency=str(offers.get("priceCurrency") or "PLN"),
                available=availability,
                sku=str(product.get("sku")) if product.get("sku") else None,
                ean=str(product.get("gtin13") or product.get("gtin")) if (
                    product.get("gtin13") or product.get("gtin")
                ) else None,
            )

    name, price, sku, ean, available = _html_fallback(response.text)
    return ProductSnapshot(
        name=name,
        store="Media Expert",
        url=url,
        price=price,
        currency="PLN",
        available=available,
        sku=sku,
        ean=ean,
    )


def snapshot_dict(snapshot: ProductSnapshot) -> dict[str, Any]:
    data = asdict(snapshot)
    data["price"] = str(data["price"])
    return data


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) == 2 else TEST_URL
    print(json.dumps(snapshot_dict(fetch_mediaexpert_product(url)), ensure_ascii=False, indent=2))
