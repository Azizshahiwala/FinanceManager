"""
populate_dummy_data.py
Populates the FinanceManager database with realistic dummy entries covering:
- 2025: January through December
- 2026: January through the current month
- Stable, varied income and expense entries with periodic salary increases
- Finance goals covering manual/automatic modes and active/completed statuses

Targets accounts: 'Aziz', 'Admin', and 'Preeti' (or user specified via CLI).
Preserves ALL existing database entries without overwriting or deleting them.

Usage:
    python populate_dummy_data.py
    python populate_dummy_data.py Aziz
    python populate_dummy_data.py Admin
"""

import os
import random
import sys
from datetime import date
from decimal import Decimal

# Set up Django environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'FinanceManager.settings')
import django
django.setup()

from django.contrib.auth.models import User
from Finance.models import Budget, Expense, FinanceGoal, Income, TransactionLogs
from Finance.services.transaction_sync import create_or_update_transaction_log


def get_target_users(username_arg=None):
    """Resolve target users. Defaults to Aziz, Admin, and Preeti."""
    if username_arg:
        user = User.objects.filter(username__iexact=username_arg).first()
        if user:
            return [user]
        print(f"User '{username_arg}' not found.")
        return []

    target_names = ['Aziz', 'Admin', 'Preeti']
    users = []
    for name in target_names:
        u = User.objects.filter(username=name).first()
        if not u:
            # Case-insensitive search fallback
            u = User.objects.filter(username__iexact=name).first()
        if u:
            users.append(u)
        else:
            # Create if user does not exist
            u = User.objects.create_user(username=name, password='password123')
            print(f"Created missing account: {name} (password: password123)")
            users.append(u)
    return users


def create_inflow(user, tx_date, category, item_name, amount, description=""):
    """Create Income and corresponding TransactionLog entry."""
    amount_dec = Decimal(str(amount))
    
    # Check if duplicate already exists to prevent duplicate spam on re-run
    existing = Income.objects.filter(
        user=user, date=tx_date, category=category, item_name=item_name, amount=amount_dec
    ).first()
    if existing:
        return existing, False

    inc = Income.objects.create(
        user=user,
        type='income',
        date=tx_date,
        category=category,
        item_name=item_name,
        amount=amount_dec,
        description=description,
    )

    record_text = f"{item_name} - {description}" if description else item_name
    sys_desc = f"{user.username}, created income of {item_name}, amounted: {amount_dec}"

    inc.description = description
    inc.save(update_fields=['description'])
    create_or_update_transaction_log(user, inc, 'income')
    return inc, True


def create_outflow(user, tx_date, category, item_name, amount, quantity=1, unit="unit", description=""):
    """Create Expense and corresponding TransactionLog entry."""
    amount_dec = Decimal(str(amount))
    qty_dec = Decimal(str(quantity)) if quantity is not None else None

    # Check if duplicate already exists
    existing = Expense.objects.filter(
        user=user, date=tx_date, category=category, item_name=item_name, amount=amount_dec
    ).first()
    if existing:
        return existing, False

    exp = Expense.objects.create(
        user=user,
        type='expense',
        date=tx_date,
        category=category,
        item_name=item_name,
        quantity=qty_dec,
        unit=unit,
        amount=amount_dec,
        description=description,
    )

    record_text = f"{item_name} - {description}" if description else item_name
    unit_str = f" in {unit}(s)" if unit else ""
    sys_desc = f"{user.username}, created expense of {item_name}, amounted: {amount_dec}{unit_str}"

    exp.description = description
    exp.save(update_fields=['description'])
    create_or_update_transaction_log(user, exp, 'expense')
    return exp, True


def set_budget(user, month_date, category, limit_amount):
    """Set monthly budget limit if not already defined."""
    limit_dec = Decimal(str(limit_amount))
    b, created = Budget.objects.get_or_create(
        user=user,
        category=category,
        month=month_date,
        defaults={'limit_amount': limit_dec}
    )
    return b, created


