"""
services.py — the single source of truth for report numbers.

build_report_data(user, start, end) -> dict
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from Finance.models import Budget, Expense, Income, TransactionLogs


# Dashboard palette (must match charts.py and Dashboard.html)
PALETTE = ['#E85D91', '#17161A', '#2E9E6E', '#E2645B', '#F3AFC9', '#837C70', '#D9CFB8']


def _expense_by_category(user, start, end):
    """Return list of {category, total, pct} sorted desc, top 6 + Others."""
    cats = list(
        Expense.objects.filter(user=user, date__gte=start, date__lte=end)
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    total = sum(c['total'] for c in cats) or Decimal('0')
    rows = [(c['category'], c['total']) for c in cats[:6]]
    if len(cats) > 6:
        rows.append(('Others', sum(c['total'] for c in cats[6:])))
    return [
        {
            'category': label,
            'total': value,
            'pct': round(float(value / total * 100), 1) if total else 0,
            'color': PALETTE[i % len(PALETTE)],
        }
        for i, (label, value) in enumerate(rows)
    ], float(total)


def _income_by_category(user, start, end):
    """Return list of {category, total, pct} sorted desc."""
    cats = list(
        Income.objects.filter(user=user, date__gte=start, date__lte=end)
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    total = sum(c['total'] for c in cats) or Decimal('0')
    rows = [(c['category'], c['total']) for c in cats[:6]]
    if len(cats) > 6:
        rows.append(('Others', sum(c['total'] for c in cats[6:])))
    return [
        {
            'category': label,
            'total': value,
            'pct': round(float(value / total * 100), 1) if total else 0,
        }
        for label, value in rows
    ], float(total)


def _daily_series(user, start, end):
    """Day-by-day income and expense totals."""
    inc_qs = (
        Income.objects.filter(user=user, date__gte=start, date__lte=end)
        .values('date').annotate(total=Sum('amount'))
    )
    exp_qs = (
        Expense.objects.filter(user=user, date__gte=start, date__lte=end)
        .values('date').annotate(total=Sum('amount'))
    )
    inc_map = {r['date']: float(r['total']) for r in inc_qs}
    exp_map = {r['date']: float(r['total']) for r in exp_qs}

    delta = (end - start).days
    labels, income, expense = [], [], []
    for i in range(delta + 1):
        d = start + timedelta(days=i)
        labels.append(d.strftime('%d %b'))
        income.append(inc_map.get(d, 0.0))
        expense.append(exp_map.get(d, 0.0))
    return {'labels': labels, 'income': income, 'expense': expense}


def _monthly_series(user, start, end):
    """Month-by-month income and expense totals."""
    from django.db.models.functions import TruncMonth

    inc_qs = (
        Income.objects.filter(user=user, date__gte=start, date__lte=end)
        .annotate(month=TruncMonth('date'))
        .values('month').annotate(total=Sum('amount'))
    )
    exp_qs = (
        Expense.objects.filter(user=user, date__gte=start, date__lte=end)
        .annotate(month=TruncMonth('date'))
        .values('month').annotate(total=Sum('amount'))
    )
    inc_map = {(r['month'].date() if hasattr(r['month'], 'date') else r['month']): float(r['total']) for r in inc_qs}
    exp_map = {(r['month'].date() if hasattr(r['month'], 'date') else r['month']): float(r['total']) for r in exp_qs}

    # Build month list from start to end
    labels, income, expense = [], [], []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        d = date(year, month, 1)
        labels.append(d.strftime('%b %Y'))
        income.append(inc_map.get(d, 0.0))
        expense.append(exp_map.get(d, 0.0))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return {'labels': labels, 'income': income, 'expense': expense}


def _previous_period(start, end):
    """Return (prev_start, prev_end) for the previous equivalent window."""
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    return prev_start, prev_end


def _period_label(start, end):
    if start.year == end.year and start.month == end.month:
        return start.strftime('%B %Y')
    if start.month == 1 and end.month == 12 and start.year == end.year:
        return str(start.year)
    return f'{start.strftime("%d %b %Y")} – {end.strftime("%d %b %Y")}'


def build_report_data(user, start: date, end: date) -> dict:
    """
    Compute all numbers needed for a report covering [start, end] (inclusive).
    Returns a dict suitable for template rendering.
    """
    # ---- Income / Expense totals ----
    total_income_dec = (
        Income.objects.filter(user=user, date__gte=start, date__lte=end)
        .aggregate(s=Sum('amount'))['s'] or Decimal('0')
    )
    total_expense_dec = (
        Expense.objects.filter(user=user, date__gte=start, date__lte=end)
        .aggregate(s=Sum('amount'))['s'] or Decimal('0')
    )
    total_income = float(total_income_dec)
    total_expense = float(total_expense_dec)
    balance = total_income - total_expense
    savings_rate = round(balance / total_income * 100, 1) if total_income > 0 else None

    # ---- Category breakdowns ----
    by_category, _ = _expense_by_category(user, start, end)
    income_by_category, _ = _income_by_category(user, start, end)

    # ---- Time series ----
    delta_days = (end - start).days
    if delta_days > 60:
        series = _monthly_series(user, start, end)
    else:
        series = _daily_series(user, start, end)

    # ---- Top 5 individual expenses ----
    top_expenses = list(
        Expense.objects.filter(user=user, date__gte=start, date__lte=end)
        .order_by('-amount')[:5]
        .values('date', 'item_name', 'category', 'amount')
    )

    # ---- Transactions (capped at 100 for PDF) ----
    transactions = list(
        TransactionLogs.objects.filter(user=user, date__gte=start, date__lte=end)
        .order_by('-date', '-created_at')
    )
    transactions_total = len(transactions)
    transactions_display = transactions[:100]

    # ---- Budget status ----
    budgets = Budget.objects.filter(user=user, month__gte=start, month__lte=end)
    budget_status = []
    for b in budgets:
        spent = float(
            Expense.objects.filter(
                user=user,
                category=b.category,
                date__year=b.month.year,
                date__month=b.month.month,
            ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        )
        limit = float(b.limit_amount)
        budget_status.append({
            'category': b.category,
            'month': b.month,
            'limit': limit,
            'spent': spent,
            'pct': round(spent / limit * 100, 1) if limit else 0,
        })

    # ---- Previous period ----
    prev_start, prev_end = _previous_period(start, end)
    prev_income = float(
        Income.objects.filter(user=user, date__gte=prev_start, date__lte=prev_end)
        .aggregate(s=Sum('amount'))['s'] or Decimal('0')
    )
    prev_expense = float(
        Expense.objects.filter(user=user, date__gte=prev_start, date__lte=prev_end)
        .aggregate(s=Sum('amount'))['s'] or Decimal('0')
    )
    prev_by_cat, _ = _expense_by_category(user, prev_start, prev_end)
    previous = {
        'total_income': prev_income,
        'total_expense': prev_expense,
        'balance': prev_income - prev_expense,
        'savings_rate': (
            round((prev_income - prev_expense) / prev_income * 100, 1)
            if prev_income > 0 else None
        ),
        'by_category': prev_by_cat,
        'label': _period_label(prev_start, prev_end),
        'start': prev_start,
        'end': prev_end,
    }

    # ---- Daily spend for projection (current month only) ----
    today = date.today()
    avg_daily_spend = None
    projected_month_end = None
    if start.year == today.year and start.month == today.month and start.day == 1:
        days_so_far = (today - start).days + 1
        if days_so_far > 0 and total_expense > 0:
            avg_daily_spend = total_expense / days_so_far
            days_in_month = calendar.monthrange(today.year, today.month)[1]
            projected_month_end = round(avg_daily_spend * days_in_month, 2)

    return {
        'period': {
            'start': start,
            'end': end,
            'label': _period_label(start, end),
        },
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
        'savings_rate': savings_rate,
        'by_category': by_category,
        'income_by_category': income_by_category,
        'series': series,
        'top_expenses': top_expenses,
        'transactions': transactions_display,
        'transactions_total': transactions_total,
        'budget_status': budget_status,
        'previous': previous,
        'avg_daily_spend': avg_daily_spend,
        'projected_month_end': projected_month_end,
        'generated_at': today,
    }
