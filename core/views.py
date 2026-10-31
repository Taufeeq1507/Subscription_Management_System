from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.mail import send_mail

from .models import (
    User, TaxRule, Product, ProductVariant, SubscriptionPlan,
    DiscountRule, QuotationTemplate, Subscription, SubscriptionLine,
    Invoice, Payment
)
from .forms import (
    CustomerSignupForm, StaffCreationForm, ProductForm, ProductVariantForm,
    SubscriptionPlanForm, TaxRuleForm, DiscountRuleForm, QuotationTemplateForm,
    QuotationTemplateLineForm, SubscriptionCreateForm, SubscriptionFromTemplateForm,
    SubscriptionLineForm, PaymentForm
)
from .services import (
    create_subscription_from_template,
    generate_invoice_for_subscription,
    run_billing_day_batch
)


def is_staff_or_admin(user):
    return user.is_authenticated and user.is_staff_role()


def is_admin_only(user):
    return user.is_authenticated and user.is_admin_role()


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = CustomerSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to Brightloop! Your customer account is ready.")
            return redirect('customer_portal')
    else:
        form = CustomerSignupForm()
    return render(request, 'core/signup.html', {'form': form})


@login_required
def dashboard(request):
    """Routes Customers to their Self-Service Portal and Staff/Admin to the Finance Lead Dashboard."""
    if not request.user.is_staff_role():
        return redirect('customer_portal')

    today = timezone.now().date()
    status_filter = request.GET.get('status', '')
    plan_filter = request.GET.get('plan', '')

    subs_qs = Subscription.objects.select_related('customer', 'plan')
    if status_filter:
        subs_qs = subs_qs.filter(status=status_filter)
    if plan_filter:
        subs_qs = subs_qs.filter(plan_id=plan_filter)

    # Finance Lead KPI Metrics (Single aggregated queries for <2s speed)
    active_subs_count = Subscription.objects.filter(status=Subscription.Status.ACTIVE).count()
    revenue_collected = Payment.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    confirmed_invoices = Invoice.objects.filter(status=Invoice.Status.CONFIRMED)
    total_billed_unpaid = confirmed_invoices.aggregate(
        billed=Sum('total_amount'),
        paid=Sum('amount_paid')
    )
    outstanding_balance = (
        (total_billed_unpaid['billed'] or Decimal('0.00')) -
        (total_billed_unpaid['paid'] or Decimal('0.00'))
    )

    overdue_invoices = Invoice.objects.filter(
        status=Invoice.Status.CONFIRMED,
        due_date__lt=today
    ).select_related('customer', 'subscription').order_by('due_date')

    due_for_billing_count = Subscription.objects.filter(
        status=Subscription.Status.ACTIVE,
        next_billing_date__lte=today
    ).count()

    recent_payments = Payment.objects.select_related('invoice', 'invoice__customer').order_by('-payment_date', '-id')[:8]
    plans = SubscriptionPlan.objects.filter(is_active=True)

    context = {
        'active_subs_count': active_subs_count,
        'revenue_collected': revenue_collected,
        'outstanding_balance': outstanding_balance,
        'overdue_count': overdue_invoices.count(),
        'overdue_invoices': overdue_invoices[:15],
        'due_for_billing_count': due_for_billing_count,
        'recent_subscriptions': subs_qs.order_by('-created_at')[:10],
        'recent_payments': recent_payments,
        'plans': plans,
        'status_filter': status_filter,
        'plan_filter': plan_filter,
        'today': today,
    }
    return render(request, 'core/dashboard.html', context)


@user_passes_test(is_admin_only)
def manage_staff(request):
    """Only Admin can add a new member of internal staff."""
    if request.method == 'POST':
        form = StaffCreationForm(request.POST)
        if form.is_valid():
            staff = form.save()
            messages.success(request, f"Staff account created for {staff.email} ({staff.role}).")
            return redirect('manage_staff')
    else:
        form = StaffCreationForm()

    staff_members = User.objects.filter(role__in=[User.Role.ADMIN, User.Role.STAFF]).order_by('role', 'email')
    customers = User.objects.filter(role=User.Role.CUSTOMER).order_by('-date_joined')[:25]
    return render(request, 'core/manage_staff.html', {
        'form': form,
        'staff_members': staff_members,
        'customers': customers,
    })


