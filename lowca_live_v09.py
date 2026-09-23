#!/usr/bin/env python3
"""Łowca Błędów v0.9 — real source -> history -> fusion -> alert candidate."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from lowca_mediaexpert_v09 import TEST_URL, fetch_mediaexpert_product
from lowca_fusion_v06 import analyze_price

STATE_FILE = Path(os.getenv("LOWCA_STATE_FILE", "lowca_live_state.json"))
ALERT_FILE = Path(os.getenv("LOWCA_ALERT_FILE", "lowca_alert.json"))
MAX_HISTORY = 30


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    snapshot = fetch_mediaexpert_product(TEST_URL)
    state = load_state()
    key = f"{snapshot.store}|{snapshot.url}"
    previous = state.get(key, {})
    history = [Decimal(str(p)) for p in previous.get("history", []) if Decimal(str(p)) > 0]
    old_price = Decimal(str(previous["price"])) if previous.get("price") else None

    result = None
    if old_price is not None and old_price != snapshot.price:
        result = analyze_price(old_price, snapshot.price, history)

    history.append(snapshot.price)
    history = history[-MAX_HISTORY:]

    entry = {
        "name": snapshot.name,
        "store": snapshot.store,
        "url": snapshot.url,
        "price": str(snapshot.price),
        "currency": snapshot.currency,
        "available": snapshot.available,
        "sku": snapshot.sku,
        "ean": snapshot.ean,
        "history": [str(p) for p in history],
        "last_alert_signature": previous.get("last_alert_signature"),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    ALERT_FILE.unlink(missing_ok=True)

    print("=== ŁOWCA BŁĘDÓW v0.9 — REAL MONITOR ===")
    print("Produkt:", snapshot.name)
    print("Cena:", snapshot.price, snapshot.currency)
    print("Dostępny:", snapshot.available)
    print("Historia:", len(history), "punktów")

    if old_price is None:
        print("Poprzednia cena: brak — zapisuję punkt bazowy.")
    elif result is None:
        print("Cena bez zmiany:", old_price, "->", snapshot.price)
        entry["last_alert_signature"] = None
    else:
        print("Zmiana:", old_price, "->", snapshot.price)
        print("Wynik:", result.level, "| score:", result.score)
        print("Powody:", " | ".join(result.reasons))

        if result.level in {"HIGH", "CRITICAL"}:
            signature = f"{snapshot.url}|{snapshot.price}|{result.level}"
            if signature != previous.get("last_alert_signature"):
                alert = {
                    "type": "LOWCA_ALERT",
                    "level": result.level,
                    "score": result.score,
                    "product": snapshot.name,
                    "store": snapshot.store,
                    "price_old": str(old_price),
                    "price_new": str(snapshot.price),
                    "currency": snapshot.currency,
                    "url": snapshot.url,
                    "ean": snapshot.ean,
                    "sku": snapshot.sku,
                    "reasons": result.reasons,
                    "checked_at": entry["checked_at"],
                }
                ALERT_FILE.write_text(
                    json.dumps(alert, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                entry["last_alert_signature"] = signature
                print("NOWY_ALERT")
            else:
                print("Ten sam alarm już był wysłany — pomijam duplikat.")
        else:
            entry["last_alert_signature"] = None

    state[key] = entry
    save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
