from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, TaxRule, Product, ProductVariant, SubscriptionPlan,
    DiscountRule, QuotationTemplate, QuotationTemplateLine,
    Subscription, SubscriptionLine, Invoice, InvoiceLine, Payment
)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'role', 'company_name', 'is_staff')
    list_filter = ('role', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Brightloop Role & Info', {'fields': ('role', 'company_name', 'phone')}),
    )

admin.site.register([
    TaxRule, Product, ProductVariant, SubscriptionPlan,
    DiscountRule, QuotationTemplate, QuotationTemplateLine,
    Subscription, SubscriptionLine, Invoice, InvoiceLine, Payment
])