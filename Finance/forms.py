from django import forms
from .models import *
from django.contrib.auth.models import User

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['amount', 'category', 'date', 'description', 'item_name', 'quantity', 'unit']
        # 'type' and 'user' set in the view, not the form —
        # incomeAdd/expenseAdd views set type='income'/'expense', user=request.user


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['category', 'limit_amount', 'month']