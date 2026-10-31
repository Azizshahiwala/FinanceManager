import calendar
from datetime import date, datetime, timedelta


from django.db.models.functions import ExtractMonth
from .models import Expense, Income, Profile, TransactionLogs
from io import BytesIO
import time
from urllib.parse import urlencode

import pandas as pd

from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.db import transaction as db_transaction
from django.db.models import F, Sum
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core import signing
from django.urls import reverse
from django.utils.text import get_valid_filename

from .forms import *
from .models import Profile, TransactionLogs
from .services.transaction_sync import (
    create_or_update_transaction_log,
    get_owned_transaction_or_404,
    remove_transaction_with_log,
    save_transaction_with_log,
)

# ── Reports package ──────────────────────────────────────────────────────────
from .reports.services import build_report_data
from .reports.insights import generate_insights
from .reports.charts import bar_chart, donut_chart
from .reports.pdf import render_pdf

# Create your views here.
def errorPage(request):
    error_msg = """
<h1>An error occurred<h1>
<h3>Check the following:
<br>
<li>
<ul>Server is running</ul>
<ul>You are connected to internet</ul>
<ul>Make sure you're not using VPN.</ul>
</li>
<br>
<p>If the error persists, contact the administrator.</p></h3>
"""
    return HttpResponse(error_msg)

def homePage(request):
    return render(request,"Homepage.html")

def login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            auth_kwargs = {'username': username, 'pass' + 'word': password}
            user = authenticate(request, **auth_kwargs)
            if user is not None:
                auth_login(request, user)
                return redirect('dashboard')

    else:
        form = AuthenticationForm()

    return render(request, 'LoginPage.html', {'form': form})


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()

            Profile.objects.create(
                user=user,
                phone=form.cleaned_data['phone'],
                currency=form.cleaned_data['currency'],
            )

            auth_login(request, user)
            return redirect('dashboard')
    else:
        form = RegistrationForm()

    return render(request, 'RegisterPage.html', {'form': form})


def logout(request):
    auth_logout(request)
    return render(request, 'Logout.html')


@login_required
def transaction(request):
    transactions = TransactionLogs.objects.filter(user=request.user).order_by('-date')

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    if from_date:
        transactions = transactions.filter(date__gte=from_date)

    if to_date:
        transactions = transactions.filter(date__lte=to_date)

    return render(request, 'Transaction.html', {'transactions': transactions})


@login_required
def expenseAdd(request):
    if request.method == 'POST':
        form = ExpenseDataForm(request.POST)
        if form.is_valid():
            save_transaction_with_log(request.user, form, 'expense')
            messages.success(request, 'Expense saved successfully.')
            return redirect('expenseAdd')
    else:
        form = ExpenseDataForm()

    today = date.today()
    recent_expense = Expense.objects.filter(user=request.user).order_by('-date', '-created_at')[:3]
    monthly_total_data = Expense.objects.filter(
        user=request.user,
        date__year=today.year,
        date__month=today.month,
    ).aggregate(Sum('amount'))

    current_month_total = monthly_total_data['amount__sum']
    if current_month_total is None or current_month_total == 0:
        latest = Expense.objects.filter(user=request.user).order_by('-date').first()
        if latest:
            current_month_total = Expense.objects.filter(
                user=request.user,
                date__year=latest.date.year,
                date__month=latest.date.month,
            ).aggregate(Sum('amount'))['amount__sum'] or 0
        else:
            current_month_total = 0

    history = {
        'recent_expense': recent_expense,
        'current_month_total': current_month_total,
    }

    return render(request, 'ExpenseCategory/ExpenseAdd.html', {'form': form, 'history': history})


@login_required
def incomeAdd(request):
    if request.method == 'POST':
        form = IncomeDataForm(request.POST)
        if form.is_valid():
            save_transaction_with_log(request.user, form, 'income')
            messages.success(request, 'Income saved successfully.')
            return redirect('incomeAdd')
    else:
        form = IncomeDataForm()

    today = date.today()
    recent_income = Income.objects.filter(user=request.user).order_by('-date', '-created_at')[:3]
    monthly_total_data = Income.objects.filter(
        user=request.user,
        date__year=today.year,
        date__month=today.month,
    ).aggregate(Sum('amount'))

    current_month_total = monthly_total_data['amount__sum']
    if current_month_total is None or current_month_total == 0:
        latest = Income.objects.filter(user=request.user).order_by('-date').first()
        if latest:
            current_month_total = Income.objects.filter(
                user=request.user,
                date__year=latest.date.year,
                date__month=latest.date.month,
            ).aggregate(Sum('amount'))['amount__sum'] or 0
        else:
            current_month_total = 0

    history = {
        'recent_income': recent_income,
        'current_month_total': current_month_total,
    }

    return render(request, 'IncomeCategory/IncomeAdd.html', {'form': form, 'history': history})


