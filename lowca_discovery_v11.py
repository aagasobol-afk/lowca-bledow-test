#!/usr/bin/env python3
"""Łowca Błędów v1.1 — automatyczne wyszukiwanie publicznych stron produktów."""
from __future__ import annotations

from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SOURCES = [
    ("BEIKS", "https://beiks.pl/"),
    ("Cyfrowe.pl", "https://www.cyfrowe.pl/"),
    ("Foto-Net", "https://foto-net.pl/"),
    ("Morele", "https://www.morele.net/"),
    ("Media Markt", "https://mediamarkt.pl/"),
    ("Martes Sport", "https://martessport.com.pl/"),
    ("eobuwie", "https://eobuwie.com.pl/"),
    ("MODIVO", "https://modivo.pl/"),
    ("Empik", "https://www.empik.com/"),
    ("Neonet", "https://www.neonet.pl/"),
]

PRODUCT_HINTS = (
    "/produkt", "/product", "/p/", "/item", "/obiektyw-", "/aparat-",
    "/telefon-", "/laptop-", "/buty-", "/kurtka-", "/plecak-"
)
CATEGORY_HINTS = (
    "/kategoria", "/category", "/cat/", "/c/", "/szukaj", "/search",
    "/kolekcja", "/collections", "/laptopy", "/aparaty-cyfrowe",
    "/buty", "/kurtki", "/telefony", "/odziez"
)
MAX_PRODUCTS_PER_STORE = 5
MAX_CATEGORY_PAGES = 6

HEADERS = {
    "User-Agent": "Lowca-Bledow/1.1 public-product-discovery",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml",
}

def same_host(a: str, b: str) -> bool:
    return urlparse(a).netloc == urlparse(b).netloc

def extract_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("#", 1)[0]
        if not same_host(base_url, href) or href in seen:
            continue
        if href.startswith(("mailto:", "javascript:")):
            continue
        seen.add(href)
        out.append(href)
    return out

def score_product_link(url: str) -> int:
    low = url.lower()
    score = 0
    if any(h in low for h in PRODUCT_HINTS):
        score += 10
    if any(h in low for h in CATEGORY_HINTS):
        score -= 7
    if "?" in url:
        score -= 1
    if url.count("/") >= 4:
        score += 1
    return score

def candidate_product_links(base_url: str, html: str) -> list[str]:
    scored = [(score_product_link(u), u) for u in extract_links(base_url, html)]
    scored = [(s, u) for s, u in scored if s > 0]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [u for _, u in scored[:MAX_PRODUCTS_PER_STORE]]

def discover_store(session: requests.Session, store: str, home_url: str) -> list[tuple[str, str]]:
    try:
        r = session.get(home_url, timeout=20, allow_redirects=True)
    except Exception as exc:
        print(f"{store}: discovery ERROR {type(exc).__name__}: {exc}")
        return []
    if r.status_code in {401, 403, 429}:
        print(f"{store}: pomijam blokadę HTTP {r.status_code}")
        return []
    if not 200 <= r.status_code < 300:
        print(f"{store}: pomijam HTTP {r.status_code}")
        return []

    found, seen = [], set()
    for u in candidate_product_links(r.url, r.text):
        if u not in seen:
            found.append((store, u))
            seen.add(u)

    links = extract_links(r.url, r.text)
    categories = []
    for u in links:
        low = u.lower()
        if any(h in low for h in CATEGORY_HINTS) and u not in categories:
            categories.append(u)
        if len(categories) >= MAX_CATEGORY_PAGES:
            break

    for category_url in categories:
        if len(found) >= MAX_PRODUCTS_PER_STORE:
            break
        try:
            cr = session.get(category_url, timeout=15, allow_redirects=True)
        except Exception:
            continue
        if cr.status_code in {401, 403, 429} or not 200 <= cr.status_code < 300:
            continue
        for u in candidate_product_links(cr.url, cr.text):
            if u not in seen:
                found.append((store, u))
                seen.add(u)
            if len(found) >= MAX_PRODUCTS_PER_STORE:
                break

    print(f"{store}: znaleziono {len(found)} kandydatów")
    return found[:MAX_PRODUCTS_PER_STORE]

def discover_all() -> list[tuple[str, str]]:
    session = requests.Session()
    session.headers.update(HEADERS)
    out, seen = [], set()
    for store, home_url in SOURCES:
        for item in discover_store(session, store, home_url):
            if item[1] not in seen:
                out.append(item)
                seen.add(item[1])
    return out

if __name__ == "__main__":
    for store, url in discover_all():
        print(store, url)
