from decimal import Decimal
from datetime import date
from Finance.reports.services import build_report_data


def current_month_range(today=None):
    """Return (first_day_of_month, today)."""
    today = today or date.today()
    return today.replace(day=1), today


def budget_status(user, profile, today=None):
    """Compare this month's spending with the user's monthly budget."""
    start, end = current_month_range(today)
    spent = Decimal(str(build_report_data(user, start, end)['total_expense']))
    budget = profile.monthly_budget

    if not budget:
        return {'has_budget': False, 'spent': spent, 'start': start, 'end': end}

    budget = Decimal(str(budget))
    percent_used = round(spent / budget * 100, 1)
    return {
        'has_budget': True,
        'spent': spent,
        'budget': budget,
        'remaining': budget - spent,
        'over_by': spent - budget,
        'percent_used': percent_used,
        'is_over': spent > budget,
        'start': start,
        'end': end,
    }