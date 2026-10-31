from datetime import timedelta
from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        STAFF = 'STAFF', 'Internal Staff'
        CUSTOMER = 'CUSTOMER', 'Customer'

    email = models.EmailField(unique=True, db_index=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        db_index=True
    )
    company_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    def is_staff_role(self):
        return self.role in [self.Role.ADMIN, self.Role.STAFF] or self.is_superuser

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.email}) - {self.role}"


class TaxRule(models.Model):
    name = models.CharField(max_length=100)
    rate_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    is_active = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return f"{self.name} ({self.rate_percent}%)"


class Product(models.Model):
    class ProductType(models.TextChoices):
        SOFTWARE = 'SOFTWARE', 'Subscription Software'
        ADDON = 'ADDON', 'Switchable Add-on'
        SERVICE = 'SERVICE', 'Service'

    name = models.CharField(max_length=150, db_index=True)
    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        default=ProductType.SOFTWARE
    )
    sales_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    tax_rule = models.ForeignKey(
        TaxRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (₹{self.sales_price})"


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    attribute_name = models.CharField(max_length=80, default='Brand')
    attribute_value = models.CharField(max_length=80)
    price_extra = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )

    class Meta:
        unique_together = ('product', 'attribute_name', 'attribute_value')

    def __str__(self):
        sign = "+" if self.price_extra >= 0 else ""
        return f"{self.product.name} - {self.attribute_name}: {self.attribute_value} ({sign}₹{self.price_extra})"


class SubscriptionPlan(models.Model):
    class BillingPeriod(models.TextChoices):
        DAILY = 'DAILY', 'Daily'
        WEEKLY = 'WEEKLY', 'Weekly'
        MONTHLY = 'MONTHLY', 'Monthly'
        YEARLY = 'YEARLY', 'Yearly'

    name = models.CharField(max_length=150, db_index=True)
    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    billing_period = models.CharField(
        max_length=20,
        choices=BillingPeriod.choices,
        default=BillingPeriod.MONTHLY
    )
    min_quantity = models.PositiveIntegerField(default=1)
    available_from = models.DateField(default=timezone.now)
    available_to = models.DateField(null=True, blank=True)

    # Plan-by-plan lifecycle controls configured by Admin
    auto_close = models.BooleanField(default=False, help_text="Close automatically on expiry date")
    can_close_early = models.BooleanField(default=True, help_text="Allow early cancellation")
    can_pause = models.BooleanField(default=True, help_text="Allow pausing subscription")
    can_renew = models.BooleanField(default=True, help_text="Allow manual or automatic renewal")
    is_active = models.BooleanField(default=True, db_index=True)

    def get_next_billing_date(self, current_date):
        if self.billing_period == self.BillingPeriod.DAILY:
            return current_date + timedelta(days=1)
        elif self.billing_period == self.BillingPeriod.WEEKLY:
            return current_date + timedelta(weeks=1)
        elif self.billing_period == self.BillingPeriod.MONTHLY:
            return current_date + timedelta(days=30)
        elif self.billing_period == self.BillingPeriod.YEARLY:
            return current_date + timedelta(days=365)
        return current_date + timedelta(days=30)

    def __str__(self):
        return f"{self.name} ({self.get_billing_period_display()})"


class DiscountRule(models.Model):
    class DiscountType(models.TextChoices):
        FIXED = 'FIXED', 'Fixed Amount'
        PERCENTAGE = 'PERCENTAGE', 'Percentage (%)'

    class TargetScope(models.TextChoices):
        SUBSCRIPTION = 'SUBSCRIPTION', 'Whole Subscription'
        PRODUCT = 'PRODUCT', 'Specific Product'

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    min_purchase_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    min_quantity = models.PositiveIntegerField(default=1)
    start_date = models.DateField(default=timezone.now, db_index=True)
    end_date = models.DateField(null=True, blank=True, db_index=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank for unlimited")
    times_used = models.PositiveIntegerField(default=0)
    applies_to = models.CharField(
        max_length=20,
        choices=TargetScope.choices,
        default=TargetScope.SUBSCRIPTION
    )
    target_product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discounts'
    )
    is_active = models.BooleanField(default=True, db_index=True)

    def is_valid_for(self, check_date, subtotal, total_qty):
        if not self.is_active:
            return False
        if check_date < self.start_date:
            return False
        if self.end_date and check_date > self.end_date:
            return False
        if self.max_uses is not None and self.times_used >= self.max_uses:
            return False
        if subtotal < self.min_purchase_amount:
            return False
        if total_qty < self.min_quantity:
            return False
        return True

    def calculate_discount(self, base_amount):
        if self.discount_type == self.DiscountType.FIXED:
            return min(self.value, base_amount)
        return (base_amount * (self.value / Decimal('100.00'))).quantize(Decimal('0.01'))

    def __str__(self):
        return f"{self.name} ({self.code})"


class QuotationTemplate(models.Model):
    name = models.CharField(max_length=150)
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.CASCADE,
        related_name='templates'
    )
    validity_days = models.PositiveIntegerField(default=15)
    payment_terms_days = models.PositiveIntegerField(default=15, help_text="Days until invoice is due")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.plan.name} - Valid {self.validity_days}d)"


class QuotationTemplateLine(models.Model):
    template = models.ForeignKey(
        QuotationTemplate,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.template.name} -> {self.product.name} x {self.quantity}"


