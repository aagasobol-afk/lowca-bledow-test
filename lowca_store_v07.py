#!/usr/bin/env python3
"""Łowca Błędów v0.7 - pamięć produktów i historii cen.

Prototyp używa SQLite. To jeszcze nie jest baza produkcyjna 24/7,
ale mamy już trwały model danych: produkt -> sklep -> kolejne pomiary ceny.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional


@dataclass
class Product:
    id: int
    name: str
    store: str
    url: str
    ean: Optional[str]
    sku: Optional[str]


@dataclass
class PricePoint:
    id: int
    product_id: int
    price: Decimal
    available: bool
    checked_at: str


class PriceStore:
    def __init__(self, db_path: str | Path = ":memory:"):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                store TEXT NOT NULL,
                url TEXT NOT NULL,
                ean TEXT,
                sku TEXT,
                UNIQUE(store, url)
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                price NUMERIC NOT NULL,
                available INTEGER NOT NULL DEFAULT 1,
                checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(product_id) REFERENCES products(id)
            );

            CREATE INDEX IF NOT EXISTS idx_price_history_product_time
            ON price_history(product_id, checked_at);
            """
        )
        self.conn.commit()

    def upsert_product(
        self,
        name: str,
        store: str,
        url: str,
        ean: Optional[str] = None,
        sku: Optional[str] = None,
    ) -> Product:
        self.conn.execute(
            """
            INSERT INTO products(name, store, url, ean, sku)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(store, url) DO UPDATE SET
                name=excluded.name,
                ean=COALESCE(excluded.ean, products.ean),
                sku=COALESCE(excluded.sku, products.sku)
            """,
            (name, store, url, ean, sku),
        )
        self.conn.commit()

        row = self.conn.execute(
            "SELECT * FROM products WHERE store=? AND url=?",
            (store, url),
        ).fetchone()
        return Product(
            id=row["id"],
            name=row["name"],
            store=row["store"],
            url=row["url"],
            ean=row["ean"],
            sku=row["sku"],
        )

    def record_price(
        self,
        product_id: int,
        price: Decimal,
        available: bool = True,
        checked_at: Optional[str] = None,
    ) -> PricePoint:
        if price <= 0:
            raise ValueError("Cena musi być większa od zera.")

        if checked_at is None:
            row = self.conn.execute(
                """
                INSERT INTO price_history(product_id, price, available)
                VALUES (?, ?, ?)
                RETURNING *
                """,
                (product_id, str(price), int(available)),
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                INSERT INTO price_history(product_id, price, available, checked_at)
                VALUES (?, ?, ?, ?)
                RETURNING *
                """,
                (product_id, str(price), int(available), checked_at),
            ).fetchone()

        self.conn.commit()
        return PricePoint(
            id=row["id"],
            product_id=row["product_id"],
            price=Decimal(str(row["price"])),
            available=bool(row["available"]),
            checked_at=row["checked_at"],
        )

    def get_history(self, product_id: int) -> list[Decimal]:
        rows = self.conn.execute(
            """
            SELECT price FROM price_history
            WHERE product_id=?
            ORDER BY checked_at ASC, id ASC
            """,
            (product_id,),
        ).fetchall()
        return [Decimal(str(row["price"])) for row in rows]

    def get_latest(self, product_id: int) -> Optional[PricePoint]:
        row = self.conn.execute(
            """
            SELECT * FROM price_history
            WHERE product_id=?
            ORDER BY checked_at DESC, id DESC
            LIMIT 1
            """,
            (product_id,),
        ).fetchone()
        if row is None:
            return None
        return PricePoint(
            id=row["id"],
            product_id=row["product_id"],
            price=Decimal(str(row["price"])),
            available=bool(row["available"]),
            checked_at=row["checked_at"],
        )

    def close(self):
        self.conn.close()


def demo():
    store = PriceStore()

    product = store.upsert_product(
        name="Sony A7 IV body - ILCE7M4B",
        store="Fotoforma",
        url="https://fotoforma.pl/aparat-cyfrowy-sony-a7-iv-body-ilce7m4b",
        ean="4548736133754",
        sku="ILCE7M4B",
    )

    for price in ("7999", "7999", "7899", "7999", "799"):
        store.record_price(product.id, Decimal(price))

    print("=== ŁOWCA BŁĘDÓW v0.7 — PAMIĘĆ PRODUKTU ===")
    print("Produkt:", product.name)
    print("Sklep:", product.store)
    print("EAN:", product.ean)
    print("SKU:", product.sku)
    print("Historia:", store.get_history(product.id))
    print("Ostatnia cena:", store.get_latest(product.id).price)
    store.close()


if __name__ == "__main__":
    demo()
