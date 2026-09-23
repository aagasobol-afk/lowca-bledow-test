#!/usr/bin/env python3
"""Łowca Błędów v0.5 - pamięć historii ceny.

Etap testowy: historia jest trzymana w pamięci procesu.
Docelowo zastąpimy ją trwałą bazą danych.
"""

from dataclasses import dataclass
from decimal import Decimal
from statistics import median
from lowca_engine_v03 import Detection


@dataclass
class HistoryResult:
    level: str
    score: int
    reasons: list[str]
    reference_price: Decimal | None = None


def classify_against_history(
    history: list[Decimal],
    current: Decimal,
    *,
    min_history_points: int = 3,
) -> HistoryResult:
    """Porównuje bieżącą cenę z medianą wcześniejszych cen.

    CRITICAL: minimum 3 historyczne punkty i bieżąca cena <= 20% mediany.
    WATCH: minimum 3 punkty i bieżąca cena <= 60% mediany.
    NORMAL: brak wystarczającej historii albo zmiana mieści się w typowym zakresie.
    """
    clean = [p for p in history if p > 0]
    if current <= 0:
        return HistoryResult("NORMAL", 0, ["nieprawidłowa cena"], None)

    if len(clean) < min_history_points:
        return HistoryResult(
            "NORMAL",
            0,
            [f"za mało historii: {len(clean)}/{min_history_points}"],
            None,
        )

    reference = Decimal(str(median(clean)))
    ratio = current / reference

    if ratio <= Decimal("0.15"):
        return HistoryResult(
            "CRITICAL",
            100,
            ["cena jest <= 20% mediany historii"],
            reference,
        )

    if ratio <= Decimal("0.60"):
        return HistoryResult(
            "WATCH",
            50,
            ["cena jest <= 60% mediany historii"],
            reference,
        )

    return HistoryResult(
        "NORMAL",
        10,
        ["cena mieści się w typowym zakresie historii"],
        reference,
    )


def demo():
    scenarios = [
        (
            "Sony A7 IV - stabilna cena",
            [Decimal("7999"), Decimal("7999"), Decimal("7899"), Decimal("7999")],
            Decimal("7799"),
            "NORMAL",
        ),
        (
            "Sony A7 IV - duża promocja",
            [Decimal("7999"), Decimal("7999"), Decimal("7899"), Decimal("7999")],
            Decimal("3999"),
            "WATCH",
        ),
        (
            "Sony A7 IV - możliwy błąd",
            [Decimal("7999"), Decimal("7999"), Decimal("7899"), Decimal("7999")],
            Decimal("799"),
            "CRITICAL",
        ),
        (
            "Nowy produkt - za mało historii",
            [Decimal("7999"), Decimal("7999")],
            Decimal("799"),
            "NORMAL",
        ),
    ]

    print("=== ŁOWCA BŁĘDÓW v0.5 — HISTORIA CENY ===")
    for name, history, current, expected in scenarios:
        result = classify_against_history(history, current)
        status = "PASS" if result.level == expected else "FAIL"
        print(
            f"{status} | {name} | historia={history} | "
            f"teraz={current} | {result.level} | "
            f"mediana={result.reference_price}"
        )


if __name__ == "__main__":
    demo()
