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

# def register(request):
#     return render(request,"RegisterPage.html")

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

# def updateBudget(request):
#     return render(request,"UpdateBudget.html")

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
    return render(request, "./ExpenseCategory/ExpenseAdd.html", {'form': form})

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
            return redirect('dashboard')
    else:
        form = IncomeDataForm()
    return render(request, "./IncomeCategory/IncomeAdd.html", {'form': form})

@login_required
def dashboard(request):
    income_logs= Income.objects.filter(user=request.user)
    expense_logs= Expense.objects.filter(user=request.user)

    total_income = income_logs.filter(type='income').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = expense_logs.filter(type='expense').aggregate(Sum('amount'))['amount__sum'] or 0

    balance = total_income - total_expense

    return render(request, "Dashboard.html", {
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance
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
    response = JsonResponse(data.to_dict(orient='records'), safe=False)
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

    export_type = request.GET.get('export_dropdown', 'csv').strip().lower()
    user_filename = request.GET.get('filename').strip().lower()
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