def generate_month_data(user, year, month):
    """Generate reproducible monthly transactions with occasional salary hikes."""
    rng = random.Random(f'{user.username}:{year}-{month:02d}')
    tx_month = date(year, month, 1)

    if year == 2025:
        salary = 78000 if month <= 3 else 80000 if month <= 6 else 82500 if month <= 9 else 85000
        rent = 17000 if month <= 6 else 17500 if month <= 9 else 18000
    else:
        salary = 90000 if month <= 5 else 92500 if month <= 7 else 95000
        rent = 18500 if month <= 5 else 18750 if month <= 7 else 19000

    if month == 1:
        salary_note = 'Direct deposit after annual salary review'
    elif (year, month) in ((2025, 4), (2025, 7), (2026, 6), (2026, 8)):
        salary_note = 'Direct deposit after salary adjustment'
    else:
        salary_note = f'Monthly salary deposit for {tx_month.strftime("%b %Y")}'

    incomes = [
        (date(year, month, 1), 'Salary', 'Monthly Tech Salary', salary, salary_note),
        (
            date(year, month, 14),
            'Freelance',
            rng.choice([
                'Website Maintenance Project',
                'Dashboard Consulting',
                'API Integration Contract',
                'Design Review Project',
            ]),
            rng.randrange(12000, 26001, 100),
            'Part-time client milestone payment',
        ),
    ]
    if month in (3, 6, 9, 12):
        incomes.append((
            date(year, month, 25),
            'Investment',
            'Quarterly Investment Dividend',
            rng.randrange(1800, 5201, 100),
            'Quarterly dividend payout',
        ))

    expenses = [
        (date(year, month, 2), 'Bills', 'Apartment Rent', rent, 1, 'month', 'Monthly home rent'),
        (
            date(year, month, 5),
            'Food',
            'Grocery & Household Shopping',
            rng.randrange(3900, 5701, 50),
            rng.randrange(8, 15),
            'kg',
            'Groceries and household essentials',
        ),
        (
            date(year, month, 8),
            'Transport',
            'Fuel & Commute',
            rng.randrange(2300, 4101, 50),
            rng.randrange(25, 41),
            'liter',
            'Fuel and regular commuting',
        ),
        (
            date(year, month, 11),
            'Bills',
            'Electricity & Utilities',
            rng.randrange(1800, 3401, 50),
            1,
            'bill',
            'Monthly household utility charges',
        ),
        (
            date(year, month, 15),
            'Food',
            'Dining Out',
            rng.randrange(1200, 3401, 50),
            1,
            'meal',
            'Occasional meal out with friends',
        ),
        (
            date(year, month, 19),
            'Bills',
            'Internet & Mobile Services',
            rng.randrange(1100, 1801, 50),
            1,
            'bundle',
            'Monthly connectivity services',
        ),
    ]
    if rng.random() < 0.65:
        category, item, amount, unit, description = rng.choice([
            ('Shopping', 'Clothing & Personal Items', rng.randrange(1500, 6501, 100), 'purchase', 'Personal or household purchase'),
            ('Medical', 'Pharmacy & Healthcare', rng.randrange(700, 3601, 100), 'visit', 'Routine health and pharmacy expense'),
            ('Education', 'Books & Online Learning', rng.randrange(900, 4201, 100), 'course', 'Learning and professional development'),
        ])
        expenses.append((
            date(year, month, 23), category, item, amount, 1, unit, description
        ))
    return incomes, expenses


def create_finance_goals(user):
    """Create one goal for each mode/status combination without overwriting existing goals."""
    goals = [
        {
            'title': 'Dummy Emergency Fund - Manual Active',
            'target_amount': Decimal('120000.00'),
            'allocated': Decimal('25000.00'),
            'deadline': date(2027, 6, 30),
            'mode': 'manual',
            'status': 'active',
        },
        {
            'title': 'Dummy Home Upgrade - Automatic Active',
            'target_amount': Decimal('80000.00'),
            'allocated': Decimal('0.00'),
            'deadline': date(2027, 12, 31),
            'mode': 'auto',
            'status': 'active',
        },
        {
            'title': 'Dummy Vacation Fund - Manual Completed',
            'target_amount': Decimal('45000.00'),
            'allocated': Decimal('45000.00'),
            'deadline': date(2026, 6, 30),
            'mode': 'manual',
            'status': 'completed',
        },
        {
            'title': 'Dummy Laptop Fund - Automatic Completed',
            'target_amount': Decimal('60000.00'),
            'allocated': Decimal('60000.00'),
            'deadline': date(2026, 9, 30),
            'mode': 'auto',
            'status': 'completed',
        },
    ]
    created_count = 0
    for goal in goals:
        _, created = FinanceGoal.objects.get_or_create(
            user=user,
            title=goal['title'],
            defaults=goal,
        )
        if created:
            created_count += 1
    return created_count


