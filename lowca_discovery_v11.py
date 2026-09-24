#!/usr/bin/env python3
"""Łowca Błędów — katalog źródeł i odkrywanie publicznych produktów."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Katalog jest szeroki celowo. Sklep może zostać pominięty, jeśli blokuje automatyczny
# dostęp albo nie udostępnia czytelnych publicznych danych produktu. Nie obchodzimy blokad.
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
    ("Komputronik", "https://www.komputronik.pl/"),
    ("x-kom", "https://www.x-kom.pl/"),
    ("RTV Euro AGD", "https://www.euro.com.pl/"),
    ("Media Expert", "https://www.mediaexpert.pl/"),
    ("OleOle", "https://www.oleole.pl/"),
    ("Decathlon", "https://www.decathlon.pl/"),
    ("8a.pl", "https://8a.pl/"),
    ("Ceneo", "https://www.ceneo.pl/"),
    ("Sferis", "https://www.sferis.pl/"),
    ("Mediaarena", "https://www.mediaarena.pl/"),
    ("Newegg PL", "https://www.newegg.com/global/pl-en/"),
    ("Zalando", "https://www.zalando.pl/"),
    ("CCC", "https://ccc.eu/pl/"),
    ("Reserved", "https://www.reserved.com/pl/pl/"),
    ("Sinsay", "https://www.sinsay.com/pl/pl/"),
    ("4F", "https://4f.com.pl/"),
    ("Sizeer", "https://sizeer.com/"),
    ("Answear", "https://answear.com/"),
    ("Born2be", "https://born2be.pl/"),
    ("Renee", "https://renee.pl/"),
    ("Wittchen", "https://wittchen.com/"),
    ("DOZ", "https://www.doz.pl/"),
    ("Super-Pharm", "https://www.superpharm.pl/"),
    ("Notino", "https://www.notino.pl/"),
    ("Ziko", "https://www.ziko.pl/"),
    ("MediaMarkt Austria", "https://www.mediamarkt.at/"),
    ("Amazon PL", "https://www.amazon.pl/"),
    ("Allegro", "https://allegro.pl/"),
    ("Empik Foto", "https://www.empikfoto.pl/"),
]

PRODUCT_HINTS = (
    "/produkt", "/product", "/p/", "/item", "/products/", "/product/",
    "/obiektyw-", "/aparat-", "/telefon-", "/laptop-", "/buty-",
    "/kurtka-", "/plecak-", "/p/produkt-", "/towar/"
)
CATEGORY_HINTS = (
    "/kategoria", "/category", "/cat/", "/c/", "/szukaj", "/search",
    "/kolekcja", "/collections", "/laptopy", "/aparaty-cyfrowe",
    "/buty", "/kurtki", "/telefony", "/odziez", "/category/",
    "/collections/"
)
BAD_HINTS = (
    "/pomoc", "/regulamin", "/dostawa", "/konto", "/blog", "/campaign",
    "/kontakt", "/newsletter", "/polityka", "/faq", "/login", "/rejestracja",
    "/cookies", "/mapa-strony"
)

MAX_PRODUCTS_PER_STORE = 100
MAX_CATEGORY_PAGES = 25
MAX_VALIDATION_CANDIDATES = 200
MAX_SITEMAP_URLS = 350

HEADERS = {
    "User-Agent": "Lowca-Bledow/1.4 public-product-discovery",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml",
}

def same_host(a: str, b: str) -> bool:
    return urlparse(a).netloc == urlparse(b).netloc

def clean_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href).split("#", 1)[0]

def is_relevant_url(url: str) -> bool:
    low = url.lower()
    return (
        url.startswith(("http://", "https://"))
        and not any(h in low for h in BAD_HINTS)
        and not any(h in low for h in CATEGORY_HINTS)
    )

def extract_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = clean_url(base_url, a["href"])
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
        score += 12
    if any(h in low for h in CATEGORY_HINTS):
        score -= 30
    if any(h in low for h in BAD_HINTS):
        score -= 25
    if "?" in url:
        score -= 1
    if url.count("/") >= 4:
        score += 1
    return score

def _jsonld_nodes(html: str):
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
                yield node

def candidate_product_links(base_url: str, html: str) -> list[str]:
    links = extract_links(base_url, html)
    for node in _jsonld_nodes(html):
        items = node.get("itemListElement")
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                target = item.get("url")
                if not target and isinstance(item.get("item"), dict):
                    target = item["item"].get("url")
                if isinstance(target, str):
                    links.append(clean_url(base_url, target))
    scored = [(score_product_link(u), u) for u in links]
    scored = [
        (s, u) for s, u in scored
        if s > 0 and is_relevant_url(u)
    ]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [u for _, u in scored[:MAX_VALIDATION_CANDIDATES]]

def has_product_jsonld(html: str) -> bool:
    for node in _jsonld_nodes(html):
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
        r = session.get(url, timeout=10, allow_redirects=True)
    except Exception:
        return False
    if r.status_code in {401, 403, 429} or not 200 <= r.status_code < 300:
        return False
    return has_product_jsonld(r.text)

def sitemap_candidates(session: requests.Session, home_url: str) -> list[str]:
    root = f"{urlparse(home_url).scheme}://{urlparse(home_url).netloc}"
    sitemap_urls = [urljoin(root, "/sitemap.xml")]
    try:
        rr = session.get(urljoin(root, "/robots.txt"), timeout=10)
        if 200 <= rr.status_code < 300:
            for line in rr.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    u = line.split(":", 1)[1].strip()
                    if u.startswith("http") and u not in sitemap_urls:
                        sitemap_urls.append(u)
    except Exception:
        pass

    found = []
    for sm in sitemap_urls[:8]:
        try:
            r = session.get(sm, timeout=12)
        except Exception:
            continue
        if r.status_code in {401, 403, 429} or not 200 <= r.status_code < 300:
            continue
        soup = BeautifulSoup(r.text, "xml")
        locs = [loc.get_text(strip=True) for loc in soup.find_all("loc")]
        for u in locs:
            low = u.lower()
            if any(h in low for h in PRODUCT_HINTS) and is_relevant_url(u):
                found.append(u)
            elif u.lower().endswith(".xml") and len(found) < MAX_SITEMAP_URLS:
                try:
                    sr = session.get(u, timeout=10)
                    if 200 <= sr.status_code < 300:
                        ss = BeautifulSoup(sr.text, "xml")
                        for loc in ss.find_all("loc"):
                            v = loc.get_text(strip=True)
                            if any(h in v.lower() for h in PRODUCT_HINTS) and is_relevant_url(v):
                                found.append(v)
                                if len(found) >= MAX_SITEMAP_URLS:
                                    break
                except Exception:
                    continue
            if len(found) >= MAX_SITEMAP_URLS:
                return found[:MAX_SITEMAP_URLS]
    return found[:MAX_SITEMAP_URLS]

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
    candidate_urls.extend(sitemap_candidates(session, r.url))

    links = extract_links(r.url, r.text)
    categories = []
    for u in links:
        low = u.lower()
        if any(h in low for h in CATEGORY_HINTS) and not any(h in low for h in BAD_HINTS):
            if u not in categories:
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

def registry_sources() -> list[tuple[str, str]]:
    path = Path("lowca_source_registry_v01.json")
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for item in data.get("sources", []):
        if not isinstance(item, dict) or item.get("status") != "active":
            continue
        name = item.get("name")
        url = item.get("url")
        if isinstance(name, str) and isinstance(url, str) and url.startswith(("http://", "https://")):
            out.append((name, url))
    return out


def discover_all() -> list[tuple[str, str]]:
    session = requests.Session()
    session.headers.update(HEADERS)
    out, seen = [], set()
    source_seen = set()
    for store, home_url in SOURCES + registry_sources():
        source_key = (store, home_url)
        if source_key in source_seen:
            continue
        source_seen.add(source_key)
        for item in discover_store(session, store, home_url):
            if item[1] not in seen:
                out.append(item)
                seen.add(item[1])
    return out

if __name__ == "__main__":
    for store, url in discover_all():
        print(store, url)
