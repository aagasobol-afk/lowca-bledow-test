#!/usr/bin/env python3
"""Łowca Błędów v1.2 — automatyczne wyszukiwanie i walidacja stron produktów."""
from __future__ import annotations

import json
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

MAX_PRODUCTS_PER_STORE = 8
MAX_CATEGORY_PAGES = 10
MAX_VALIDATION_CANDIDATES = 18

HEADERS = {
    "User-Agent": "Lowca-Bledow/1.2 public-product-discovery",
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
        score -= 10
    if any(x in low for x in ("/pomoc", "/regulamin", "/dostawa", "/konto", "/blog", "/campaign")):
        score -= 20
    if "?" in url:
        score -= 1
    if url.count("/") >= 4:
        score += 1
    return score

def candidate_product_links(base_url: str, html: str) -> list[str]:
    scored = [(score_product_link(u), u) for u in extract_links(base_url, html)]
    scored = [(s, u) for s, u in scored if s > 0]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [u for _, u in scored[:MAX_VALIDATION_CANDIDATES]]

def has_product_jsonld(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text()
        try:
            data = json.loads(raw)
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if isinstance(node, dict):
                if node.get("@type") == "Product":
                    return True
                graph = node.get("@graph")
                if isinstance(graph, list) and any(
                    isinstance(x, dict) and x.get("@type") == "Product" for x in graph
                ):
                    return True
    return False

def validate_product(session: requests.Session, url: str) -> bool:
    try:
        r = session.get(url, timeout=12, allow_redirects=True)
    except Exception:
        return False
    if r.status_code in {401, 403, 429} or not 200 <= r.status_code < 300:
        return False
    return has_product_jsonld(r.text)

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
    candidate_urls = candidate_product_links(r.url, r.text)

    links = extract_links(r.url, r.text)
    categories = []
    for u in links:
        low = u.lower()
        if any(h in low for h in CATEGORY_HINTS) and u not in categories:
            categories.append(u)
        if len(categories) >= MAX_CATEGORY_PAGES:
            break

    for category_url in categories:
        if len(candidate_urls) >= MAX_VALIDATION_CANDIDATES:
            break
        try:
            cr = session.get(category_url, timeout=15, allow_redirects=True)
        except Exception:
            continue
        if cr.status_code in {401, 403, 429} or not 200 <= cr.status_code < 300:
            continue
        candidate_urls.extend(candidate_product_links(cr.url, cr.text))

    for url in candidate_urls:
        if len(found) >= MAX_PRODUCTS_PER_STORE:
            break
        if url in seen:
            continue
        seen.add(url)
        if validate_product(session, url):
            found.append((store, url))

    print(f"{store}: znaleziono {len(found)} prawdziwych produktów")
    return found

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
