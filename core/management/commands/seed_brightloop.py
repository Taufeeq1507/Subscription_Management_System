from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import (
    User, TaxRule, Product, ProductVariant, SubscriptionPlan,
    DiscountRule, QuotationTemplate, QuotationTemplateLine,
    Subscription, SubscriptionLine, Invoice, Payment
)
from core.services import generate_invoice_for_subscription


class Command(BaseCommand):
    help = "Seeds Brightloop Software demo data for the Odoo Hackathon"

    def handle(self, *args, **options):
        today = timezone.now().date()

        # 1. Users (Admin, Staff, 2 Customers)
        admin_user, _ = User.objects.get_or_create(
            email='admin@brightloop.io',
            defaults={
                'username': 'admin',
                'first_name': 'Aarav',
                'last_name': 'Admin',
                'role': User.Role.ADMIN,
                'company_name': 'Brightloop Software',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.set_password('Brightloop@123')
        admin_user.save()

        staff_user, _ = User.objects.get_or_create(
            email='sales@brightloop.io',
            defaults={
                'username': 'sales_rep',
                'first_name': 'Riya',
                'last_name': 'Sharma (Staff)',
                'role': User.Role.STAFF,
                'company_name': 'Brightloop Software',
                'is_staff': True,
            }
        )
        staff_user.set_password('Brightloop@123')
        staff_user.save()

        cust1, _ = User.objects.get_or_create(
            email='founder@smallshop.in',
            defaults={
                'username': 'smallshop',
                'first_name': 'Kabir',
                'last_name': 'Verma',
                'role': User.Role.CUSTOMER,
                'company_name': 'Verma Retail Shop',
                'phone': '+91 9876543210',
            }
        )
        cust1.set_password('Customer@123')
        cust1.save()

        cust2, _ = User.objects.get_or_create(
            email='cto@apexcorp.in',
            defaults={
                'username': 'apexcorp',
                'first_name': 'Neha',
                'last_name': 'Kapoor',
                'role': User.Role.CUSTOMER,
                'company_name': 'Apex Enterprise Ltd',
                'phone': '+91 9123456780',
            }
        )
        cust2.set_password('Customer@123')
        cust2.save()

        # 2. Tax Rules
        gst_18, _ = TaxRule.objects.get_or_create(
            name='GST 18%',
            defaults={'rate_percent': Decimal('18.00'), 'is_active': True}
        )
        gst_12, _ = TaxRule.objects.get_or_create(
            name='GST 12%',
            defaults={'rate_percent': Decimal('12.00'), 'is_active': True}
        )

        # 3. Products & Odoo +560 Variant
        erp_prod, _ = Product.objects.get_or_create(
            name='Brightloop Cloud Suite',
            defaults={
                'product_type': Product.ProductType.SOFTWARE,
                'sales_price': Decimal('2000.00'),
                'cost_price': Decimal('600.00'),
                'tax_rule': gst_18,
                'notes': 'Core cloud subscription software billed per seat.',
            }
        )
        odoo_variant, _ = ProductVariant.objects.get_or_create(
            product=erp_prod,
            attribute_name='Brand',
            attribute_value='Odoo',
            defaults={'price_extra': Decimal('560.00')}
        )
        std_variant, _ = ProductVariant.objects.get_or_create(
            product=erp_prod,
            attribute_name='Brand',
            attribute_value='Standard',
            defaults={'price_extra': Decimal('0.00')}
        )

        addon_analytics, _ = Product.objects.get_or_create(
            name='Advanced Analytics Add-on',
            defaults={
                'product_type': Product.ProductType.ADDON,
                'sales_price': Decimal('800.00'),
                'cost_price': Decimal('200.00'),
                'tax_rule': gst_18,
                'notes': 'Switchable monthly/yearly analytics module.',
            }
        )

        support_prod, _ = Product.objects.get_or_create(
            name='Priority 24/7 SLA Support',
            defaults={
                'product_type': Product.ProductType.SERVICE,
                'sales_price': Decimal('1500.00'),
                'cost_price': Decimal('500.00'),
                'tax_rule': gst_12,
                'notes': 'Dedicated account support.',
            }
        )

        # 4. Subscription Plans
        monthly_plan, _ = SubscriptionPlan.objects.get_or_create(
            name='SMB Monthly Flex Plan',
            defaults={
                'base_price': Decimal('2000.00'),
                'billing_period': SubscriptionPlan.BillingPeriod.MONTHLY,
                'min_quantity': 1,
                'available_from': today - timedelta(days=90),
                'auto_close': False,
                'can_close_early': True,
                'can_pause': True,
                'can_renew': True,
            }
        )
        yearly_plan, _ = SubscriptionPlan.objects.get_or_create(
            name='Enterprise Annual Contract',
            defaults={
                'base_price': Decimal('20000.00'),
                'billing_period': SubscriptionPlan.BillingPeriod.YEARLY,
                'min_quantity': 5,
                'available_from': today - timedelta(days=90),
                'available_to': today + timedelta(days=365),
                'auto_close': True,
                'can_close_early': False,
                'can_pause': False,
                'can_renew': True,
            }
        )

        # 5. Discount Rules
        seat_discount, _ = DiscountRule.objects.get_or_create(
            code='BULK15',
            defaults={
                'name': '15% Multi-Seat Discount (5+ Seats)',
                'discount_type': DiscountRule.DiscountType.PERCENTAGE,
                'value': Decimal('15.00'),
                'min_purchase_amount': Decimal('5000.00'),
                'min_quantity': 5,
                'start_date': today - timedelta(days=30),
                'end_date': today + timedelta(days=60),
                'max_uses': 10,
                'applies_to': DiscountRule.TargetScope.SUBSCRIPTION,
            }
        )

        # 6. Quotation Template
        q_template, _ = QuotationTemplate.objects.get_or_create(
            name='Enterprise Odoo Turnkey Package',
            defaults={
                'plan': yearly_plan,
                'validity_days': 15,
                'payment_terms_days': 15,
                'notes': 'Standard enterprise offer with Odoo brand variant and Analytics.',
            }
        )
        QuotationTemplateLine.objects.get_or_create(
            template=q_template,
            product=erp_prod,
            variant=odoo_variant,
            defaults={'quantity': 10}
        )
        QuotationTemplateLine.objects.get_or_create(
            template=q_template,
            product=addon_analytics,
            variant=None,
            defaults={'quantity': 1}
        )

        # 7. Sample Active Subscriptions & Invoices
        if not Subscription.objects.exists():
            # Sub 1: Active & Due Today (Ready for Billing Day demo)
            sub1 = Subscription.objects.create(
                customer=cust2,
                plan=yearly_plan,
                template_used=q_template,
                status=Subscription.Status.ACTIVE,
                start_date=today,
                expiry_date=today + timedelta(days=365),
                next_billing_date=today,
                payment_terms=Subscription.PaymentTerms.NET_15,
                discount_rule=seat_discount,
            )
            SubscriptionLine.objects.create(
                subscription=sub1, product=erp_prod, variant=odoo_variant, quantity=10
            )
            SubscriptionLine.objects.create(
                subscription=sub1, product=addon_analytics, quantity=2
            )

            # Sub 2: Active with an Overdue Invoice + a Paid Invoice
            sub2 = Subscription.objects.create(
                customer=cust1,
                plan=monthly_plan,
                status=Subscription.Status.ACTIVE,
                start_date=today - timedelta(days=60),
                expiry_date=today + timedelta(days=300),
                next_billing_date=today - timedelta(days=30),
                payment_terms=Subscription.PaymentTerms.IMMEDIATE,
            )
            SubscriptionLine.objects.create(
                subscription=sub2, product=erp_prod, variant=std_variant, quantity=2
            )
            inv_overdue, _ = generate_invoice_for_subscription(sub2, billing_date=today - timedelta(days=20))
            if inv_overdue:
                inv_overdue.status = Invoice.Status.CONFIRMED
                inv_overdue.due_date = today - timedelta(days=10)
                inv_overdue.save()

            # Create a paid invoice for revenue stats
            inv_paid, _ = generate_invoice_for_subscription(sub1, billing_date=today)
            if inv_paid:
                inv_paid.status = Invoice.Status.CONFIRMED
                inv_paid.save()
                Payment.objects.create(
                    invoice=inv_paid,
                    amount=inv_paid.total_amount,
                    payment_date=today,
                    payment_method=Payment.Method.BANK_TRANSFER,
                    note='NEFT Ref #UTR99881122',
                    recorded_by=staff_user
                )

        self.stdout.write(self.style.SUCCESS(
            "Brightloop demo data seeded! Logins:\n"
            "  Admin:    admin@brightloop.io / Brightloop@123\n"
            "  Staff:    sales@brightloop.io / Brightloop@123\n"
            "  Customer: founder@smallshop.in / Customer@123"
        ))