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
    transactions = Transaction.objects.filter(user=request.user).order_by('-date')
    
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

@login_required
def expenseAdd(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.user = request.user
            txn.type = 'expense'
            txn.save()
            
            return redirect('expenseAdd')
    else:
        form = TransactionForm()
    return render(request, "./ExpenseCategory/ExpenseAdd.html", {'form': form})

@login_required
def incomeAdd(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.user = request.user
            txn.type = 'income'
            txn.save()
            return redirect('dashboard')
    else:
        form = TransactionForm()
    return render(request, "./IncomeCategory/IncomeAdd.html", {'form': form})

@login_required
def dashboard(request):
    data = Transaction.objects.filter(user=request.user)
    total_income = data.filter(type='income').aggregate(Sum('amount'))['amount__sum'] or 0
    total_expense = data.filter(type='expense').aggregate(Sum('amount'))['amount__sum'] or 0
    balance = total_income - total_expense

    return render(request, "Dashboard.html", {
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance
    })
@login_required
def exportArea(request):
    data = Transaction.objects.filter(user=request.user)
    print(data)
    return render(request, "ExportArea.html")