@user_passes_test(is_staff_or_admin)
def catalog_view(request):
    """Products, Variants, Plans, Taxes, Discounts, and Quotation Templates."""
    if request.method == 'POST':
        if not request.user.is_admin_role():
            messages.error(request, "Only Admins can create or modify products, plans, taxes, and discounts.")
            return redirect('catalog')

        form_type = request.POST.get('form_type')
        form_map = {
            'product': (ProductForm, "Product created successfully."),
            'variant': (ProductVariantForm, "Product variant (+price extra) added."),
            'plan': (SubscriptionPlanForm, "Subscription plan created."),
            'tax': (TaxRuleForm, "Tax rule added."),
            'discount': (DiscountRuleForm, "Discount rule created."),
            'template': (QuotationTemplateForm, "Quotation template created."),
            'template_line': (QuotationTemplateLineForm, "Line added to quotation template."),
        }
        if form_type in form_map:
            FormClass, success_msg = form_map[form_type]
            form = FormClass(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, success_msg)
            else:
                messages.error(request, f"Error in {form_type} form: {form.errors.as_text()}")
        return redirect('catalog')

    context = {
        'products': Product.objects.prefetch_related('variants').select_related('tax_rule').all(),
        'plans': SubscriptionPlan.objects.all(),
        'taxes': TaxRule.objects.all(),
        'discounts': DiscountRule.objects.select_related('target_product').all(),
        'templates': QuotationTemplate.objects.prefetch_related('lines__product', 'lines__variant').select_related('plan').all(),
        'product_form': ProductForm(),
        'variant_form': ProductVariantForm(),
        'plan_form': SubscriptionPlanForm(),
        'tax_form': TaxRuleForm(),
        'discount_form': DiscountRuleForm(),
        'template_form': QuotationTemplateForm(),
        'template_line_form': QuotationTemplateLineForm(),
    }
    return render(request, 'core/catalog.html', context)


@user_passes_test(is_staff_or_admin)
def subscription_list(request):
    status_filter = request.GET.get('status', '')
    q = request.GET.get('q', '')

    qs = Subscription.objects.select_related('customer', 'plan', 'discount_rule').order_by('-created_at')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if q:
        qs = qs.filter(
            Q(subscription_number__icontains=q) |
            Q(customer__email__icontains=q) |
            Q(customer__company_name__icontains=q)
        )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    if request.method == 'POST':
        action = request.POST.get('create_mode')
        if action == 'from_template':
            t_form = SubscriptionFromTemplateForm(request.POST)
            if t_form.is_valid():
                sub = create_subscription_from_template(
                    customer=t_form.cleaned_data['customer'],
                    template=t_form.cleaned_data['template'],
                    start_date=t_form.cleaned_data['start_date'],
                    discount_rule=t_form.cleaned_data['discount_rule']
                )
                messages.success(request, f"Quotation {sub.subscription_number} created from template!")
                return redirect('subscription_detail', pk=sub.pk)
        else:
            c_form = SubscriptionCreateForm(request.POST)
            if c_form.is_valid():
                sub = c_form.save()
                messages.success(request, f"Subscription {sub.subscription_number} created.")
                return redirect('subscription_detail', pk=sub.pk)

    return render(request, 'core/subscription_list.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'q': q,
        'create_form': SubscriptionCreateForm(initial={'start_date': timezone.now().date(), 'next_billing_date': timezone.now().date()}),
        'template_form': SubscriptionFromTemplateForm(initial={'start_date': timezone.now().date()}),
        'statuses': Subscription.Status.choices,
    })


