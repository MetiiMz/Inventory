# -*- coding: utf-8 -*-
"""B1: backfill invoice_code for sales created before persistence.

Auto codes were previously derived at display time from ``sale_date``, so
editing a date changed the code. From now on the code is stored at
creation; existing sales with an empty code get one derived from their
current ``sale_date`` — making every code permanent.
"""
from django.db import migrations

from inventory.jalali import gregorian_to_jalali


def _code(sale_id, sale_date):
    """Same format as inventory.utils.invoice_code (frozen copy)."""
    try:
        y, m, d = (int(x) for x in str(sale_date)[:10].split("-"))
        jy, jm, _jd = gregorian_to_jalali(y, m, d)
        return f"TT-{jy}{jm:02d}-{sale_id:04d}"
    except (ValueError, TypeError):
        return f"TT-{sale_id:04d}"


def backfill_sale_codes(apps, schema_editor):
    Sale = apps.get_model("inventory", "Sale")
    for sale in (Sale.objects.filter(invoice_code="")
                 .only("id", "sale_date", "invoice_code").iterator()):
        sale.invoice_code = _code(sale.id, sale.sale_date)
        sale.save(update_fields=["invoice_code"])


def unbackfill(apps, schema_editor):
    """Codes are derived from sale data; nothing to revert."""


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0008_remove_product_sale_price"),
    ]

    operations = [
        migrations.RunPython(backfill_sale_codes, unbackfill),
    ]
