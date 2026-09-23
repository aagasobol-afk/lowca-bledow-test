#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SOURCES = [
    ("BEIKS", "https://beiks.pl/"),
    ("Cyfrowe.pl", "https://www.cyfrowe.pl/"),
    ("E-OKO", "https://e-oko.pl/"),
    ("Foto-Net", "https://foto-net.pl/"),
    ("Morele", "https://www.morele.net/"),
    ("Media Markt", "https://mediamarkt.pl/"),
    ("Martes Sport", "https://martessport.com.pl/"),
    ("eobuwie", "https://eobuwie.com.pl/"),
    ("MODIVO", "https://modivo.pl/"),
    ("Empik", "https://www.empik.com/"),
    ("Neonet", "https://www.neonet.pl/"),
]

HEADERS = {
    "User-Agent": "Lowca-Bledow-source-probe/0.3",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml",
}

PRODUCT_HINTS = (
    "/produkt", "/product", "/p/", "/item", "/obiektyw-", "/aparat-",
    "/telefon-", "/laptop-", "/buty-", "/kurtka-", "/plecak-"
)
CATEGORY_HINTS = (
    "/kategoria", "/category", "/cat/", "/c/", "/szukaj", "/search",
    "/kolekcja", "/collections", "/laptopy", "/aparaty-cyfrowe",
    "/buty", "/kurtki", "/telefony", "/odziez"
)

def parse_product_jsonld(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for tag in soup.find_all("script", attrs={"type": re.compile("ld\+json", re.I)}):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "Product":
                found.append(item)
            elif isinstance(item.get("@type"), list) and "Product" in item.get("@type"):
                found.append(item)
            elif isinstance(item.get("@graph"), list):
                found.extend(
                    x for x in item["@graph"]
                    if isinstance(x, dict)
                    and ("Product" == x.get("@type") or "Product" in (x.get("@type") or []))
                )
    if not found:
        return {}
    item = found[0]
    offers = item.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    return {
        "name": item.get("name"),
        "sku": item.get("sku"),
        "ean": item.get("gtin13") or item.get("gtin"),
        "price": offers.get("price") if isinstance(offers, dict) else None,
        "currency": offers.get("priceCurrency") if isinstance(offers, dict) else None,
        "availability": offers.get("availability") if isinstance(offers, dict) else None,
    }

def extract_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    base_host = urlparse(base_url).netloc
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("#", 1)[0]
        parsed = urlparse(href)
        if parsed.netloc != base_host or href in seen:
            continue
        if href.startswith(("mailto:", "javascript:")):
            continue
        seen.add(href)
        out.append(href)
    return out

def candidate_product_links(base_url: str, html: str) -> list[str]:
    links = extract_links(base_url, html)
    scored = []
    for href in links:
        low = href.lower()
        score = 0
        if any(h in low for h in PRODUCT_HINTS):
            score += 10
        if any(h in low for h in CATEGORY_HINTS):
            score -= 6
        if "?" in href:
            score -= 1
        if score > 0:
            scored.append((score, href))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [href for _, href in scored[:5]]

def discover_product_links(session: requests.Session, base_url: str, homepage_html: str) -> list[str]:
    direct = candidate_product_links(base_url, homepage_html)
    if len(direct) >= 3:
        return direct[:5]

    # One level deeper: many stores expose categories on the homepage,
    # while real product pages are linked from those category pages.
    links = extract_links(base_url, homepage_html)
    category_links = []
    for href in links:
        low = href.lower()
        if any(h in low for h in CATEGORY_HINTS):
            category_links.append(href)
        if len(category_links) >= 8:
            break

    found, seen = [], set(direct)
    for category_url in category_links:
        try:
            r = session.get(category_url, timeout=15, allow_redirects=True)
        except Exception:
            continue
        if r.status_code in {401, 403, 429} or not (200 <= r.status_code < 300):
            continue

        for href in candidate_product_links(r.url, r.text):
            if href not in seen:
                found.append(href)
                seen.add(href)
            if len(found) >= 5:
                break
        if len(found) >= 5:
            break

    return (direct + found)[:5]

def probe(name: str, url: str) -> dict:
    result = {
        "store": name,
        "url": url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "homepage_status": None,
        "product_tests": [],
        "error": None,
    }
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        r = session.get(url, timeout=25, allow_redirects=True)
        result["homepage_status"] = r.status_code
        if r.status_code in {401, 403, 429}:
            result["error"] = f"blocked_http_{r.status_code}"
            return result
        if not (200 <= r.status_code < 300):
            result["error"] = f"http_{r.status_code}"
            return result

        links = discover_product_links(session, r.url, r.text)
        for product_url in links:
            try:
                pr = session.get(product_url, timeout=20, allow_redirects=True)
                item = {
                    "url": product_url,
                    "status": pr.status_code,
                    "blocked": pr.status_code in {401, 403, 429},
                    "json_ld_product": False,
                    "product": None,
                }
                if 200 <= pr.status_code < 300:
                    product = parse_product_jsonld(pr.text)
                    item["json_ld_product"] = bool(product)
                    item["product"] = product or None
                result["product_tests"].append(item)
            except Exception as exc:
                result["product_tests"].append({
                    "url": product_url,
                    "error": f"{type(exc).__name__}: {exc}"
                })
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result

results = [probe(*item) for item in SOURCES]
print(json.dumps(results, ensure_ascii=False, indent=2))
with open("lowca_source_probe_v03.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
