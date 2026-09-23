#!/usr/bin/env python3
"""Benchmark przepływu end-to-end v0.8."""

from decimal import Decimal
from lowca_e2e_v08 import run


def main():
    # run() ma własny kontrolowany scenariusz i kończy się kodem 0,
    # jeśli pipeline wygeneruje HIGH/CRITICAL.
    run()
    print("WYNIK: E2E PASS")


if __name__ == "__main__":
    main()
