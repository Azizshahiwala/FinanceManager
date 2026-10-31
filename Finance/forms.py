from django import forms
from .models import *
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

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

class RegistrationForm(UserCreationForm):

    full_name = forms.CharField(max_length=150, label="Full Name")
    email = forms.EmailField()
    phone = forms.CharField(max_length=15, required=True)

    currency = forms.ChoiceField(
        choices=[
            ('INR', 'INR (₹)'),
            ('USD', 'USD ($)'),
            ('EUR', 'EUR (€)'),
            ('GBP', 'GBP (£)'),
        ],
        initial='INR'
    )

    class Meta:
        model = User
        fields = [
            'full_name',
            'username',
            'email',
            'phone',
            'currency',
            'password1',
            'password2'
        ]

    def clean_email(self):
        email = self.cleaned_data['email']

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "This email is already registered."
            )

        return email

    def save(self, commit=True):
        user = super().save(commit=False)

        full_name = self.cleaned_data['full_name'].strip().split()

        user.first_name = full_name[0]
        user.last_name = ' '.join(full_name[1:])
        user.email = self.cleaned_data['email']

        if commit:
            user.save()

        return user        