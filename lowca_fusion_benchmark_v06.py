#!/usr/bin/env python3
"""Benchmark połączenia sygnałów v0.6."""
from decimal import Decimal
from lowca_fusion_v06 import analyze_price

CASES = [
    ("stabilna", 7999, 7799, [7999,7999,7899,7999], "NORMAL"),
    ("rabat 10%", 999, 899, [999,999,949,999], "NORMAL"),
    ("rabat 20%", 999, 799, [999,999,949,999], "NORMAL"),
    ("duży rabat", 7999, 3999, [7999,7999,7899,7999], "HIGH"),
    ("duży rabat", 1999, 999, [1999,1999,1899,1999], "HIGH"),
    ("bardzo duży rabat", 7999, 1599, [7999,7999,7899,7999], "HIGH"),
    ("błąd cyfry", 7999, 799, [7999,7999,7899,7999], "CRITICAL"),
    ("przecinek", 7999, 79.99, [7999,7999,7899,7999], "CRITICAL"),
    ("przecinek", 2369, 236.90, [2369,2369,2299,2369], "CRITICAL"),
    ("błąd bez historii", 7999, 799, [7999,7999], "CRITICAL"),
    ("nowy produkt, duży spadek", 999, 499, [999,999], "WATCH"),
    ("brak zmiany", 7999, 7999, [7999,7999,7899,7999], "NORMAL"),
]


def main():
    passed = 0
    failed = []

    for name, old, new, history, expected in CASES:
        result = analyze_price(
            Decimal(str(old)),
            Decimal(str(new)),
            [Decimal(str(x)) for x in history],
        )
        if result.level == expected:
            passed += 1
        else:
            failed.append(
                f"{name}: {old}->{new}: expected {expected}, "
                f"got {result.level} (score={result.score})"
            )

    print("=== ŁOWCA BŁĘDÓW v0.6 — FUSION BENCHMARK ===")
    print(f"Przypadki: {len(CASES)}")
    print(f"PASS: {passed}")
    print(f"FAIL: {len(failed)}")

    if failed:
        print("\n--- BŁĘDY ---")
        for item in failed:
            print(item)
        raise SystemExit(1)

    print("\nWYNIK: 100% PASS")


if __name__ == "__main__":
    main()