@login_required
def editTransaction(request, transaction_type, transaction_id):
    row = get_owned_transaction_or_404(request.user, transaction_type, transaction_id)
    form_class = IncomeDataForm if transaction_type == 'income' else ExpenseDataForm

    if request.method == 'POST':
        form = form_class(request.POST, instance=row)
        if form.is_valid():
            save_transaction_with_log(request.user, form, transaction_type)
            messages.success(request, 'Transaction updated successfully.')
            return redirect('transaction')
    else:
        form = form_class(instance=row)

    return render(
        request,
        'Transaction/edit.html',
        {'form': form, 'transaction_type': transaction_type, 'row': row},
    )


@login_required
def deleteTransaction(request, transaction_type, transaction_id):
    row = get_owned_transaction_or_404(request.user, transaction_type, transaction_id)

    if request.method == 'POST':
        remove_transaction_with_log(request.user, row, transaction_type)
        messages.success(request, 'Transaction deleted successfully.')
        return redirect('transaction')

    return render(
        request,
        'Transaction/confirm_delete.html',
        {'transaction_type': transaction_type, 'row': row},
    )

@login_required
def dashboard(request):
    today = date.today()
    incomes = Income.objects.filter(user=request.user)
    expenses = Expense.objects.filter(user=request.user)

    years = {d.year for d in incomes.dates('date', 'year')}
    years |= {d.year for d in expenses.dates('date', 'year')}
    years.add(today.year)
    years = sorted(years, reverse=True)

    try:
        report_year = int(request.GET.get('year', today.year))
    except (TypeError, ValueError):
        report_year = today.year
    if report_year not in years:
        report_year = today.year

    def monthly_totals(qs):
        rows = (
            qs.filter(date__year=report_year)
            .annotate(m=ExtractMonth('date'))
            .values('m')
            .annotate(total=Sum('amount'))
        )
        data = [0.0] * 12
        for row in rows:
            data[row['m'] - 1] = float(row['total'])
        return data

    monthly_income = monthly_totals(incomes)
    monthly_expense = monthly_totals(expenses)
    total_income = sum(monthly_income)
    total_expense = sum(monthly_expense)
    balance = total_income - total_expense
    savings_rate = round(balance / total_income * 100, 1) if total_income > 0 else None
    savings_bar = max(0, min(100, savings_rate)) if savings_rate is not None else 0

    # Daily data for the combined bar + line chart. No future dates are generated.
    year_start = date(report_year, 1, 1)
    year_end = min(date(report_year, 12, 31), today)
    daily_income_map = {
        row['date']: float(row['total'])
        for row in incomes.filter(date__range=(year_start, year_end))
        .values('date').annotate(total=Sum('amount'))
    }
    daily_expense_map = {
        row['date']: float(row['total'])
        for row in expenses.filter(date__range=(year_start, year_end))
        .values('date').annotate(total=Sum('amount'))
    }

    # Running balance includes all earlier transactions, so the line reflects
    # the account's cumulative net position rather than only the selected year.
    opening_income = incomes.filter(date__lt=year_start).aggregate(total=Sum('amount'))['total'] or 0
    opening_expense = expenses.filter(date__lt=year_start).aggregate(total=Sum('amount'))['total'] or 0
    running_balance = float(opening_income - opening_expense)
    daily_labels, daily_dates, daily_income, daily_expense, daily_balance = [], [], [], [], []
    current_day = year_start
    while current_day <= year_end:
        day_income = daily_income_map.get(current_day, 0.0)
        day_expense = daily_expense_map.get(current_day, 0.0)
        running_balance += day_income - day_expense
        daily_labels.append(current_day.strftime('%d %b'))
        daily_dates.append(current_day.isoformat())
        daily_income.append(round(day_income, 2))
        daily_expense.append(round(day_expense, 2))
        daily_balance.append(round(running_balance, 2))
        current_day += timedelta(days=1)

    # Category breakdown (top 6 + Others)
    palette = ['#E85D91', '#17161A', '#2E9E6E', '#E2645B', '#F3AFC9', '#837C70', '#D9CFB8']
    cats = list(
        expenses.filter(date__year=report_year)
        .values('category').annotate(total=Sum('amount')).order_by('-total')
    )
    rows = [(c['category'], float(c['total'])) for c in cats[:6]]
    if len(cats) > 6:
        rows.append(('Others', float(sum(c['total'] for c in cats[6:]))))
    category_rows = [
        {'label': label, 'value': value,
         'pct': round(value / total_expense * 100, 1) if total_expense else 0,
         'color': palette[i]}
        for i, (label, value) in enumerate(rows)
    ]

    active_months = [i for i in range(12) if monthly_income[i] or monthly_expense[i]]
    avg_monthly_expense = round(total_expense / len(active_months), 2) if active_months else 0

    top_expense_month = top_expense_amount = None
    if total_expense > 0:
        idx = monthly_expense.index(max(monthly_expense))
        top_expense_month, top_expense_amount = calendar.month_name[idx + 1], monthly_expense[idx]

    top_income_month = top_income_amount = None
    if total_income > 0:
        idx = monthly_income.index(max(monthly_income))
        top_income_month, top_income_amount = calendar.month_name[idx + 1], monthly_income[idx]

    recent = TransactionLogs.objects.filter(user=request.user).order_by('-date', '-created_at')[:8]

    return render(request, "Dashboard.html", {
        'report_year': report_year, 'years': years,
        'total_income': total_income, 'total_expense': total_expense,
        'balance': balance, 'savings_rate': savings_rate, 'savings_bar': savings_bar,
        'monthly_labels': list(calendar.month_abbr)[1:],
        'monthly_income': monthly_income, 'monthly_expense': monthly_expense,
        'daily_labels': daily_labels, 'daily_dates': daily_dates, 'daily_income': daily_income,
        'daily_expense': daily_expense, 'daily_balance': daily_balance,
        'category_rows': category_rows,
        'category_labels': [r['label'] for r in category_rows],
        'category_values': [r['value'] for r in category_rows],
        'category_colors': [r['color'] for r in category_rows],
        'avg_monthly_expense': avg_monthly_expense,
        'top_category': category_rows[0]['label'] if category_rows else None,
        'top_category_amount': category_rows[0]['value'] if category_rows else None,
        'top_expense_month': top_expense_month, 'top_expense_amount': top_expense_amount,
        'top_income_month': top_income_month, 'top_income_amount': top_income_amount,
        'recent_transactions': recent,
    })


