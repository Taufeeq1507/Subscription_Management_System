from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import (
    Subscription, SubscriptionLine, Invoice, InvoiceLine,
    DiscountRule, QuotationTemplate
)


def create_subscription_from_template(customer, template: QuotationTemplate, start_date=None, discount_rule=None):
    """Creates a Subscription in QUOTATION status pre-filled from a QuotationTemplate."""
    start = start_date or timezone.now().date()
    expiry = start + timedelta(days=template.validity_days)

    terms_map = {
        0: Subscription.PaymentTerms.IMMEDIATE,
        7: Subscription.PaymentTerms.NET_7,
        15: Subscription.PaymentTerms.NET_15,
        30: Subscription.PaymentTerms.NET_30,
    }
    payment_terms = terms_map.get(template.payment_terms_days, Subscription.PaymentTerms.NET_15)

    with transaction.atomic():
        sub = Subscription.objects.create(
            customer=customer,
            plan=template.plan,
            template_used=template,
            status=Subscription.Status.QUOTATION,
            start_date=start,
            expiry_date=expiry,
            next_billing_date=start,
            payment_terms=payment_terms,
            discount_rule=discount_rule,
            notes=template.notes,
        )
        for t_line in template.lines.select_related('product', 'variant').all():
            SubscriptionLine.objects.create(
                subscription=sub,
                product=t_line.product,
                variant=t_line.variant,
                quantity=t_line.quantity,
                tax_rule=t_line.product.tax_rule,
            )
    return sub


def generate_invoice_for_subscription(sub: Subscription, billing_date=None):
    """
    Idempotently generates a single Invoice for a subscription's current billing cycle.
    Returns (invoice, created_bool). Never bills twice for the same cycle.
    """
    cycle_start = sub.next_billing_date
    today = billing_date or timezone.now().date()

    # Check auto-close rule before billing
    if sub.expiry_date and today > sub.expiry_date and sub.plan.auto_close:
        sub.status = Subscription.Status.CLOSED
        sub.save(update_fields=['status'])
        return None, False

    # Idempotency check: prevent duplicate billing for the same cycle
    existing = Invoice.objects.filter(
        subscription=sub,
        billing_period_start=cycle_start
    ).first()
    if existing:
        return existing, False

    cycle_end = sub.plan.get_next_billing_date(cycle_start) - timedelta(days=1)
    due_date = today + timedelta(days=sub.get_due_days())

    lines = list(sub.lines.select_related('product', 'variant', 'tax_rule').all())
    if not lines:
        return None, False

    with transaction.atomic():
        subtotal = sum((l.untaxed_amount for l in lines), Decimal('0.00'))
        total_qty = sum(l.quantity for l in lines)

        # Evaluate Discount Rule automatically
        discount_amount = Decimal('0.00')
        applied_discount = None
        rule = sub.discount_rule

        if rule and rule.is_valid_for(today, subtotal, total_qty):
            if rule.applies_to == DiscountRule.TargetScope.SUBSCRIPTION:
                discount_amount = rule.calculate_discount(subtotal)
            elif rule.applies_to == DiscountRule.TargetScope.PRODUCT and rule.target_product_id:
                product_subtotal = sum(
                    (l.untaxed_amount for l in lines if l.product_id == rule.target_product_id),
                    Decimal('0.00')
                )
                discount_amount = rule.calculate_discount(product_subtotal)

            if discount_amount > Decimal('0.00'):
                applied_discount = rule
                rule.times_used += 1
                rule.save(update_fields=['times_used'])

        # Proportionally adjust tax if a discount was applied
        discount_ratio = (
            (subtotal - discount_amount) / subtotal
            if subtotal > Decimal('0.00') else Decimal('1.00')
        )

        raw_tax = sum((l.tax_amount for l in lines), Decimal('0.00'))
        tax_amount = (raw_tax * discount_ratio).quantize(Decimal('0.01'))
        total_amount = max(Decimal('0.00'), (subtotal - discount_amount) + tax_amount)

        invoice = Invoice.objects.create(
            subscription=sub,
            customer=sub.customer,
            billing_period_start=cycle_start,
            billing_period_end=cycle_end,
            issue_date=today,
            due_date=due_date,
            status=Invoice.Status.DRAFT,
            subtotal=subtotal,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            total_amount=total_amount,
            applied_discount=applied_discount,
        )

        for l in lines:
            variant_label = f" ({l.variant.attribute_name}: {l.variant.attribute_value})" if l.variant else ""
            tax_rate = l.tax_rule.rate_percent if (l.tax_rule and l.tax_rule.is_active) else Decimal('0.00')
            InvoiceLine.objects.create(
                invoice=invoice,
                product=l.product,
                description=f"{l.product.name}{variant_label}",
                quantity=l.quantity,
                unit_price=l.unit_price,
                tax_rate_percent=tax_rate,
                untaxed_amount=l.untaxed_amount,
                tax_amount=l.tax_amount,
                line_total=l.line_total,
            )

        # Advance subscription to the next billing cycle
        sub.next_billing_date = sub.plan.get_next_billing_date(cycle_start)
        sub.save(update_fields=['next_billing_date', 'updated_at'])

    return invoice, True


def run_billing_day_batch(billing_date=None):
    """
    Finds all ACTIVE subscriptions due on or before `billing_date` and generates invoices.
    Returns summary dict: {'created': int, 'skipped': int, 'closed': int}
    """
    today = billing_date or timezone.now().date()
    due_subs = Subscription.objects.filter(
        status=Subscription.Status.ACTIVE,
        next_billing_date__lte=today
    ).select_related('plan', 'customer', 'discount_rule')

    summary = {'created': 0, 'skipped': 0, 'closed': 0}
    for sub in due_subs:
        inv, created = generate_invoice_for_subscription(sub, billing_date=today)
        if sub.status == Subscription.Status.CLOSED:
            summary['closed'] += 1
        elif created:
            summary['created'] += 1
        else:
            summary['skipped'] += 1
    return summary