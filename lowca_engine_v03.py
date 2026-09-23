#!/usr/bin/env python3
"""
Łowca Błędów v0.3
Pierwszy silnik testowy: odczyt ceny z karty produktu Fotoforma
+ kontrolowane testy błędów cenowych.

Etap testowy: nie omija zabezpieczeń sklepu i nie wykonuje zakupów.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import requests

FOTOFORMA_URL = "https://fotoforma.pl/aparat-cyfrowy-sony-a7-iv-body-ilce7m4b"

KNOWN_PRODUCT = {
    "name": "Sony A7 IV body - ILCE7M4B",
    "ean": "4548736133754",
    "product_id": "22752",
    "reference_price": Decimal("7999.00"),
}


@dataclass
class ProductSnapshot:
    name: str
    price: Decimal
    available: bool
    product_id: Optional[str] = None
    ean: Optional[str] = None
    url: Optional[str] = None


@dataclass
class Detection:
    level: str
    reasons: list[str]
    score: int


def parse_polish_price(value: str) -> Optional[Decimal]:
    cleaned = value.replace("\xa0", " ").replace("zł", "").strip()
    cleaned = re.sub(r"\s+", "", cleaned)

    if not re.search(r"\d", cleaned):
        return None

    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")

    try:
        return Decimal(cleaned)
    except Exception:
        return None


def extract_fotoforma_snapshot(html: str, url: str) -> ProductSnapshot:
    price = None

    patterns = [
        r'Cena:\s*.*?(\d[\d\s\xa0]*[,.]\d{2})',
        r'>(\d[\d\s\xa0]*[,.]\d{2})</',
        r'"price"\s*:\s*"?(\d+(?:[.,]\d{1,2})?)',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            price = parse_polish_price(match.group(1))
            if price is not None:
                break

    if price is None:
        raise ValueError("Nie znaleziono ceny na stronie produktu.")

    product_id = None
    ean = None

    match = re.search(r"ID produktu:\s*(\d+)", html, re.IGNORECASE)
    if match:
        product_id = match.group(1)

    match = re.search(r"Kod produktu:\s*(\d{8,14})", html, re.IGNORECASE)
    if match:
        ean = match.group(1)

    available = bool(re.search(r"Dostępność:\s*dostępny", html, re.IGNORECASE))

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    name = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else "Nieznany produkt"

    return ProductSnapshot(
        name=name,
        price=price,
        available=available,
        product_id=product_id,
        ean=ean,
        url=url,
    )


def classify_price_change(old: Decimal, new: Decimal) -> Detection:
    """
    Kluczowa zasada: sam duży rabat nie jest błędem cenowym.

    CRITICAL wymaga mocnego sygnału strukturalnego (np. usunięcie cyfry
    albo przesunięcie przecinka). Duży, ale możliwy rabat trafia do WATCH
    i dopiero historia/rynek/wariant może podnieść go wyżej.
    """
    if old <= 0 or new <= 0:
        return Detection("NORMAL", ["nieprawidłowa cena bazowa"], 0)

    if old == new:
        return Detection("NORMAL", ["brak zmiany ceny"], 0)

    ratio = new / old
    score = 0
    reasons: list[str] = []

    old_digits = str(int(old))
    new_text = format(new, "f")
    new_digits = new_text.replace(".", "").rstrip("0")

    # Bardzo mocny sygnał: zniknięcie jednej cyfry z początku/końca.
    if old_digits and (
        new_digits == old_digits[:-1] or new_digits == old_digits[1:]
    ):
        score += 110
        reasons.append("podejrzenie usunięcia jednej cyfry")

    # Mocny sygnał: przesunięcie przecinka o 1–2 miejsca,
    # np. 7999 -> 799.9 / 79.99.
    for divisor in (Decimal("10"), Decimal("100")):
        if new == old / divisor:
            score += 110
            reasons.append("podejrzenie przesunięcia przecinka")
            break

    if score >= 100:
        return Detection("CRITICAL", reasons, score)

    # Zwykła obniżka: nie alarmujemy.
    if ratio >= Decimal("0.80"):
        return Detection("NORMAL", ["zmiana mieści się w zakresie zwykłej obniżki"], 10)

    # Duży spadek bez strukturalnego dowodu błędu:
    # obserwujemy, ale nie ogłaszamy pomyłki cenowej.
    score = 30
    reasons.append("duży spadek ceny wymaga weryfikacji")
    return Detection("WATCH", reasons, score)


def run_controlled_tests() -> list[tuple[str, str, str]]:
    base = KNOWN_PRODUCT["reference_price"]
    cases = [
        ("7999 -> 799", Decimal("799")),
        ("7999 -> 79.99", Decimal("79.99")),
        ("7999 -> 799.90", Decimal("799.90")),
        ("7999 -> 899", Decimal("899")),
        ("7999 -> 7499", Decimal("7499")),
        ("7999 -> 7999", Decimal("7999")),
    ]

    results = []
    for label, new_price in cases:
        result = classify_price_change(base, new_price)
        results.append((label, result.level, "; ".join(result.reasons)))
    return results


def fetch_live_product() -> ProductSnapshot:
    response = requests.get(
        FOTOFORMA_URL,
        headers={"User-Agent": "LowcaBledowTest/0.3"},
        timeout=20,
    )
    response.raise_for_status()
    return extract_fotoforma_snapshot(response.text, FOTOFORMA_URL)


if __name__ == "__main__":
    print("=== ŁOWCA BŁĘDÓW v0.3 ===")
    print("Produkt testowy:", KNOWN_PRODUCT["name"])
    print("EAN:", KNOWN_PRODUCT["ean"])
    print("ID:", KNOWN_PRODUCT["product_id"])
    print()

    print("--- TEST KONTROLOWANY ---")
    for label, level, reason in run_controlled_tests():
        print(f"{label:18} -> {level:8} | {reason}")

    print()
    print("--- LIVE FOTOFORMA ---")
    try:
        snapshot = fetch_live_product()
        print("Produkt:", snapshot.name)
        print("Cena:", snapshot.price, "PLN")
        print("Dostępny:", snapshot.available)
        print("ID:", snapshot.product_id)
        print("EAN:", snapshot.ean)
        print("URL:", snapshot.url)

        detection = classify_price_change(
            KNOWN_PRODUCT["reference_price"], snapshot.price
        )
        print("Ocena względem ceny referencyjnej:", detection.level)
    except Exception as exc:
        print("LIVE ERROR:", exc)