def populate_user_data(user):
    print(f"\n>>> Populating financial data for account: '{user.username}'")
    print("-" * 65)

    created_incomes = 0
    created_expenses = 0
    created_budgets = 0

    # -------------------------------------------------------------------------
    # 1. Monthly budget targets from January 2025 through the current month.
    # -------------------------------------------------------------------------
    today = date.today()
    budget_months = []
    year, month = 2025, 1
    while (year, month) <= (today.year, today.month):
        budget_months.append(date(year, month, 1))
        month += 1
        if month == 13:
            year += 1
            month = 1

    budget_caps = {
        'Food': 16000.00,
        'Transport': 6500.00,
        'Bills': 12000.00,
        'Shopping': 10000.00,
        'Medical': 5000.00,
    }

    for b_month in budget_months:
        for cat, limit in budget_caps.items():
            _, was_created = set_budget(user, b_month, cat, limit)
            if was_created:
                created_budgets += 1

    # -------------------------------------------------------------------------
    # 2. Entries for Year 2025 — Month 1: October 2025
    # -------------------------------------------------------------------------
    incomes_oct_2025 = [
        (date(2025, 10, 1), 'Salary', 'Monthly Tech Salary', 85000.00, 'Direct deposit for Oct'),
        (date(2025, 10, 14), 'Freelance', 'UI/UX Client Project', 22500.00, 'Fintech app wireframes milestone'),
        (date(2025, 10, 26), 'Investment', 'Stock Dividend Payout', 4200.00, 'Quarterly equity dividend'),
    ]
    expenses_oct_2025 = [
        (date(2025, 10, 2), 'Bills', 'Apartment Rent', 18000.00, 1, 'month', 'October house rental'),
        (date(2025, 10, 4), 'Food', 'Organic Supermarket Grocery', 4850.00, 12, 'kg', 'Pantry staples and vegetables'),
        (date(2025, 10, 7), 'Transport', 'Fuel Refill & Car Wash', 3200.00, 35, 'liter', 'Shell petrol pump'),
        (date(2025, 10, 10), 'Bills', 'Electricity & Power Bill', 2450.00, 1, 'bill', 'State electricity board'),
        (date(2025, 10, 12), 'Food', 'Family Weekend Dinner', 2850.00, 1, 'order', 'Bistro restaurant dine-out'),
        (date(2025, 10, 16), 'Shopping', 'Noise Cancelling Headphones', 6999.00, 1, 'unit', 'Office workstation gear'),
        (date(2025, 10, 19), 'Medical', 'Dental Hygiene & Checkup', 1800.00, 1, 'session', 'Clinic consultation'),
        (date(2025, 10, 23), 'Food', 'Fresh Produce & Fruits', 1650.00, 6, 'kg', 'Weekly market farmer stall'),
        (date(2025, 10, 28), 'Bills', 'Fiber Broadband Internet', 1199.00, 1, 'month', '300 Mbps unlimited plan'),
        (date(2025, 10, 30), 'Transport', 'Metro Smart Card Recharge', 1200.00, 1, 'pass', 'Monthly travel commuter card'),
    ]

    # -------------------------------------------------------------------------
    # 3. Entries for Year 2025 — Month 2: November 2025
    # -------------------------------------------------------------------------
    incomes_nov_2025 = [
        (date(2025, 11, 1), 'Salary', 'Monthly Tech Salary', 85000.00, 'Direct deposit for Nov'),
        (date(2025, 11, 18), 'Freelance', 'Fullstack API Integration', 19000.00, 'Django backend development'),
        (date(2025, 11, 25), 'Other', 'Old Electronics Sale', 5500.00, 'Sold old graphics card'),
    ]
    expenses_nov_2025 = [
        (date(2025, 11, 2), 'Bills', 'Apartment Rent', 18000.00, 1, 'month', 'November house rental'),
        (date(2025, 11, 5), 'Food', 'Monthly Wholesale Groceries', 5400.00, 15, 'kg', 'Rice, flour, cooking oil'),
        (date(2025, 11, 8), 'Transport', 'Fuel Top-up', 2900.00, 30, 'liter', 'Commute fuel'),
        (date(2025, 11, 12), 'Bills', 'Water & Utility Charges', 850.00, 1, 'bill', 'Society maintenance utility'),
        (date(2025, 11, 15), 'Shopping', 'Winter Thermal Jacket', 4200.00, 1, 'unit', 'Winter wardrobe essential'),
        (date(2025, 11, 19), 'Food', 'Bakery & Coffee Outing', 1350.00, 4, 'item', 'Cafe workspace session'),
        (date(2025, 11, 22), 'Education', 'Cloud Architecture Certification', 4900.00, 1, 'course', 'Professional upskilling exam'),
        (date(2025, 11, 26), 'Medical', 'Prescription Pharmacy Medicines', 1450.00, 1, 'pack', 'Seasonal wellness medicines'),
        (date(2025, 11, 28), 'Bills', 'Mobile Cellular Postpaid', 999.00, 1, 'month', 'Primary 5G mobile billing'),
    ]

    # -------------------------------------------------------------------------
    # 4. Entries for Year 2025 — Month 3: December 2025
    # -------------------------------------------------------------------------
    incomes_dec_2025 = [
        (date(2025, 12, 1), 'Salary', 'Monthly Tech Salary', 85000.00, 'Direct deposit for Dec'),
        (date(2025, 12, 20), 'Business', 'Year-End Performance Bonus', 45000.00, 'Annual milestone incentive'),
        (date(2025, 12, 28), 'Investment', 'Mutual Fund Return Withdrawal', 12500.00, 'Short-term debt fund redemption'),
    ]
    expenses_dec_2025 = [
        (date(2025, 12, 2), 'Bills', 'Apartment Rent', 18000.00, 1, 'month', 'December house rental'),
        (date(2025, 12, 6), 'Food', 'Gourmet Holiday Dinner', 4600.00, 1, 'meal', 'Festive season team dinner'),
        (date(2025, 12, 9), 'Food', 'Weekly Groceries & Dairy', 3800.00, 8, 'kg', 'Cheeses and winter groceries'),
        (date(2025, 12, 13), 'Shopping', 'Holiday Gifts & Festive Decor', 8500.00, 5, 'items', 'Year-end gifts for family'),
        (date(2025, 12, 17), 'Transport', 'Highway Toll & Highway Fuel', 4100.00, 40, 'liter', 'Weekend road trip fuel'),
        (date(2025, 12, 21), 'Bills', 'Electricity & Heating Bill', 3100.00, 1, 'bill', 'Winter season heater consumption'),
        (date(2025, 12, 24), 'Food', 'New Year Party Supplies', 3250.00, 1, 'order', 'Catering snacks and desserts'),
        (date(2025, 12, 29), 'Medical', 'Annual Comprehensive Blood Test', 2600.00, 1, 'test', 'Diagnostic preventive panel'),
    ]

    # -------------------------------------------------------------------------
    # 5. Entries for Year 2026 — Month 1: January 2026
    # -------------------------------------------------------------------------
    incomes_jan_2026 = [
        (date(2026, 1, 1), 'Salary', 'Monthly Tech Salary', 90000.00, 'Annual revised salary increment'),
        (date(2026, 1, 16), 'Freelance', 'Data Dashboard Architecture', 28000.00, 'React & Django consulting contract'),
        (date(2026, 1, 27), 'Investment', 'Fixed Deposit Quarterly Interest', 3850.00, 'Bank interest payout'),
    ]
    expenses_jan_2026 = [
        (date(2026, 1, 2), 'Bills', 'Apartment Rent', 18500.00, 1, 'month', 'January lease renewal rent'),
        (date(2026, 1, 4), 'Food', 'Supermarket Organic Supplies', 5100.00, 12, 'kg', 'Fresh grains, produce, dairy'),
        (date(2026, 1, 7), 'Transport', 'Vehicle Service & Synthetic Oil', 4800.00, 1, 'service', 'Car periodic maintenance check'),
        (date(2026, 1, 11), 'Bills', 'Fiber Broadband & Streaming Pack', 1499.00, 1, 'bundle', 'Home entertainment bundle'),
        (date(2026, 1, 14), 'Education', 'Data Science & AI Textbook Series', 3200.00, 2, 'books', 'Technical reference textbooks'),
        (date(2026, 1, 18), 'Food', 'Weekend Brunch with Friends', 2200.00, 1, 'meal', 'Artisan bakery breakfast'),
        (date(2026, 1, 22), 'Shopping', 'Ergonomic Desk Chair Upgrade', 8400.00, 1, 'unit', 'Home workstation ergonomics'),
        (date(2026, 1, 25), 'Medical', 'Eye Exam & Anti-Glare Lenses', 3500.00, 1, 'pair', 'Computer vision eyewear'),
        (date(2026, 1, 29), 'Transport', 'City Rideshare & Cabs', 1650.00, 5, 'trips', 'Airport transit and meetings'),
    ]

    # -------------------------------------------------------------------------
    # 6. Entries for Year 2026 — Month 2: February 2026
    # -------------------------------------------------------------------------
    incomes_feb_2026 = [
        (date(2026, 2, 1), 'Salary', 'Monthly Tech Salary', 90000.00, 'Direct deposit for Feb'),
        (date(2026, 2, 14), 'Freelance', 'API Security Audit Project', 24000.00, 'Penetration testing milestone'),
        (date(2026, 2, 22), 'Investment', 'Bond Coupon Yield', 5200.00, 'Semi-annual bond coupon'),
    ]
    expenses_feb_2026 = [
        (date(2026, 2, 2), 'Bills', 'Apartment Rent', 18500.00, 1, 'month', 'February house rental'),
        (date(2026, 2, 5), 'Food', 'Bulk Grocery & Household Goods', 4750.00, 10, 'kg', 'Supermarket monthly bulk run'),
        (date(2026, 2, 8), 'Transport', 'Petrol Station Fuel Refill', 3100.00, 32, 'liter', 'Daily office commute fuel'),
        (date(2026, 2, 12), 'Bills', 'Electricity & Heating Power', 2250.00, 1, 'bill', 'Power utility monthly invoice'),
        (date(2026, 2, 14), 'Food', 'Valentine Special Dinner Outing', 3600.00, 1, 'dinner', 'Fine dining restaurant'),
        (date(2026, 2, 18), 'Shopping', 'Mechanical Wireless Keyboard', 5200.00, 1, 'unit', 'Productivity peripheral'),
        (date(2026, 2, 21), 'Medical', 'Fitness Gym Membership Quarterly', 4500.00, 3, 'months', 'Health center subscription'),
        (date(2026, 2, 25), 'Transport', 'Express Train Tickets', 1850.00, 2, 'tickets', 'Intercity business trip'),
        (date(2026, 2, 27), 'Food', 'Weekend Fresh Vegetable Mart', 1400.00, 5, 'kg', 'Fresh local green market'),
    ]

    # -------------------------------------------------------------------------
    # 7. Entries for Year 2026 — Month 3: August 2026
    # -------------------------------------------------------------------------
    incomes_aug_2026 = [
        (date(2026, 8, 1), 'Salary', 'Monthly Tech Salary', 95000.00, 'Direct deposit for Aug'),
        (date(2026, 8, 12), 'Freelance', 'Mobile App Dashboard', 21500.00, 'Analytics dashboard delivery'),
        (date(2026, 8, 25), 'Investment', 'Equity Dividend Payout', 4600.00, 'Quarterly dividend distribution'),
    ]
    expenses_aug_2026 = [
        (date(2026, 8, 2), 'Bills', 'Apartment Rent', 19000.00, 1, 'month', 'August house rental'),
        (date(2026, 8, 5), 'Food', 'Monthly Grocery Shopping', 4950.00, 11, 'kg', 'Pantry staples and fresh produce'),
        (date(2026, 8, 8), 'Transport', 'Fuel Refill', 3150.00, 34, 'liter', 'Daily commute fuel'),
        (date(2026, 8, 11), 'Bills', 'Electricity & Utility Bill', 2380.00, 1, 'bill', 'Monthly electricity charges'),
        (date(2026, 8, 15), 'Food', 'Dinner with Friends', 2650.00, 1, 'meal', 'Weekend restaurant outing'),
        (date(2026, 8, 19), 'Shopping', 'Running Shoes', 5800.00, 1, 'pair', 'Replacement workout shoes'),
        (date(2026, 8, 23), 'Medical', 'Pharmacy & Wellness Supplies', 1250.00, 1, 'order', 'Monthly health essentials'),
        (date(2026, 8, 28), 'Bills', 'Home Broadband Plan', 1299.00, 1, 'month', 'Monthly internet subscription'),
    ]

    # -------------------------------------------------------------------------
    # 8. Entries for Year 2026 — Month 4: September 2026
    # -------------------------------------------------------------------------
    incomes_sep_2026 = [
        (date(2026, 9, 1), 'Salary', 'Monthly Tech Salary', 95000.00, 'Direct deposit for Sep'),
        (date(2026, 9, 14), 'Freelance', 'Cloud Migration Consulting', 26000.00, 'Infrastructure migration milestone'),
        (date(2026, 9, 26), 'Other', 'Online Course Royalties', 3200.00, 'Learning course sales payout'),
    ]
    expenses_sep_2026 = [
        (date(2026, 9, 2), 'Bills', 'Apartment Rent', 19000.00, 1, 'month', 'September house rental'),
        (date(2026, 9, 5), 'Food', 'Weekly Grocery & Dairy Run', 5200.00, 12, 'kg', 'Groceries and household staples'),
        (date(2026, 9, 8), 'Transport', 'Fuel & Vehicle Top-up', 3300.00, 35, 'liter', 'Monthly commute fuel'),
        (date(2026, 9, 11), 'Bills', 'Electricity & Water Charges', 2520.00, 1, 'bill', 'Monthly utility charges'),
        (date(2026, 9, 15), 'Education', 'Online Cloud Certification', 4100.00, 1, 'course', 'Professional development course'),
        (date(2026, 9, 19), 'Food', 'Cafe & Brunch Outing', 1850.00, 1, 'meal', 'Weekend cafe visit'),
        (date(2026, 9, 23), 'Shopping', 'Desk Organizer & Supplies', 2150.00, 1, 'set', 'Home office organization'),
        (date(2026, 9, 28), 'Bills', 'Mobile Phone Plan', 1099.00, 1, 'month', 'Monthly mobile service'),
    ]

    # -------------------------------------------------------------------------
    # 9. Entries for Year 2026 — Month 5: October 2026
    # -------------------------------------------------------------------------
    incomes_oct_2026 = [
        (date(2026, 10, 1), 'Salary', 'Monthly Tech Salary', 95000.00, 'Direct deposit for Oct'),
        (date(2026, 10, 16), 'Freelance', 'Finance Platform Integration', 23500.00, 'Payment integration delivery'),
        (date(2026, 10, 27), 'Investment', 'Fixed Deposit Interest', 4200.00, 'Quarterly interest credit'),
    ]
    expenses_oct_2026 = [
        (date(2026, 10, 2), 'Bills', 'Apartment Rent', 19000.00, 1, 'month', 'October house rental'),
        (date(2026, 10, 5), 'Food', 'Supermarket Grocery & Produce', 5100.00, 12, 'kg', 'Monthly pantry and produce'),
        (date(2026, 10, 8), 'Transport', 'Fuel Station Refill', 3400.00, 36, 'liter', 'Daily commute fuel'),
        (date(2026, 10, 11), 'Bills', 'Electricity & Internet Bills', 3650.00, 1, 'bundle', 'Monthly home utilities'),
        (date(2026, 10, 15), 'Shopping', 'Work Backpack', 3900.00, 1, 'unit', 'Laptop commuter backpack'),
        (date(2026, 10, 19), 'Food', 'Family Dinner', 3250.00, 1, 'meal', 'Weekend family restaurant dinner'),
        (date(2026, 10, 23), 'Medical', 'Routine Health Checkup', 2100.00, 1, 'visit', 'Preventive clinic checkup'),
        (date(2026, 10, 28), 'Bills', 'Streaming & Mobile Subscriptions', 1499.00, 1, 'bundle', 'Monthly entertainment and phone'),
    ]

    # -------------------------------------------------------------------------
    # 10. Entries for Year 2026 — Month 6: November 2026
    # -------------------------------------------------------------------------
    incomes_nov_2026 = [
        (date(2026, 11, 1), 'Salary', 'Monthly Tech Salary', 95000.00, 'Direct deposit for Nov'),
        (date(2026, 11, 13), 'Freelance', 'Business Reporting Automation', 28500.00, 'Monthly reporting workflow delivery'),
        (date(2026, 11, 24), 'Other', 'Used Monitor Sale', 6200.00, 'Sale of old workstation monitor'),
    ]
    expenses_nov_2026 = [
        (date(2026, 11, 2), 'Bills', 'Apartment Rent', 19000.00, 1, 'month', 'November house rental'),
        (date(2026, 11, 5), 'Food', 'Monthly Grocery & Household Shop', 5350.00, 13, 'kg', 'Groceries and household supplies'),
        (date(2026, 11, 8), 'Transport', 'Fuel & Metro Recharge', 3600.00, 1, 'bundle', 'Monthly commuting expenses'),
        (date(2026, 11, 11), 'Bills', 'Electricity & Water Utility', 2480.00, 1, 'bill', 'Monthly utility invoice'),
        (date(2026, 11, 15), 'Shopping', 'Winter Jacket', 6300.00, 1, 'unit', 'Cold-weather clothing'),
        (date(2026, 11, 19), 'Food', 'Coffee & Bakery Visit', 1450.00, 1, 'order', 'Cafe meeting and refreshments'),
        (date(2026, 11, 23), 'Medical', 'Prescription & Pharmacy Items', 1680.00, 1, 'order', 'Monthly prescription refill'),
        (date(2026, 11, 28), 'Bills', 'Fiber Broadband Subscription', 1299.00, 1, 'month', 'Monthly home internet service'),
    ]

    # Combine all months
    all_incomes = (
        incomes_oct_2025 + incomes_nov_2025 + incomes_dec_2025
        + incomes_jan_2026 + incomes_feb_2026
        + incomes_aug_2026 + incomes_sep_2026 + incomes_oct_2026 + incomes_nov_2026
    )
    all_expenses = (
        expenses_oct_2025 + expenses_nov_2025 + expenses_dec_2025
        + expenses_jan_2026 + expenses_feb_2026
        + expenses_aug_2026 + expenses_sep_2026 + expenses_oct_2026 + expenses_nov_2026
    )

    # Fill months without an existing salary record; seeded variation keeps reruns idempotent.
    months_with_salary = {
        (dt.year, dt.month)
        for dt, category, item, _, _ in all_incomes
        if category == 'Salary' and item == 'Monthly Tech Salary'
    }
    for month_start in budget_months:
        if (month_start.year, month_start.month) not in months_with_salary:
            month_incomes, month_expenses = generate_month_data(
                user, month_start.year, month_start.month
            )
            all_incomes.extend(month_incomes)
            all_expenses.extend(month_expenses)


    # Insert Incomes
    for dt, cat, item, amt, desc in all_incomes:
        _, was_created = create_inflow(user, dt, cat, item, amt, desc)
        if was_created:
            created_incomes += 1

    # Insert Expenses
    for dt, cat, item, amt, qty, unit, desc in all_expenses:
        _, was_created = create_outflow(user, dt, cat, item, amt, qty, unit, desc)
        if was_created:
            created_expenses += 1

    created_goals = create_finance_goals(user)

    # -------------------------------------------------------------------------
    # Print Results for this user
    # -------------------------------------------------------------------------
    print(f"  + New Budgets created:        {created_budgets}")
    print(f"  + New Income entries:         {created_incomes}")
    print(f"  + New Expense entries:        {created_expenses}")
    print(f"  + New FinanceGoal entries:    {created_goals}")
    print(f"  + New TransactionLogs:        {created_incomes + created_expenses}")

    total_inc = Income.objects.filter(user=user).count()
    total_exp = Expense.objects.filter(user=user).count()
    total_logs = TransactionLogs.objects.filter(user=user).count()
    total_budgets = Budget.objects.filter(user=user).count()
    total_goals = FinanceGoal.objects.filter(user=user).count()

    print(f"  -> Total records now for '{user.username}':")
    print(
        f"     Incomes: {total_inc} | Expenses: {total_exp} | Logs: {total_logs} "
        f"| Budgets: {total_budgets} | Goals: {total_goals}"
    )


def main():
    target_username = sys.argv[1] if len(sys.argv) > 1 else None
    target_users = get_target_users(target_username)

    if not target_users:
        print("No accounts found to populate.")
        return

    print("=" * 65)
    print("FINANCE MANAGER DUMMY DATA GENERATOR")
    print(f"Spans January 2025 through {date.today().strftime('%B %Y')}")
    print("All original database entries are strictly preserved.")
    print("=" * 65)

    for user in target_users:
        populate_user_data(user)

    print("\n" + "=" * 65)
    print("Data population completed successfully!")
    print("=" * 65)


if __name__ == '__main__':
    main()
