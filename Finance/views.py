from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.db.models import Sum
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required 
from django.contrib.auth.forms import AuthenticationForm
from .forms import *
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
