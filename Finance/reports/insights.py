"""
insights.py — rule-based insight generation.

generate_insights(data) -> list[dict]

Each dict has:  { 'level': 'info' | 'good' | 'warn', 'text': str }

Rules (up to 6, ordered warn → good → info):
  1. Spending change vs previous period
  2. Savings rate (below 10% → warn, above 30% → good)
  3. Top expense category share + change
  4. Fastest growing expense category
  5. Budget alerts (≥80% → warn, >100% → warn)
  6. Largest single expense
  7. No-income warning
  8. Monthly projection (current month only)
"""
from __future__ import annotations

from datetime import date


def generate_insights(data: dict) -> list[dict]:
    raw: list[dict] = []

    total_expense = data.get('total_expense', 0)
    total_income = data.get('total_income', 0)
    savings_rate = data.get('savings_rate')
    previous = data.get('previous', {})
    by_category = data.get('by_category', [])
    budget_status = data.get('budget_status', [])
    top_expenses_raw = data.get('top_expenses', [])
    period_label = data['period']['label']

    prev_expense = previous.get('total_expense', 0)
    prev_label = previous.get('label', 'the previous period')
    prev_by_cat = {c['category']: c for c in previous.get('by_category', [])}

    # ── 1. Spending change ────────────────────────────────────────────────
    if prev_expense > 0 and total_expense > 0:
        change_pct = round((total_expense - prev_expense) / prev_expense * 100, 1)
        if abs(change_pct) > 10:
            direction = 'up' if change_pct > 0 else 'down'
            level = 'warn' if change_pct > 0 else 'good'
            raw.append({
                'level': level,
                'text': (
                    f'Spending is {direction} {abs(change_pct):.0f}% '
                    f'compared to {prev_label}.'
                ),
            })

    # ── 2. Savings rate ───────────────────────────────────────────────────
    if savings_rate is not None:
        if savings_rate < 10:
            raw.append({
                'level': 'warn',
                'text': (
                    f'Your savings rate is {savings_rate}%. '
                    'Try to save at least 10% of your income.'
                ),
            })
        elif savings_rate > 30:
            raw.append({
                'level': 'good',
                'text': (
                    f'Great savings rate of {savings_rate}%! '
                    'You\'re saving more than 30% of your income.'
                ),
            })

    # ── 3. Top expense category ───────────────────────────────────────────
    if by_category:
        top_cat = by_category[0]
        cat_name = top_cat['category']
        cat_pct = top_cat['pct']
        prev_cat = prev_by_cat.get(cat_name)
        change_str = ''
        if prev_cat and prev_cat['total'] > 0 and top_cat['total'] > 0:
            cat_chg = round(
                (float(top_cat['total']) - float(prev_cat['total']))
                / float(prev_cat['total']) * 100,
                0,
            )
            if abs(cat_chg) >= 5:
                direction = 'up' if cat_chg > 0 else 'down'
                change_str = f', {direction} {abs(cat_chg):.0f}% vs {prev_label}'
        raw.append({
            'level': 'info',
            'text': (
                f'{cat_name} is your biggest spending category '
                f'({cat_pct}% of total{change_str}).'
            ),
        })

    # ── 4. Fastest growing category ──────────────────────────────────────
    MIN_AMOUNT = 100  # ignore tiny amounts
    fastest = None
    fastest_pct = 0.0
    for cat in by_category:
        prev_cat = prev_by_cat.get(cat['category'])
        if not prev_cat:
            continue
        prev_amt = float(prev_cat['total'])
        curr_amt = float(cat['total'])
        if prev_amt < MIN_AMOUNT:
            continue
        pct_chg = (curr_amt - prev_amt) / prev_amt * 100
        if pct_chg > fastest_pct:
            fastest_pct = pct_chg
            fastest = cat['category']
    if fastest and fastest_pct > 20:
        raw.append({
            'level': 'info',
            'text': (
                f'{fastest} is growing fastest '
                f'(+{fastest_pct:.0f}% vs {prev_label}).'
            ),
        })

    # ── 5. Budget alerts ─────────────────────────────────────────────────
    for b in budget_status:
        pct = b['pct']
        cat = b['category']
        limit = b['limit']
        spent = b['spent']
        if pct > 100:
            over = round(spent - limit, 2)
            raw.append({
                'level': 'warn',
                'text': (
                    f'Budget for {cat} exceeded by ₹{over:,.2f} '
                    f'({pct:.0f}% used).'
                ),
            })
        elif pct >= 80:
            raw.append({
                'level': 'warn',
                'text': (
                    f'You have used {pct:.0f}% of your {cat} budget. '
                    'Watch your spending.'
                ),
            })

    # ── 6. Largest single expense ─────────────────────────────────────────
    if top_expenses_raw and total_expense > 0:
        top = top_expenses_raw[0]
        amt = float(top['amount'])
        share = round(amt / total_expense * 100, 1)
        name = top.get('item_name') or top.get('category') or 'An expense'
        raw.append({
            'level': 'info',
            'text': (
                f'Your single largest expense is "{name}" '
                f'(₹{amt:,.2f}, {share}% of total spending).'
            ),
        })

    # ── 7. No-income warning ──────────────────────────────────────────────
    if total_expense > 0 and total_income == 0:
        raw.append({
            'level': 'warn',
            'text': (
                'No income recorded for this period, '
                'but expenses are present.'
            ),
        })

    # ── 8. Monthly projection ─────────────────────────────────────────────
    projected = data.get('projected_month_end')
    if projected is not None:
        raw.append({
            'level': 'info',
            'text': (
                f'At your current pace, you\'re on track to spend '
                f'₹{projected:,.2f} by month end.'
            ),
        })

    # ── Sort: warn first, then good, then info; cap at 6 ─────────────────
    order = {'warn': 0, 'good': 1, 'info': 2}
    raw.sort(key=lambda x: order.get(x['level'], 3))
    return raw[:6]
