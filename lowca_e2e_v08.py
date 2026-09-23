#!/usr/bin/env python3
"""Łowca Błędów v0.8 - pierwszy przepływ end-to-end.

Źródło jest na razie symulowane, żeby nie obchodzić blokad sklepów.
Przepływ: snapshot -> zapis historii -> fusion -> alarm payload.
"""
from __future__ import annotations

import json
import os
import tempfile
from decimal import Decimal

from lowca_fusion_v06 import analyze_price
from lowca_store_v07 import PriceStore


def run():
    # Kontrolowany "snapshot" udający wynik dozwolonego źródła danych.
    product = {
        "name": "Sony A7 IV body - ILCE7M4B",
        "store": "TEST-SOURCE",
        "url": "https://example.test/sony-a7-iv",
        "ean": "4548736133754",
        "sku": "ILCE7M4B",
        "available": True,
    }

    historical_prices = ["7999", "7999", "7899", "7999"]
    current_price = Decimal("799")

    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = PriceStore(tmp.name)
        item = store.upsert_product(
            product["name"],
            product["store"],
            product["url"],
            product["ean"],
            product["sku"],
        )

        for price in historical_prices:
            store.record_price(item.id, Decimal(price))

        previous = store.get_latest(item.id)
        store.record_price(item.id, current_price, product["available"])

        history = store.get_history(item.id)[:-1]
        fusion = analyze_price(
            previous.price if previous else Decimal(historical_prices[-1]),
            current_price,
            history,
        )

        alarm = {
            "type": "LOWCA_ALERT",
            "level": fusion.level,
            "score": fusion.score,
            "product": product["name"],
            "store": product["store"],
            "price_old": str(previous.price if previous else Decimal(historical_prices[-1])),
            "price_new": str(current_price),
            "currency": "PLN",
            "url": product["url"],
            "ean": product["ean"],
            "sku": product["sku"],
            "reasons": fusion.reasons,
        }

        print("=== ŁOWCA BŁĘDÓW v0.8 — END TO END ===")
        print("Produkt:", product["name"])
        print("Cena:", alarm["price_old"], "->", alarm["price_new"], "PLN")
        print("Wynik:", fusion.level)
        print("Score:", fusion.score)
        print("Powody:", " | ".join(fusion.reasons))
        print("ALARM_JSON_START")
        print(json.dumps(alarm, ensure_ascii=False))
        print("ALARM_JSON_END")

        if fusion.level not in {"HIGH", "CRITICAL"}:
            raise SystemExit("Kontrolowany scenariusz nie wygenerował alarmu.")


if __name__ == "__main__":
    run()
