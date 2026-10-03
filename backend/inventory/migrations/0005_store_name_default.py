# -*- coding: utf-8 -*-
"""نام پیش‌فرض فروشگاه = Tick O Time (سطر Setting فقط اگر وجود نداشته باشد)."""
from django.db import migrations


def seed(apps, schema_editor):
    Setting = apps.get_model("inventory", "Setting")
    Setting.objects.get_or_create(
        key="store_name", defaults={"value": "Tick O Time"})


def unseed(apps, schema_editor):
    Setting = apps.get_model("inventory", "Setting")
    Setting.objects.filter(key="store_name", value="Tick O Time").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0004_sale_payment_settled_at"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
