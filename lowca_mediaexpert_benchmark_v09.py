#!/usr/bin/env python3
"""Benchmark parsera Media Expert v0.9 na kontrolowanym HTML."""

from lowca_mediaexpert_v09 import _first_product_jsonld, _price, _available


FIXTURE = r'''
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "SONY Alpha A7 IV",
  "sku": "475671",
  "gtin13": "4548736133754",
  "offers": {
    "@type": "Offer",
    "price": "7999.00",
    "priceCurrency": "PLN",
    "availability": "https://schema.org/InStock"
  }
}
</script>
'''


def run():
    product = _first_product_jsonld(FIXTURE)
    assert product is not None
    assert product["name"] == "SONY Alpha A7 IV"
    assert product["sku"] == "475671"
    assert product["gtin13"] == "4548736133754"

    offers = product["offers"]
    assert _price(offers["price"]) == 7999
    assert _available(offers["availability"]) is True

    assert _price("7 999,00 zł") == 7999
    assert _price("799,90") == 799.90
    assert _available("https://schema.org/OutOfStock") is False

    print("=== ŁOWCA BŁĘDÓW v0.9 — MEDIA EXPERT ADAPTER ===")
    print("JSON-LD Product: OK")
    print("Cena / waluta: OK")
    print("SKU / EAN: OK")
    print("Dostępność: OK")
    print("WYNIK: 100% OK")


if __name__ == "__main__":
    run()
