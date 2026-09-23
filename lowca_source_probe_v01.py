#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

SOURCES = [
    ("BEIKS", "https://beiks.pl/"),
    ("Cyfrowe.pl", "https://www.cyfrowe.pl/"),
    ("E-OKO", "https://e-oko.pl/"),
    ("Foto-Net", "https://foto-net.pl/"),
    ("Komputronik", "https://www.komputronik.pl/"),
    ("x-kom", "https://www.x-kom.pl/"),
    ("Morele", "https://www.morele.net/"),
    ("RTV Euro AGD", "https://www.euro.com.pl/"),
    ("Media Markt", "https://mediamarkt.pl/"),
    ("Zalando", "https://www.zalando.pl/"),
    ("8a.pl", "https://8a.pl/"),
    ("Martes Sport", "https://martessport.com.pl/"),
    ("eobuwie", "https://eobuwie.com.pl/"),
    ("MODIVO", "https://modivo.pl/"),
    ("Decathlon", "https://www.decathlon.pl/"),
    ("Allegro", "https://allegro.pl/"),
    ("Empik", "https://www.empik.com/"),
    ("Neonet", "https://www.neonet.pl/"),
    ("OleOle", "https://www.oleole.pl/"),
]

HEADERS = {
    "User-Agent": "Lowca-Bledow-source-probe/0.1",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml",
}

def probe(name: str, url: str) -> dict:
    result = {
        "store": name,
        "url": url,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": None,
        "ok": False,
        "blocked": False,
        "json_ld": False,
        "bytes": 0,
        "error": None,
    }
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        text = r.text[:2_000_000]
        result["status"] = r.status_code
        result["ok"] = 200 <= r.status_code < 300
        result["blocked"] = r.status_code in {401, 403, 429}
        result["bytes"] = len(r.content)
        result["json_ld"] = 'application/ld+json' in text.lower() and '"@type"' in text
        result["final_url"] = r.url
        result["host"] = urlparse(r.url).netloc
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result

results = [probe(*item) for item in SOURCES]
print(json.dumps(results, ensure_ascii=False, indent=2))
with open("lowca_source_probe.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
