#!/usr/bin/env python3
"""Benchmark pamięci produktów v0.7."""

from decimal import Decimal
from lowca_store_v07 import PriceStore


def main():
    store = PriceStore()

    product = store.upsert_product(
        "Sony A7 IV body - ILCE7M4B",
        "Fotoforma",
        "https://example.test/sony-a7-iv",
        ean="4548736133754",
        sku="ILCE7M4B",
    )

    # Ten sam produkt nie tworzy duplikatu.
    same = store.upsert_product(
        "Sony A7 IV body - ILCE7M4B",
        "Fotoforma",
        "https://example.test/sony-a7-iv",
        ean="4548736133754",
        sku="ILCE7M4B",
    )

    assert product.id == same.id

    for price in ("7999", "7999", "7899", "7999", "799"):
        store.record_price(product.id, Decimal(price))

    history = store.get_history(product.id)
    assert history == [
        Decimal("7999"),
        Decimal("7999"),
        Decimal("7899"),
        Decimal("7999"),
        Decimal("799"),
    ]

    latest = store.get_latest(product.id)
    assert latest is not None
    assert latest.price == Decimal("799")
    assert latest.available is True

    print("=== ŁOWCA BŁĘDÓW v0.7 — STORE BENCHMARK ===")
    print("Produktów: 1")
    print("Punktów historii: 5")
    print("Duplikat produktu: zablokowany")
    print("Ostatnia cena: 799 PLN")
    print("WYNIK: 100% PASS")

    store.close()


if __name__ == "__main__":
    main()
