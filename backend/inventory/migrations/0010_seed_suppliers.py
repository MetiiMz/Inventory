# -*- coding: utf-8 -*-
"""K1: pre-fill the managed supplier list from suppliers already in use.

Every distinct, non-empty, stripped ``Product.supplier`` value becomes a
Setting row under ``supplier:<name>`` (``get_or_create`` → idempotent), so
upgrading shops see their existing suppliers in the settings list right away.
The product model itself is untouched: ``Product.supplier`` stays a free-text
field, so old data, Excel import/export and API clients keep working.

Reverse is a no-op (nothing to undo).
"""
from django.db import migrations


def seed_suppliers(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    Setting = apps.get_model("inventory", "Setting")
    names = {
        (product.supplier or "").strip()
        for product in Product.objects.exclude(supplier="").exclude(
            supplier__isnull=True
        ).iterator()
    }
    for name in sorted(name for name in names if name):
        Setting.objects.get_or_create(
            key="supplier:" + name, defaults={"value": name}
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0009_backfill_sale_invoice_codes"),
    ]

    operations = [
        migrations.RunPython(seed_suppliers, noop),
    ]
