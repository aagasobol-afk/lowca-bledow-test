#!/usr/bin/env python3
"""Benchmark pamięci ceny v0.5."""

from decimal import Decimal
from lowca_history_v05 import classify_against_history

CASES = [
    ([7999, 7999, 7899, 7999], 7799, "NORMAL"),
    ([7999, 7999, 7899, 7999], 6999, "NORMAL"),
    ([7999, 7999, 7899, 7999], 5999, "NORMAL"),
    ([7999, 7999, 7899, 7999], 3999, "WATCH"),
    ([7999, 7999, 7899, 7999], 2999, "WATCH"),
    ([7999, 7999, 7899, 7999], 1599, "WATCH"),
    ([7999, 7999, 7899, 7999], 799, "CRITICAL"),
    ([7999, 7999, 7899, 7999], 79.99, "CRITICAL"),
    ([999, 999, 899, 999], 799, "NORMAL"),
    ([999, 999, 899, 999], 499, "WATCH"),
    ([999, 999, 899, 999], 99.90, "CRITICAL"),
    ([2369, 2369, 2299, 2369], 1899, "NORMAL"),
    ([2369, 2369, 2299, 2369], 1199, "WATCH"),
    ([2369, 2369, 2299, 2369], 236.90, "CRITICAL"),
    ([7999, 7999], 799, "NORMAL"),
    ([7999], 799, "NORMAL"),
    ([], 799, "NORMAL"),
]


def main():
    passed = 0
    failed = []

    for history, current, expected in CASES:
        result = classify_against_history(
            [Decimal(str(x)) for x in history],
            Decimal(str(current)),
        )
        if result.level == expected:
            passed += 1
        else:
            failed.append(
                f"{history} -> {current}: expected {expected}, "
                f"got {result.level}; " + "; ".join(result.reasons)
            )

    print("=== ŁOWCA BŁĘDÓW v0.5 — HISTORIA ===")
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