@login_required
def subscription_detail(request, pk):
    sub = get_object_or_404(
        Subscription.objects.select_related('customer', 'plan', 'discount_rule', 'template_used')
        .prefetch_related('lines__product', 'lines__variant', 'lines__tax_rule', 'invoices'),
        pk=pk
    )
    # Customers can only see their own subscriptions
    if not request.user.is_staff_role() and sub.customer != request.user:
        messages.error(request, "Access denied.")
        return redirect('customer_portal')

    if request.method == 'POST' and request.user.is_staff_role():
        line_form = SubscriptionLineForm(request.POST)
        if line_form.is_valid():
            line = line_form.save(commit=False)
            line.subscription = sub
            line.save()
            messages.success(request, f"Added {line.product.name} to {sub.subscription_number}.")
            return redirect('subscription_detail', pk=sub.pk)
    else:
        line_form = SubscriptionLineForm()

    lifecycle_steps = ['DRAFT', 'QUOTATION', 'CONFIRMED', 'ACTIVE', 'CLOSED']
    return render(request, 'core/subscription_detail.html', {
        'sub': sub,
        'line_form': line_form,
        'lifecycle_steps': lifecycle_steps,
    })


@login_required
def subscription_transition(request, pk, action):
    """Handles state transitions respecting Plan-level lifecycle flags."""
    sub = get_object_or_404(Subscription.objects.select_related('plan'), pk=pk)
    is_staff = request.user.is_staff_role()

    if not is_staff and sub.customer != request.user:
        messages.error(request, "Unauthorized action.")
        return redirect('customer_portal')

    plan = sub.plan
    today = timezone.now().date()

    if action == 'send_quote' and is_staff:
        sub.status = Subscription.Status.QUOTATION
        sub.save(update_fields=['status'])
        messages.success(request, f"{sub.subscription_number} marked as Quotation.")

    elif action == 'confirm':
        sub.status = Subscription.Status.CONFIRMED
        sub.save(update_fields=['status'])
        messages.success(request, f"{sub.subscription_number} Confirmed!")

    elif action == 'activate' and is_staff:
        sub.status = Subscription.Status.ACTIVE
        if not sub.next_billing_date:
            sub.next_billing_date = today
        sub.save(update_fields=['status', 'next_billing_date'])
        messages.success(request, f"{sub.subscription_number} is now ACTIVE.")

    elif action == 'pause':
        if not plan.can_pause and not request.user.is_admin_role():
            messages.error(request, f"Plan '{plan.name}' does not allow pausing.")
        else:
            sub.status = Subscription.Status.PAUSED
            sub.save(update_fields=['status'])
            messages.warning(request, f"Subscription {sub.subscription_number} paused.")

    elif action == 'resume':
        sub.status = Subscription.Status.ACTIVE
        sub.save(update_fields=['status'])
        messages.success(request, f"Subscription {sub.subscription_number} resumed to Active.")

    elif action == 'renew':
        if not plan.can_renew and not request.user.is_admin_role():
            messages.error(request, f"Plan '{plan.name}' does not allow renewal.")
        else:
            base_date = max(sub.expiry_date or today, today)
            sub.expiry_date = plan.get_next_billing_date(base_date)
            sub.status = Subscription.Status.ACTIVE
            sub.save(update_fields=['expiry_date', 'status'])
            messages.success(request, f"Subscription renewed! New expiry date: {sub.expiry_date}.")

    elif action == 'close':
        if not plan.can_close_early and not request.user.is_admin_role():
            messages.error(request, f"Plan '{plan.name}' locks in contract and cannot be closed early.")
        else:
            sub.status = Subscription.Status.CLOSED
            sub.save(update_fields=['status'])
            messages.info(request, f"Subscription {sub.subscription_number} closed.")

    elif action == 'bill_now' and is_staff:
        inv, created = generate_invoice_for_subscription(sub, billing_date=today)
        if created:
            messages.success(request, f"Invoice {inv.invoice_number} generated for {sub.subscription_number}!")
            return redirect('invoice_detail', pk=inv.pk)
        elif inv:
            messages.info(request, f"Invoice {inv.invoice_number} already exists for this billing cycle (idempotent check prevented duplicate billing).")
            return redirect('invoice_detail', pk=inv.pk)
        else:
            messages.warning(request, "Could not generate invoice (check line items or auto-close expiry).")

    return redirect('subscription_detail', pk=sub.pk)


