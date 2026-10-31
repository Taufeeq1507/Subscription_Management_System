from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Auth & Password Reset
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', views.signup_view, name='signup'),
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='core/password_reset.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='core/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='core/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='core/password_reset_complete.html'), name='password_reset_complete'),

    # Core Screens
    path('', views.dashboard, name='dashboard'),
    path('staff/', views.manage_staff, name='manage_staff'),
    path('catalog/', views.catalog_view, name='catalog'),

    # Subscriptions
    path('subscriptions/', views.subscription_list, name='subscription_list'),
    path('subscriptions/<int:pk>/', views.subscription_detail, name='subscription_detail'),
    path('subscriptions/<int:pk>/action/<str:action>/', views.subscription_transition, name='subscription_transition'),

    # Invoices & Automated Billing Engine
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/run-batch/', views.trigger_billing_batch, name='trigger_billing_batch'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/action/<str:action>/', views.invoice_action, name='invoice_action'),

    # Customer Self-Service Portal
    path('portal/', views.customer_portal, name='customer_portal'),
]