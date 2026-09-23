#!/usr/bin/env python3
"""Łowca Błędów v0.9 — real source -> history -> detector.

Stan jest przechowywany w prostym pliku JSON. To etap prototypowy:
później zastąpimy go trwałą bazą dla monitoringu 24/7.
"""
from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path

from lowca_mediaexpert_v09 import TEST_URL, fetch_mediaexpert_product
from lowca_engine_v03 import classify_price_change

STATE_FILE = Path(os.getenv("LOWCA_STATE_FILE", "lowca_live_state.json"))


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    snapshot = fetch_mediaexpert_product(TEST_URL)
    state = load_state()
    key = f"{snapshot.store}|{snapshot.url}"

    previous = state.get(key)
    detection = None
    if previous:
        detection = classify_price_change(
            Decimal(str(previous["price"])),
            snapshot.price,
        )

    state[key] = {
        "name": snapshot.name,
        "store": snapshot.store,
        "url": snapshot.url,
        "price": str(snapshot.price),
        "currency": snapshot.currency,
        "available": snapshot.available,
        "sku": snapshot.sku,
        "ean": snapshot.ean,
    }
    save_state(state)

    print("=== ŁOWCA BŁĘDÓW v0.9 — REAL SOURCE ===")
    print("Produkt:", snapshot.name)
    print("Sklep:", snapshot.store)
    print("Cena:", snapshot.price, snapshot.currency)
    print("Dostępny:", snapshot.available)
    print("SKU:", snapshot.sku or "-")
    print("EAN:", snapshot.ean or "-")

    if previous is None:
        print("Poprzednia cena: brak — zapisuję punkt bazowy.")
        return 0

    print("Poprzednia cena:", previous["price"], previous["currency"])
    print("Wynik:", detection.level)
    print("Score:", detection.score)
    print("Powody:", " | ".join(detection.reasons))

    if detection.level in {"HIGH", "CRITICAL"}:
        print("ALERT_CANDIDATE")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