@user_passes_test(is_staff_or_admin)
def invoice_list(request):
    status_filter = request.GET.get('status', '')
    overdue_only = request.GET.get('overdue', '')
    today = timezone.now().date()

    qs = Invoice.objects.select_related('customer', 'subscription', 'applied_discount').order_by('-issue_date', '-id')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if overdue_only == '1':
        qs = qs.filter(status=Invoice.Status.CONFIRMED, due_date__lt=today)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'core/invoice_list.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'overdue_only': overdue_only,
        'statuses': Invoice.Status.choices,
        'today': today,
    })


@user_passes_test(is_staff_or_admin)
def trigger_billing_batch(request):
    if request.method == 'POST':
        summary = run_billing_day_batch()
        messages.success(
            request,
            f"Billing Day Batch Complete: {summary['created']} new invoices created, "
            f"{summary['skipped']} duplicate cycles skipped, {summary['closed']} expired subscriptions auto-closed."
        )
    return redirect('invoice_list')


@login_required
def invoice_detail(request, pk):
    inv = get_object_or_404(
        Invoice.objects.select_related('customer', 'subscription', 'applied_discount')
        .prefetch_related('lines__product', 'payments__recorded_by'),
        pk=pk
    )
    if not request.user.is_staff_role() and inv.customer != request.user:
        messages.error(request, "Access denied.")
        return redirect('customer_portal')

    if request.method == 'POST' and request.user.is_staff_role():
        pay_form = PaymentForm(request.POST)
        if pay_form.is_valid():
            payment = pay_form.save(commit=False)
            payment.invoice = inv
            payment.recorded_by = request.user
            payment.save()
            messages.success(request, f"Payment of ₹{payment.amount} recorded against {inv.invoice_number}.")
            return redirect('invoice_detail', pk=inv.pk)
    else:
        pay_form = PaymentForm(initial={'amount': inv.amount_due, 'payment_date': timezone.now().date()})

    return render(request, 'core/invoice_detail.html', {
        'inv': inv,
        'pay_form': pay_form,
    })


@user_passes_test(is_staff_or_admin)
def invoice_action(request, pk, action):
    inv = get_object_or_404(Invoice.objects.select_related('customer'), pk=pk)

    if action == 'confirm':
        inv.status = Invoice.Status.CONFIRMED
        inv.save(update_fields=['status'])
        messages.success(request, f"Invoice {inv.invoice_number} confirmed.")
    elif action == 'cancel':
        inv.status = Invoice.Status.CANCELLED
        inv.save(update_fields=['status'])
        messages.warning(request, f"Invoice {inv.invoice_number} cancelled.")
    elif action == 'send_email':
        send_mail(
            subject=f"Invoice {inv.invoice_number} from Brightloop Software",
            message=(
                f"Hello {inv.customer.first_name or inv.customer.username},\n\n"
                f"Your invoice {inv.invoice_number} for ₹{inv.total_amount} is ready.\n"
                f"Due Date: {inv.due_date}\n\nThank you,\nBrightloop Software"
            ),
            from_email="billing@brightloop.io",
            recipient_list=[inv.customer.email],
            fail_silently=True,
        )
        messages.success(request, f"Invoice {inv.invoice_number} emailed to {inv.customer.email} (logged to console).")

    return redirect('invoice_detail', pk=inv.pk)


@login_required
def customer_portal(request):
    """Self-service portal where customers view and manage their own subscriptions and invoices."""
    my_subs = Subscription.objects.filter(customer=request.user).select_related('plan', 'discount_rule').order_by('-created_at')
    my_invoices = Invoice.objects.filter(customer=request.user).select_related('subscription').order_by('-issue_date')
    return render(request, 'core/customer_portal.html', {
        'my_subs': my_subs,
        'my_invoices': my_invoices,
    })