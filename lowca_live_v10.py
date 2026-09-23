#!/usr/bin/env python3
"""Łowca Błędów v1.0 — wielosklepowy monitor cen."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from lowca_fusion_v06 import analyze_price
from lowca_public_product_v10 import fetch_public_product, snapshot_dict

STATE_FILE = Path(os.getenv("LOWCA_STATE_FILE", "lowca_live_state_v10.json"))
ALERT_FILE = Path(os.getenv("LOWCA_ALERT_FILE", "lowca_alert_v10.json"))
MAX_HISTORY = 30
MEGA_SALE_RATIO = Decimal("0.30")
PRODUCTS = [
    ("Cyfrowe.pl", "https://www.cyfrowe.pl/aparat-om-system-pen-srebrny-p.html"),
    ("Cyfrowe.pl", "https://www.cyfrowe.pl/obiektyw-sony-fe-600-mm-f-6-3-gm-p.html"),
    ("Cyfrowe.pl", "https://www.cyfrowe.pl/obiektyw-sony-fe-8-14-mm-f-3-5-sel814gb-syx-p.html"),
    ("Foto-Net", "https://foto-net.pl/aparat-Canon-EOS-2000D-BODY-uzywany-WB001.html"),
    ("Foto-Net", "https://foto-net.pl/aparat-Canon-EOS-R50-18-45-uzywany-WB001.html"),
    ("Foto-Net", "https://foto-net.pl/aparat-Nikon-Z5-BODY-uzywany-WB001.html"),
    ("Neonet", "https://www.neonet.pl/p/1073505-zelazko-tefal-easygliss-plus-2-fv5718.html"),
    ("Neonet", "https://www.neonet.pl/p/1144085-kierownica-do-konsol-logitech-g29-shifter-pc-ps3-ps4-ps5.html"),
    ("Neonet", "https://www.neonet.pl/p/1169968-ekspres-automatyczny-siemens-te653311rw-eq6-plus.html"),
]

def load_state():
    if not STATE_FILE.exists(): return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    state, alerts, checked = load_state(), [], 0
    for store, url in PRODUCTS:
        try:
            snapshot = fetch_public_product(url, store); checked += 1
            key = f"{store}|{url}"; previous = state.get(key, {})
            history = [Decimal(str(p)) for p in previous.get("history", []) if Decimal(str(p)) > 0]
            old_price = Decimal(str(previous["price"])) if previous.get("price") else None
            result = analyze_price(old_price, snapshot.price, history) if old_price is not None and old_price != snapshot.price else None
            ratio = snapshot.price / old_price if old_price and old_price > 0 else None
            mega_sale = ratio is not None and ratio <= MEGA_SALE_RATIO
            signature, alert_record = None, None
            if mega_sale:
                signature = f"{url}|MEGA_SALE|{snapshot.price}"
                alert_record = {"type":"LOWCA_DEAL","level":"MEGA_OKAZJA","score":0,"product":snapshot.name,"store":store,"price_old":str(old_price),"price_new":str(snapshot.price),"currency":snapshot.currency,"reduction_percent":str((Decimal("1")-ratio)*100),"url":url,"ean":snapshot.ean,"sku":snapshot.sku,"reasons":["spadek ceny o co najmniej 70% względem poprzedniego odczytu"],"checked_at":datetime.now(timezone.utc).isoformat()}
            elif result and result.level in {"HIGH","CRITICAL"}:
                signature = f"{url}|{result.level}|{snapshot.price}"
                alert_record = {"type":"LOWCA_ALERT","level":result.level,"score":result.score,"product":snapshot.name,"store":store,"price_old":str(old_price),"price_new":str(snapshot.price),"currency":snapshot.currency,"url":url,"ean":snapshot.ean,"sku":snapshot.sku,"reasons":result.reasons,"checked_at":datetime.now(timezone.utc).isoformat()}
            old_signature = previous.get("last_alert_signature")
            if alert_record is not None and signature != old_signature:
                alerts.append(alert_record)
            history = (history + [snapshot.price])[-MAX_HISTORY:]
            state[key] = {**snapshot_dict(snapshot),"history":[str(p) for p in history],"last_alert_signature":signature if signature != old_signature else old_signature,"checked_at":datetime.now(timezone.utc).isoformat()}
            print(f"{store}: {snapshot.name} | {snapshot.price} {snapshot.currency} | old={old_price} | mega={mega_sale} | level={result.level if result else 'NORMAL'}")
        except Exception as exc:
            print(f"{store}: ERROR | {url} | {type(exc).__name__}: {exc}")
    ALERT_FILE.unlink(missing_ok=True)
    if alerts:
        ALERT_FILE.write_text(json.dumps(alerts[0], ensure_ascii=False, indent=2), encoding="utf-8")
        print("NOWY_ALERT:", alerts[0]["type"], alerts[0]["level"], alerts[0]["product"])
    else: print("BRAK_NOWYCH_ALARMÓW")
    save_state(state); print(f"Sprawdzono poprawnie: {checked}/{len(PRODUCTS)}"); return 0

if __name__ == "__main__": raise SystemExit(main())
