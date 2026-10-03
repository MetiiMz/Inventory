from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_product_quantity"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="product",
            name="quantity",
        ),
    ]