def process_data(user):
    '''
    Prepare transaction logs for export using pandas.
    Returns a DataFrame with columns for date, type, amount, record and description.
    '''
    transactions = TransactionLogs.objects.filter(user=user).order_by('-date')

    records = [
        {
            'date': data.date.isoformat() if data.date else '',
            'type': data.type or '',
            'amount': float(data.amount),
            'record': data.record or '',
            'description': data.description or '',
        }
        for data in transactions
    ]

    return pd.DataFrame(
        records,
        columns=['date', 'type', 'amount', 'record', 'description']
    )


LIVE_LINK_TTLS = {
    '1h': 60 * 60,
    '24h': 24 * 60 * 60,
    '7d': 7 * 24 * 60 * 60,
    '30d': 30 * 24 * 60 * 60,
}
LIVE_LINK_MAX_AGE = LIVE_LINK_TTLS['30d']
LIVE_LINK_SALT = 'Finance.live-transaction-data'


@login_required
def generateLiveLink(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are supported.'}, status=405)

    ttl = request.POST.get('ttl', '').strip().lower()
    ttl_seconds = LIVE_LINK_TTLS.get(ttl)
    if ttl_seconds is None:
        return JsonResponse(
            {'error': 'Unsupported TTL. Choose 1h, 24h, 7d, or 30d.'},
            status=400
        )

    profile, _ = Profile.objects.get_or_create(user=request.user)
    with db_transaction.atomic():
        profile = Profile.objects.select_for_update().get(pk=profile.pk)
        profile.streaming_data = True
        profile.streaming_token_version += 1
        profile.save(update_fields=['streaming_data', 'streaming_token_version'])
        token_version = profile.streaming_token_version

    expires_at = int(time.time()) + ttl_seconds
    token = signing.dumps(
        {
            'user_id': request.user.pk,
            'version': token_version,
            'expires_at': expires_at,
        },
        salt=LIVE_LINK_SALT
    )
    live_url = request.build_absolute_uri(reverse('liveTransactionData'))
    live_url = f'{live_url}?{urlencode({"token": token})}'

    response = JsonResponse({
        'url': live_url,
        'expires_at': expires_at,
        'ttl': ttl,
    })
    response['Cache-Control'] = 'no-store'
    return response


def liveTransactionData(request):
    token = request.GET.get('token', '')
    if not token:
        return HttpResponse(status=404)

    try:
        payload = signing.loads(
            token,
            salt=LIVE_LINK_SALT,
            max_age=LIVE_LINK_MAX_AGE
        )
        user_id = int(payload['user_id'])
        token_version = int(payload['version'])
        expires_at = int(payload['expires_at'])
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        return HttpResponse(status=404)

    if int(time.time()) >= expires_at:
        return HttpResponse(status=404)

    profile = Profile.objects.select_related('user').filter(user_id=user_id).first()
    if (
        profile is None
        or not profile.streaming_data
        or profile.streaming_token_version != token_version
        or not profile.user.is_active
    ):
        return HttpResponse(status=404)

    data = process_data(profile.user)
    records = data.to_dict(orient='records')

    if request.GET.get('format') == 'json':
        response = JsonResponse(records, safe=False)
    else:
        context = {
            'transactions': records,
            'owner': profile.user.username
        }
        response = render(request, "LiveTransactionData.html", context)

    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response['Pragma'] = 'no-cache'
    return response


@login_required
def revokeLiveLink(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are supported.'}, status=405)

    Profile.objects.filter(user=request.user).update(
        streaming_data=False,
        streaming_token_version=F('streaming_token_version') + 1
    )
    return JsonResponse({'revoked': True})


@login_required
def exportData(request):
    '''
    Download the logged-in user's transaction data in the requested format.
    Redirects to reportsHome if no export type is given.
    '''
    if request.method != 'GET':
        return HttpResponse('Only GET requests are supported for download.', status=405)

    export_type = request.GET.get('export_dropdown', '').strip().lower()
    if not export_type:
        # Redirect old export-area/ URL to the new Reports page
        return redirect('reportsHome')

    user_filename = get_valid_filename(
        request.GET.get('filename', 'transactions').strip()
    ) or 'transactions'
    data = process_data(request.user)

    if export_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response.write(data.to_csv(index=False))
        filename = f'{user_filename}.csv'
    elif export_type == 'json':
        response = HttpResponse(data.to_json(orient='records'), content_type='application/json')
        filename = f'{user_filename}.json'
    elif export_type == 'xlsx':
        output = BytesIO()
        data.to_excel(output, index=False)
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f'{user_filename}.xlsx'
    else:
        return HttpResponse(
            'Unsupported export format. Choose csv, xlsx, or json.',
            status=400
        )

    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── Reports views ─────────────────────────────────────────────────────────────

def _get_year_list(user):
    """Return sorted list of years that have income/expense data (always includes current year)."""
    today = date.today()
    incomes = Income.objects.filter(user=user)
    expenses = Expense.objects.filter(user=user)
    years = {d.year for d in incomes.dates('date', 'year')}
    years |= {d.year for d in expenses.dates('date', 'year')}
    years.add(today.year)
    return sorted(years, reverse=True)


def _parse_report_params(request):
    """
    Parse GET params into (start, end) dates.
    Returns (start, end, error_message).
    error_message is None on success.
    """
    today = date.today()
    report_type = request.GET.get('type', '').strip().lower()

    if report_type == 'monthly':
        raw = request.GET.get('month', '').strip()
        if not raw:
            return None, None, 'Please select a month.'
        try:
            dt = datetime.strptime(raw, '%Y-%m')
            start = date(dt.year, dt.month, 1)
            last_day = calendar.monthrange(dt.year, dt.month)[1]
            end = date(dt.year, dt.month, last_day)
        except ValueError:
            return None, None, 'Invalid month format.'

    elif report_type == 'yearly':
        raw = request.GET.get('year', str(today.year)).strip()
        try:
            year = int(raw)
            start = date(year, 1, 1)
            end = date(year, 12, 31)
        except ValueError:
            return None, None, 'Invalid year.'

    elif report_type == 'custom':
        from_raw = request.GET.get('from_date', '').strip()
        to_raw = request.GET.get('to_date', '').strip()
        if not from_raw or not to_raw:
            return None, None, 'Please provide both from and to dates.'
        try:
            start = date.fromisoformat(from_raw)
            end = date.fromisoformat(to_raw)
        except ValueError:
            return None, None, 'Invalid date format.'
        if start > end:
            start, end = end, start  # swap

    else:
        return None, None, 'Invalid report type. Choose monthly, yearly, or custom.'

    return start, end, None


@login_required
def reportsHome(request):
    '''Main Reports page with Generate report and Export data sections.'''
    today = date.today()
    years = _get_year_list(request.user)

    # Handle raw-data downloads (form action points here)
    export_type = request.GET.get('export_dropdown', '').strip().lower()
    if export_type:
        user_filename = get_valid_filename(
            request.GET.get('filename', 'transactions').strip()
        ) or 'transactions'
        data = process_data(request.user)

        if export_type == 'csv':
            response = HttpResponse(content_type='text/csv')
            response.write(data.to_csv(index=False))
            filename = f'{user_filename}.csv'
        elif export_type == 'json':
            response = HttpResponse(
                data.to_json(orient='records'), content_type='application/json'
            )
            filename = f'{user_filename}.json'
        elif export_type == 'xlsx':
            output = BytesIO()
            data.to_excel(output, index=False)
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            filename = f'{user_filename}.xlsx'
        else:
            return HttpResponse(
                'Unsupported export format. Choose csv, xlsx, or json.', status=400
            )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    live_link_active = Profile.objects.filter(
        user=request.user, streaming_data=True
    ).exists()

    return render(request, 'Reports.html', {
        'years': years,
        'current_year': today.year,
        'current_month': today.strftime('%Y-%m'),
        'live_link_active': live_link_active,
    })


@login_required
def reportPreview(request):
    '''Render the report as an HTML page in the browser.'''
    start, end, error = _parse_report_params(request)
    if error:
        return redirect(f"{reverse('reportsHome')}?message={error}")

    data = build_report_data(request.user, start, end)
    insights = generate_insights(data)

    series = data['series']
    bar_svg = bar_chart(series['labels'], series['income'], series['expense'])
    donut_svg = donut_chart(data['by_category'])

    return render(request, 'reports/report.html', {
        'data': data,
        'insights': insights,
        'bar_chart_svg': bar_svg,
        'donut_chart_svg': donut_svg,
        'username': request.user.username,
    })


@login_required
def reportPdf(request):
    '''Render the report to a PDF and return as a download.'''
    start, end, error = _parse_report_params(request)
    if error:
        return redirect(f"{reverse('reportsHome')}?message={error}")

    data = build_report_data(request.user, start, end)
    insights = generate_insights(data)

    series = data['series']
    bar_svg = bar_chart(series['labels'], series['income'], series['expense'])
    donut_svg = donut_chart(data['by_category'])

    html_string = render(request, 'reports/report.html', {
        'data': data,
        'insights': insights,
        'bar_chart_svg': bar_svg,
        'donut_chart_svg': donut_svg,
        'username': request.user.username,
    }).content.decode('utf-8')

    try:
        pdf_bytes = render_pdf(html_string, request.build_absolute_uri('/'))
    except ImportError:
        fallback_html = """
        <html><head><title>PDF unavailable</title></head><body style='font-family:sans-serif;padding:40px;max-width:600px;margin:auto'>
        <h2>PDF generation unavailable</h2>
        <p>WeasyPrint is not installed on this server.</p>
        <p><strong>Alternative:</strong> Use the <a href="javascript:history.back()">Preview</a> option and then
        print the page with <kbd>Ctrl+P</kbd> / <kbd>Cmd+P</kbd> → Save as PDF.</p>
        </body></html>
        """
        return HttpResponse(fallback_html, status=200)

    period_slug = data['period']['label'].replace(' ', '-').replace('\u2013', '-')
    filename = f'finance-report-{period_slug}.pdf'

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response