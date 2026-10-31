from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import (
    User, TaxRule, Product, ProductVariant, SubscriptionPlan,
    DiscountRule, QuotationTemplate, QuotationTemplateLine,
    Subscription, SubscriptionLine, Payment
)

TAILWIND_INPUT = "w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
TAILWIND_CHECKBOX = "h-4 w-4 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500"


class TailwindFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = TAILWIND_CHECKBOX
            else:
                field.widget.attrs['class'] = TAILWIND_INPUT


class CustomerSignupForm(TailwindFormMixin, UserCreationForm):
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    email = forms.EmailField(required=True)
    company_name = forms.CharField(max_length=150, required=True)
    phone = forms.CharField(max_length=30, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'company_name', 'phone')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CUSTOMER
        if commit:
            user.save()
        return user


class StaffCreationForm(TailwindFormMixin, UserCreationForm):
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=[(User.Role.STAFF, 'Internal Staff'), (User.Role.ADMIN, 'Admin')])

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'role')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.company_name = "Brightloop Software"
        if commit:
            user.save()
        return user


class ProductForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'product_type', 'sales_price', 'cost_price', 'tax_rule', 'notes', 'is_active']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}


class ProductVariantForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['product', 'attribute_name', 'attribute_value', 'price_extra']


class SubscriptionPlanForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = [
            'name', 'base_price', 'billing_period', 'min_quantity',
            'available_from', 'available_to', 'auto_close',
            'can_close_early', 'can_pause', 'can_renew', 'is_active'
        ]
        widgets = {
            'available_from': forms.DateInput(attrs={'type': 'date'}),
            'available_to': forms.DateInput(attrs={'type': 'date'}),
        }


class TaxRuleForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = TaxRule
        fields = ['name', 'rate_percent', 'is_active']


class DiscountRuleForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = DiscountRule
        fields = [
            'name', 'code', 'discount_type', 'value',
            'min_purchase_amount', 'min_quantity', 'start_date', 'end_date',
            'max_uses', 'applies_to', 'target_product', 'is_active'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class QuotationTemplateForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = QuotationTemplate
        fields = ['name', 'plan', 'validity_days', 'payment_terms_days', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}


class QuotationTemplateLineForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = QuotationTemplateLine
        fields = ['template', 'product', 'variant', 'quantity']


class SubscriptionCreateForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Subscription
        fields = [
            'customer', 'plan', 'status', 'start_date',
            'expiry_date', 'next_billing_date', 'payment_terms',
            'discount_rule', 'notes'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'next_billing_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = User.objects.filter(role=User.Role.CUSTOMER)


class SubscriptionFromTemplateForm(TailwindFormMixin, forms.Form):
    customer = forms.ModelChoiceField(queryset=User.objects.filter(role=User.Role.CUSTOMER))
    template = forms.ModelChoiceField(queryset=QuotationTemplate.objects.all())
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    discount_rule = forms.ModelChoiceField(
        queryset=DiscountRule.objects.filter(is_active=True),
        required=False
    )


class SubscriptionLineForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = SubscriptionLine
        fields = ['product', 'variant', 'quantity', 'tax_rule']


class PaymentForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'payment_date', 'payment_method', 'note']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
        }