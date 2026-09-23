#!/usr/bin/env python3
"""Łowca Błędów v0.6 - połączenie sygnałów.

Łączy:
1) strukturę zmiany ceny (v0.4),
2) historię ceny (v0.5).

Nie podejmuje zakupów ani nie wysyła powiadomień.
"""
from dataclasses import dataclass
from decimal import Decimal

from lowca_engine_v03 import Detection, classify_price_change
from lowca_history_v05 import HistoryResult, classify_against_history


@dataclass
class FusionResult:
    level: str
    score: int
    reasons: list[str]
    price_signal: Detection
    history_signal: HistoryResult


def analyze_price(
    old: Decimal,
    new: Decimal,
    history: list[Decimal],
) -> FusionResult:
    price_signal = classify_price_change(old, new)
    history_signal = classify_against_history(history, new)

    score = 0
    reasons: list[str] = []

    price_points = {
        "NORMAL": 0,
        "WATCH": 25,
        "CRITICAL": 100,
    }
    history_points = {
        "NORMAL": 0,
        "WATCH": 35,
        "CRITICAL": 80,
    }

    score += price_points[price_signal.level]
    score += history_points[history_signal.level]

    if price_signal.level != "NORMAL" and history_signal.level != "NORMAL":
        score += 20
        reasons.append("dwa niezależne sygnały wskazują na anomalię")

    if price_signal.level == "CRITICAL":
        reasons.append("silny sygnał strukturalny ceny")

    if history_signal.level == "CRITICAL":
        reasons.append("cena jest ekstremalnie niska względem historii")

    if history_signal.reference_price is not None:
        reasons.append(
            f"mediana historii: {history_signal.reference_price} PLN"
        )

    if score >= 120:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 25:
        level = "WATCH"
    else:
        level = "NORMAL"

    return FusionResult(
        level=level,
        score=score,
        reasons=reasons,
        price_signal=price_signal,
        history_signal=history_signal,
    )


def demo():
    scenarios = [
        (
            "stabilna cena",
            Decimal("7999"), Decimal("7799"),
            [Decimal("7999"), Decimal("7999"), Decimal("7899"), Decimal("7999")],
        ),
        (
            "duża promocja",
            Decimal("7999"), Decimal("3999"),
            [Decimal("7999"), Decimal("7999"), Decimal("7899"), Decimal("7999")],
        ),
        (
            "podejrzany błąd",
            Decimal("7999"), Decimal("799"),
            [Decimal("7999"), Decimal("7999"), Decimal("7899"), Decimal("7999")],
        ),
        (
            "błąd bez historii",
            Decimal("7999"), Decimal("799"),
            [Decimal("7999"), Decimal("7999")],
        ),
    ]

    print("=== ŁOWCA BŁĘDÓW v0.6 — FUSION ===")
    for name, old, new, history in scenarios:
        result = analyze_price(old, new, history)
        print(
            f"{name:20} -> {result.level:8} | score={result.score:3} | "
            f"price={result.price_signal.level:8} | "
            f"history={result.history_signal.level:8}"
        )
        for reason in result.reasons:
            print(f"   - {reason}")


if __name__ == "__main__":
    demo()
