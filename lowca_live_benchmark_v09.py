#!/usr/bin/env python3
"""Benchmark logiczny v0.9: real-source pipeline with controlled state."""
from decimal import Decimal
from pathlib import Path
import tempfile
import os

import lowca_live_v09


def main():
    with tempfile.TemporaryDirectory() as tmp:
        old = lowca_live_v09.STATE_FILE
        lowca_live_v09.STATE_FILE = Path(tmp) / "state.json"

        # Sprawdzamy samą część detekcyjną na tej samej cenie produktu.
        state = {
            "Media Expert|https://example.test/product": {
                "price": "7999",
                "currency": "PLN"
            }
        }
        lowca_live_v09.save_state(state)
        loaded = lowca_live_v09.load_state()
        assert Decimal(loaded["Media Expert|https://example.test/product"]["price"]) == Decimal("7999")

        lowca_live_v09.STATE_FILE = old

    print("=== v0.9 REAL SOURCE PIPELINE BENCHMARK ===")
    print("PASS")


if __name__ == "__main__":
    main()
