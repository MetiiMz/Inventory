"""TikoTime ORM models — عمداً شبیه دیتابیس قدیمی، اما با کلید و ایندکس درست."""
from django.db import models


class Setting(models.Model):
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.TextField(default="", blank=True)

    class Meta:
        db_table = "settings"


class Product(models.Model):
    name = models.CharField(max_length=200)
    reference = models.CharField(max_length=200, default="", blank=True)
    office_code = models.CharField(max_length=100, db_index=True)
    website_code = models.CharField(max_length=100, db_index=True)
    brand = models.CharField(max_length=100, default="", blank=True)
    purchase_price = models.FloatField(default=0)
    sale_price = models.FloatField(default=0)
    available = models.BooleanField(default=True, db_index=True)
    supplier = models.CharField(max_length=200, default="", blank=True)
    # تاریخ خرید به‌صورت ISO ذخیره می‌شود (تبدیل شمسی↔میلادی در jalali.py)
    purchase_date = models.CharField(max_length=10, default="", blank=True, db_index=True)
    purchase_type = models.CharField(max_length=20, default="person")
    notes = models.TextField(default="", blank=True)
    image = models.CharField(max_length=255, default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        indexes = [
            models.Index(fields=["brand"]),
            models.Index(fields=["-id"]),
        ]


class Sale(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="sales", db_index=True,
    )
    sale_price = models.FloatField(default=0)
    purchase_price = models.FloatField(default=0)
    profit = models.FloatField(default=0)
    sale_date = models.CharField(max_length=10, default="", blank=True, db_index=True)
    customer = models.CharField(max_length=200, default="", blank=True)
    customer_phone = models.CharField(max_length=30, default="", blank=True)
    sale_type = models.CharField(max_length=20, default="person")
    payment_type = models.CharField(max_length=20, default="cash")
    final_price = models.FloatField(default=0)
    paid_cash = models.FloatField(default=0)
    paid_pos = models.FloatField(default=0)
    paid_card2card = models.FloatField(default=0)
    is_settled = models.BooleanField(default=True, db_index=True)
    settled_at = models.CharField(max_length=10, default="", blank=True)
    invoice_code = models.CharField(max_length=40, default="", blank=True)
    notes = models.TextField(default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sales"
        indexes = [
            models.Index(fields=["-sale_date", "-id"]),
            models.Index(fields=["payment_type", "is_settled"]),
        ]


class Payment(models.Model):
    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, null=True, blank=True,
        related_name="payments", db_index=True,
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payments", db_index=True,
    )
    product_name = models.CharField(max_length=200, default="", blank=True)
    customer_name = models.CharField(max_length=200, default="", blank=True)
    customer_phone = models.CharField(max_length=30, default="", blank=True)
    total_amount = models.FloatField(default=0)
    paid_amount = models.FloatField(default=0)
    pay_date = models.CharField(max_length=10, default="", blank=True, db_index=True)
    settled_at = models.CharField(max_length=10, default="", blank=True)
    notes = models.TextField(default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"


class Repair(models.Model):
    watch_name = models.CharField(max_length=200)
    watch_code = models.CharField(max_length=100, default="", blank=True)
    issue = models.TextField(default="", blank=True)
    delivery_date = models.CharField(max_length=10, default="", blank=True, db_index=True)
    return_date = models.CharField(max_length=10, default="", blank=True, db_index=True)
    customer_name = models.CharField(max_length=200, default="", blank=True)
    customer_phone = models.CharField(max_length=30, default="", blank=True)
    is_warranty = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="received", db_index=True)
    repair_price = models.FloatField(default=0)
    image = models.CharField(max_length=255, default="", blank=True)
    notes = models.TextField(default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "repairs"
        indexes = [models.Index(fields=["status", "-id"])]


class Tracking(models.Model):
    item_name = models.CharField(max_length=200)
    item_code = models.CharField(max_length=100, default="", blank=True)
    customer_name = models.CharField(max_length=200, default="", blank=True)
    customer_phone = models.CharField(max_length=30, default="", blank=True)
    price = models.FloatField(default=0)
    status = models.CharField(max_length=20, default="new", db_index=True)
    notes = models.TextField(default="", blank=True)
    image = models.CharField(max_length=255, default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tracking"
        indexes = [models.Index(fields=["status", "-id"])]
