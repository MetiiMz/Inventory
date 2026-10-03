# -*- coding: utf-8 -*-
"""Shared test helpers — factories for products/sales and common payloads."""
import datetime

from inventory.jalali import gregorian_to_jalali
from inventory.models import Product


def today_iso():
    """Today as an ISO date string."""
    return datetime.date.today().isoformat()


def today_jalali():
    """Today as a (jy, jm, jd) tuple."""
    d = datetime.date.today()
    return gregorian_to_jalali(d.year, d.month, d.day)


def make_product(**overrides):
    """Create a Product with valid defaults (office/website codes unique)."""
    seq = Product.objects.count() + int(datetime.datetime.now().timestamp() % 100000)
    fields = {
        "name": "Test Watch",
        "office_code": f"OF-{seq}",
        "website_code": f"WS-{seq}",
        "purchase_price": 1_000_000.0,
        "sale_price": 1_500_000.0,
        "purchase_date": today_iso(),
        "brand": "",
        "supplier": "",
        "reference": "",
        "notes": "",
        "image": "",
    }
    fields.update(overrides)
    return Product.objects.create(**fields)


def product_payload(**overrides):
    """A valid JSON payload for the product create endpoints."""
    seq = int(datetime.datetime.now().timestamp() % 1000000)
    payload = {
        "name": "Payload Watch",
        "office_code": f"OF-P{seq}",
        "website_code": f"WS-P{seq}",
        "purchase_price": "2000000",
        "sale_price": "3000000",
    }
    payload.update(overrides)
    return payload


def sale_payload(product_id, **overrides):
    """A valid JSON payload for sale creation (cash by default)."""
    payload = {
        "product_id": product_id,
        "sale_price": "1500000",
        "payment_type": "cash",
        "customer": "علی",
        "customer_phone": "09123456789",
    }
    payload.update(overrides)
    return payload
