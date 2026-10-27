import calendar
from datetime import date

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
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required 
from django.contrib.auth.forms import AuthenticationForm
from django.core import signing
from django.urls import reverse
from django.utils.text import get_valid_filename
from .forms import *
from .models import Profile, TransactionLogs

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
            user = authenticate(username=username, password=password)
            if user is not None:
                auth_login(request, user)
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
        
    return render(request, "LoginPage.html", {"form": form})

def logout(request):
    auth_logout(request)
    return render(request,"Logout.html")

@login_required
def transaction(request):
    transactions = TransactionLogs.objects.filter(user=request.user).order_by('-date')
    
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    
    if from_date:
        transactions = transactions.filter(date__gte=from_date) 
        
    if to_date:
        transactions = transactions.filter(date__lte=to_date)
        
    return render(request, "Transaction.html", {
        'transactions': transactions,
    })

def addTransaction(request, type):
    log = None
    date = None
    record = None
    if type == 'expense':
        log = Expense.objects.filter(user=request.user).order_by('-created_at').first()
        item_name = log.item_name or 'N/A'
        unit      = log.unit or 'unit'
        amount    = log.amount or 0
        description = f"{log.user}, created expense of {item_name}, amounted: {amount}, in {unit}(s)"

    else:
        log = Income.objects.filter(user=request.user).order_by('-created_at').first()
        item_name = log.item_name or 'N/A'
        amount    = log.amount or 0
        description = f"{log.user}, created income of {item_name}, amounted: {amount}"

    date = log.date
    user_note = log.description or ''
    item_name = log.item_name or 'N/A'

    if user_note:
        record = f"{item_name} - {user_note}"
    else:
        record = item_name

    transactionlog = TransactionLogs(
        user=request.user,
        type=type,
        date=date,
        amount=log.amount,
        record=record,
        description=description
    )
    transactionlog.save()
    return

@login_required
def expenseAdd(request):
    if request.method == 'POST':
        form = ExpenseDataForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.user = request.user
            txn.type = 'expense'            
            txn.save()
            addTransaction(request, 'expense')
            
            return redirect('expenseAdd')
    else:
        form = ExpenseDataForm()

    today = date.today()
    recent_expense = Expense.objects.filter(user=request.user).order_by('-date')[:3]
    monthly_total_data = Expense.objects.filter(
            user=request.user,
            date__year=today.year,
            date__month=today.month
        ).aggregate(Sum('amount')) 
    
    current_month_total = monthly_total_data['amount__sum'] or 0
        
    history = {
            'recent_expense':recent_expense,
            'current_month_total':current_month_total
        }
    
    return render(request, "./ExpenseCategory/ExpenseAdd.html", {'form': form,'history':history})

@login_required
def incomeAdd(request):
    if request.method == 'POST':
        form = IncomeDataForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.user = request.user
            txn.type = 'income'
            txn.save()
            addTransaction(request, 'income')
            return redirect('incomeAdd')
    else:
        form = IncomeDataForm()

    today = date.today()
    recent_income = Income.objects.filter(user=request.user).order_by('-date')[:3]
    monthly_total_data = Income.objects.filter(
        user=request.user,
        date__year=today.year,
        date__month=today.month
    ).aggregate(Sum('amount')) 

    current_month_total = monthly_total_data['amount__sum'] or 0
    
    history = {
        'recent_income':recent_income,
        'current_month_total':current_month_total
    }

    return render(request, "./IncomeCategory/IncomeAdd.html", {'form': form,'history':history})

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
    except ValueError:
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
    monthly_balance = [round(i - e, 2) for i, e in zip(monthly_income, monthly_expense)]

    total_income = sum(monthly_income)
    total_expense = sum(monthly_expense)
    balance = total_income - total_expense
    savings_rate = round(balance / total_income * 100, 1) if total_income > 0 else None
    savings_bar = max(0, min(100, savings_rate)) if savings_rate is not None else 0

    # Category breakdown (top 6 + Others) with shared colours for chart and legend
    palette = ['#E85D91', '#17161A', '#2E9E6E', '#E2645B', '#F3AFC9', '#837C70', '#D9CFB8']
    cats = list(
        expenses.filter(date__year=report_year)
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    rows = [(c['category'], float(c['total'])) for c in cats[:6]]
    if len(cats) > 6:
        rows.append(('Others', float(sum(c['total'] for c in cats[6:]))))
    category_rows = [
        {
            'label': label,
            'value': value,
            'pct': round(value / total_expense * 100, 1) if total_expense else 0,
            'color': palette[i],
        }
        for i, (label, value) in enumerate(rows)
    ]

    # Highlights
    active_months = [i for i in range(12) if monthly_income[i] or monthly_expense[i]]
    avg_monthly_expense = round(total_expense / len(active_months), 2) if active_months else 0

    top_expense_month = top_expense_amount = None
    if total_expense > 0:
        idx = monthly_expense.index(max(monthly_expense))
        top_expense_month = calendar.month_name[idx + 1]
        top_expense_amount = monthly_expense[idx]

    top_income_month = top_income_amount = None
    if total_income > 0:
        idx = monthly_income.index(max(monthly_income))
        top_income_month = calendar.month_name[idx + 1]
        top_income_amount = monthly_income[idx]

    recent = TransactionLogs.objects.filter(user=request.user).order_by('-date', '-created_at')[:8]

    return render(request, "Dashboard.html", {
        'report_year': report_year,
        'years': years,
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
        'savings_rate': savings_rate,
        'savings_bar': savings_bar,
        'monthly_labels': list(calendar.month_abbr)[1:],
        'monthly_income': monthly_income,
        'monthly_expense': monthly_expense,
        'monthly_balance': monthly_balance,
        'category_rows': category_rows,
        'category_labels': [r['label'] for r in category_rows],
        'category_values': [r['value'] for r in category_rows],
        'category_colors': [r['color'] for r in category_rows],
        'avg_monthly_expense': avg_monthly_expense,
        'top_category': category_rows[0]['label'] if category_rows else None,
        'top_category_amount': category_rows[0]['value'] if category_rows else None,
        'top_expense_month': top_expense_month,
        'top_expense_amount': top_expense_amount,
        'top_income_month': top_income_month,
        'top_income_amount': top_income_amount,
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
    '''
    if request.method != 'GET':
        return HttpResponse('Only GET requests are supported for download.', status=405)

    export_type = request.GET.get('export_dropdown', '').strip().lower()
    if not export_type:
        live_link_active = Profile.objects.filter(
            user=request.user,
            streaming_data=True
        ).exists()
        return render(
            request,
            "ExportArea.html",
            {'live_link_active': live_link_active}
        )

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