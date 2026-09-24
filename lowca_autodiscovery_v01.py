#!/usr/bin/env python3
"""Łowca Błędów — samodzielne odkrywanie nowych publicznych sklepów."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

REGISTRY_FILE = Path("lowca_source_registry_v01.json")
MAX_NEW_SOURCES = 15
SEARCH_RESULTS_PER_QUERY = 20
TIMEOUT = 12

QUERIES = [
    "sklep internetowy elektronika aparaty obiektywy Polska",
    "sklep internetowy laptopy telefony elektronika Polska",
    "sklep internetowy buty odzież sportowa outdoor Polska",
    "sklep internetowy dom ogród meble wyposażenie Polska",
    "sklep internetowy kosmetyki perfumy Polska",
    "sklep internetowy fotografia sprzęt foto Polska",
    "sklep internetowy AGD RTV Polska",
    "sklep internetowy rowery turystyka góry outdoor Polska",
    "sklep internetowy meble wnętrza dom ogród Polska",
    "sklep internetowy zegarki biżuteria Polska",
    "sklep internetowy dzieci zabawki Polska",
]

BLOCKED_HOST_PARTS = (
    "google.", "bing.", "duckduckgo.", "facebook.", "instagram.", "youtube.",
    "tiktok.", "wikipedia.", "allegro.", "ceneo.", "amazon."
)

HEADERS = {
    "User-Agent": "Lowca-Bledow/1.5 public-store-discovery",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.7",
}


def load_registry() -> dict:
    if not REGISTRY_FILE.exists():
        return {"sources": []}
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"sources": []}
    except Exception:
        return {"sources": []}


def save_registry(registry: dict) -> None:
    REGISTRY_FILE.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def unwrap_result(href: str) -> str:
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc:
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if target:
            return target
    return href


def search_public_web(session: requests.Session, query: str) -> list[str]:
    engines = [
        ("https://lite.duckduckgo.com/lite/?q=", "ddg-lite"),
        ("https://www.google.com/search?q=", "google"),
        ("https://www.bing.com/search?q=", "bing"),
    ]
    for base, engine in engines:
        url = base + quote_plus(query)
        try:
            response = session.get(url, timeout=TIMEOUT)
        except Exception as exc:
            print(f"AUTO: {engine} niedostępna: {type(exc).__name__}")
            continue
        if response.status_code in {401, 403, 429}:
            print(f"AUTO: {engine} odmówiła dostępu HTTP {response.status_code}")
            continue
        if not 200 <= response.status_code < 300:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        urls, seen = [], set()
        for a in soup.find_all("a", href=True):
            target = unwrap_result(a.get("href", ""))
            if target.startswith("/url?"):
                target = unwrap_result("https://www.google.com" + target)
            if not target.startswith(("http://", "https://")):
                continue
            host = (urlparse(target).hostname or "").lower()
            if not host or any(part in host for part in BLOCKED_HOST_PARTS):
                continue
            if target in seen:
                continue
            seen.add(target)
            urls.append(target)
            if len(urls) >= SEARCH_RESULTS_PER_QUERY:
                break
        if urls:
            return urls
    return []

def host_from_url(url: str) -> str | None:
    try:
        host = (urlparse(url).hostname or "").lower().strip(".")
    except Exception:
        return None
    if not host or any(part in host for part in BLOCKED_HOST_PARTS):
        return None
    if host.startswith("www."):
        host = host[4:]
    return host


def is_candidate_store(url: str) -> bool:
    host = host_from_url(url)
    if not host:
        return False
    path = urlparse(url).path.lower()
    return (
        not any(x in path for x in ("/blog", "/aktualnosci", "/kontakt", "/regulamin"))
        and "." in host
    )


def validate_public_store(session: requests.Session, url: str) -> bool:
    try:
        response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    except Exception:
        return False
    if response.status_code in {401, 403, 429}:
        return False
    if not 200 <= response.status_code < 300:
        return False

    soup = BeautifulSoup(response.text, "html.parser")
    # Szukamy publicznych danych produktu. Nie obchodzimy zabezpieczeń.
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text()
        try:
            data = json.loads(raw)
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("@type") == "Product":
                return True
            graph = node.get("@graph")
            if isinstance(graph, list) and any(
                isinstance(x, dict) and x.get("@type") == "Product" for x in graph
            ):
                return True

    text = soup.get_text(" ", strip=True).lower()
    price_markers = (" zł", " pln", " cena", "koszyk", "dodaj do koszyka")
    return any(marker in text for marker in price_markers)


def discover_new_sources() -> list[tuple[str, str]]:
    registry = load_registry()
    known_hosts = {
        host_from_url(item.get("url", ""))
        for item in registry.get("sources", [])
        if isinstance(item, dict)
    }
    known_hosts.discard(None)

    session = requests.Session()
    session.headers.update(HEADERS)
    candidates: dict[str, str] = {}

    for query in QUERIES:
        for url in search_public_web(session, query):
            host = host_from_url(url)
            if not host or host in known_hosts or not is_candidate_store(url):
                continue
            candidates.setdefault(host, f"https://{host}/")

    print(f"AUTO: kandydatów po wyszukiwaniu: {len(candidates)}")
    accepted: list[tuple[str, str]] = []
    for host, url in candidates.items():
        if len(accepted) >= MAX_NEW_SOURCES:
            break
        if validate_public_store(session, url):
            name = host.split(".")[0].replace("-", " ").title()
            accepted.append((name, url))
            known_hosts.add(host)
            registry.setdefault("sources", []).append(
                {"name": name, "url": url, "status": "active"}
            )
            print(f"AUTO: dodano nowe źródło: {name} -> {url}")
        else:
            print(f"AUTO: odrzucono źródło: {url}")

    save_registry(registry)
    print(f"AUTO: nowych źródeł w tej rundzie: {len(accepted)}")
    return accepted


if __name__ == "__main__":
    discover_new_sources()
