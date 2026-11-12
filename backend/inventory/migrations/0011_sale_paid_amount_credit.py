# -*- coding: utf-8 -*-
"""M1: settle / deposit / credit sale — replace the three payment buckets.

Adds ``Sale.paid_amount`` (the single amount paid so far, backfilled from
``paid_cash + paid_pos + paid_card2card``), ``Sale.credit_provider`` and
``Sale.credit_tracking_code`` for buy-now-pay-later sales, plus a partial
unique constraint on the tracking code so the same stored code can never
exist twice.

The three old bucket columns are NOT dropped and NOT modified here: new code
no longer writes them, but they keep their old values for legacy rows and are
still returned by ``sale_dict`` for API compatibility.
"""
from django.db import migrations, models
import django.db.models.deletion


def backfill_paid_amount(apps, schema_editor):
    """Set ``paid_amount`` = sum of the three legacy buckets for every sale.

    Idempotent: running it again rewrites the same value.
    """
    Sale = apps.get_model("inventory", "Sale")
    for sale in Sale.objects.only(
        "id", "paid_cash", "paid_pos", "paid_card2card", "paid_amount",
    ).iterator():
        total = (sale.paid_cash or 0) + (sale.paid_pos or 0) + (
            sale.paid_card2card or 0
        )
        if sale.paid_amount != total:
            sale.paid_amount = total
            Sale.objects.filter(id=sale.id).update(paid_amount=total)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0010_seed_suppliers"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="paid_amount",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="sale",
            name="credit_provider",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="sale",
            name="credit_tracking_code",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.RunPython(backfill_paid_amount, noop),
        migrations.AddConstraint(
            model_name="sale",
            constraint=models.UniqueConstraint(
                condition=~models.Q(credit_tracking_code=""),
                fields=["credit_tracking_code"],
                name="uniq_sale_credit_tracking_code",
            ),
        ),
    ]
