# Brightloop Software — Subscription Management System

A unified recurring billing, subscription lifecycle, and revenue reporting platform built for the **Odoo x FLUX Lucknow Hackathon '26 Virtual Round (October 31, 2026)**.

---

## 🛠️ Tech Architecture & Features
- **Pure Django & Tailwind CSS (CDN):** Fast, lightweight single-app (`core`) architecture with zero bloat, ensuring clean commit timestamps, SQLite database usage, and no Docker requirement.
- **Strict Role-Based Access Control (RBAC):** Distinct permissions for **Admin** (system configuration, staff provisioning, catalog setup), **Internal Staff** (quotations, subscriptions, billing batches, payment reconciliation), and **Customers** (isolated self-service portal).
- **Security & Validators:** Unique email enforcement, custom password validator requiring >8 characters with uppercase, lowercase, and special characters, and secure password recovery flows.
- **Product Variants & Plans:** Attribute-based variant pricing (e.g., choosing the `Odoo` brand automatically adds `+₹560`) and plan-specific lifecycle rules (`auto_close`, `can_close_early`, `can_pause`, `can_renew`).
- **Idempotent Billing Day Engine:** Automatically generates cycle invoices with taxes and discount rules applied, while strictly preventing duplicate billing through database row locking (`select_for_update`).
- **Finance Lead Dashboard:** Sub-2-second indexed reporting on active subscriptions, collected revenue, outstanding balances, and overdue invoices.

---

## 🚀 Quick Setup Guide for Evaluators

### 1. Clone & Setup Virtual Environment
```bash
git clone https://github.com/higo-odoo/Subscription-Management-System.git
cd Subscription-Management-System

python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Database Migrations
```bash
python manage.py migrate
```

### 4. Why Run the Seeder? (Important Note on Accounts)
The public user registration page (`/signup/`) is strictly restricted to creating **Customer** accounts. 

To test the **Admin Dashboard**, **Staff Operations**, and **Catalog Configuration**, you must run the demo seeder script. This seeds the database with pre-configured products, variants (`+₹560` Odoo brand), plans, active subscriptions, overdue invoices, and privileged internal accounts.

Run the seeder command:
```bash
python manage.py seed_brightloop
```

### 5. Start the Development Server
```bash
python manage.py runserver
```
Open your browser and navigate to: **`http://127.0.0.1:8000/`**

---

## 🔑 Pre-Seeded Demo Credentials

Use these accounts to test the different permission tiers during the demo:

| Role | Login Email | Password | What You Can Test |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@brightloop.io` | `Brightloop@123` | Full system control, catalog setup, tax/discount rules, and adding new internal staff. |
| **Internal Staff** | `sales@brightloop.io` | `Brightloop@123` | Fast quote generation from templates, subscription lifecycle transitions, running the Billing Day batch, and recording payments. |
| **Customer 1** | `founder@smallshop.in` | `Customer@123` | Customer Portal (SMB Monthly Flex Plan with an overdue invoice to test self-service review). |
| **Customer 2** | `cto@apexcorp.in` | `Customer@123` | Customer Portal (Enterprise Annual Contract with bulk discount and paid invoice history). |

---

## 📧 Email Configuration & Password Reset (Console vs. Production)

### 📌 For Demo & Evaluation (Current Setup)
By default in `brightloop/settings.py`, the email backend is set to **Console Mode**:
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```
* **Why?** When you test the **Forgot Password** or **Send Invoice Email** features, no external SMTP server is required. The password reset link and invoice notification emails will print directly into your terminal console window where `runserver` is running, allowing instant evaluation.

### 🏭 For Production Deployment
To send actual emails to users via Gmail or other transactional providers in a live production environment, update `brightloop/settings.py`:

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-production-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-google-app-password'  # Use an App Password, not your login password
DEFAULT_FROM_EMAIL = 'Brightloop Billing <billing@brightloop.io>'
```