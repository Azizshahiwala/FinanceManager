from django import forms
from .models import *
from django.contrib.auth.models import User

class TransactionForm(forms.ModelForm):
    class Meta:
        model = TransactionLogs
        fields = ['date', 'record', 'description']
        # 'type' and 'user' set in the view, not the form —
        # incomeAdd/expenseAdd views set type='income'/'expense', user=request.user

class IncomeDataForm(forms.ModelForm):
    class Meta: 
        model = Income
        fields = ['date','category','item_name','amount','description']

class ExpenseDataForm(forms.ModelForm):
    class Meta: 
        model = Expense
        fields = ['date','category','item_name','quantity','unit','amount','description']
class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['category', 'limit_amount', 'month']