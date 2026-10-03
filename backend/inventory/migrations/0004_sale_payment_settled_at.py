# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0003_remove_product_quantity"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="settled_at",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="payment",
            name="settled_at",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
    ]