class Subscription(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        QUOTATION = 'QUOTATION', 'Quotation'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        ACTIVE = 'ACTIVE', 'Active'
        PAUSED = 'PAUSED', 'Paused'
        CLOSED = 'CLOSED', 'Closed'

    class PaymentTerms(models.TextChoices):
        IMMEDIATE = 'IMMEDIATE', 'Immediate Payment'
        NET_7 = 'NET_7', 'Net 7 Days'
        NET_15 = 'NET_15', 'Net 15 Days'
        NET_30 = 'NET_30', 'Net 30 Days'

    subscription_number = models.CharField(max_length=40, unique=True, db_index=True, blank=True)
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        db_index=True
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    template_used = models.ForeignKey(
        QuotationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True
    )
    start_date = models.DateField(default=timezone.now, db_index=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    next_billing_date = models.DateField(default=timezone.now, db_index=True)
    payment_terms = models.CharField(
        max_length=20,
        choices=PaymentTerms.choices,
        default=PaymentTerms.NET_15
    )
    discount_rule = models.ForeignKey(
        DiscountRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'next_billing_date']),
            models.Index(fields=['customer', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.subscription_number:
            last_sub = Subscription.objects.order_by('-id').first()
            next_id = (last_sub.id + 1) if last_sub else 1
            self.subscription_number = f"SUB-{next_id:05d}"
        super().save(*args, **kwargs)

    def get_due_days(self):
        mapping = {
            self.PaymentTerms.IMMEDIATE: 0,
            self.PaymentTerms.NET_7: 7,
            self.PaymentTerms.NET_15: 15,
            self.PaymentTerms.NET_30: 30,
        }
        return mapping.get(self.payment_terms, 15)

    @property
    def total_quantity(self):
        return sum(line.quantity for line in self.lines.all())

    @property
    def untaxed_subtotal(self):
        return sum(line.untaxed_amount for line in self.lines.all())

    @property
    def total_tax(self):
        return sum(line.tax_amount for line in self.lines.all())

    @property
    def estimated_total(self):
        return self.untaxed_subtotal + self.total_tax

    def __str__(self):
        return f"{self.subscription_number} - {self.customer.email} ({self.status})"


class SubscriptionLine(models.Model):
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True)
    tax_rule = models.ForeignKey(
        TaxRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    untaxed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def save(self, *args, **kwargs):
        if self.unit_price is None:
            extra = self.variant.price_extra if self.variant else Decimal('0.00')
            self.unit_price = self.product.sales_price + extra
        if not self.tax_rule and self.product.tax_rule:
            self.tax_rule = self.product.tax_rule

        self.untaxed_amount = (self.unit_price * Decimal(self.quantity)).quantize(Decimal('0.01'))
        tax_rate = self.tax_rule.rate_percent if (self.tax_rule and self.tax_rule.is_active) else Decimal('0.00')
        self.tax_amount = (self.untaxed_amount * (tax_rate / Decimal('100.00'))).quantize(Decimal('0.01'))
        self.line_total = self.untaxed_amount + self.tax_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.subscription.subscription_number} - {self.product.name} (x{self.quantity})"


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        PAID = 'PAID', 'Paid'
        CANCELLED = 'CANCELLED', 'Cancelled'

    invoice_number = models.CharField(max_length=40, unique=True, db_index=True, blank=True)
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='invoices',
        db_index=True
    )
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='invoices',
        db_index=True
    )
    billing_period_start = models.DateField(db_index=True)
    billing_period_end = models.DateField()
    issue_date = models.DateField(default=timezone.now, db_index=True)
    due_date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    applied_discount = models.ForeignKey(
        DiscountRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['subscription', 'billing_period_start'],
                name='unique_subscription_billing_cycle'
            )
        ]
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['customer', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            last_inv = Invoice.objects.order_by('-id').first()
            next_id = (last_inv.id + 1) if last_inv else 1
            self.invoice_number = f"INV-{next_id:05d}"
        super().save(*args, **kwargs)

    @property
    def amount_due(self):
        return max(Decimal('0.00'), self.total_amount - self.amount_paid)

    @property
    def is_overdue(self):
        return (
            self.status == self.Status.CONFIRMED
            and self.due_date < timezone.now().date()
            and self.amount_due > Decimal('0.00')
        )

    def recalculate_payment_status(self):
        total_paid = sum(p.amount for p in self.payments.all())
        self.amount_paid = total_paid
        if self.status != self.Status.CANCELLED and total_paid >= self.total_amount and self.total_amount > 0:
            self.status = self.Status.PAID
        self.save(update_fields=['amount_paid', 'status'])

    def __str__(self):
        return f"{self.invoice_number} ({self.status}) - ₹{self.total_amount}"


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    untaxed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description}"


class Payment(models.Model):
    class Method(models.TextChoices):
        BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer / NEFT'
        UPI = 'UPI', 'UPI'
        CARD = 'CARD', 'Credit / Debit Card'
        CASH = 'CASH', 'Cash / Cheque'

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='payments',
        db_index=True
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_date = models.DateField(default=timezone.now, db_index=True)
    payment_method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.BANK_TRANSFER
    )
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            self.invoice.recalculate_payment_status()

    def __str__(self):
        return f"₹{self.amount} for {self.invoice.invoice_number} via {self.get_payment_method_display()}"