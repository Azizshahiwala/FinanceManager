from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Budget, Expense, Income, TransactionLogs


class TransactionForm(forms.ModelForm):
    class Meta:
        model = TransactionLogs
        fields = ['date', 'record', 'description']
        # 'type' and 'user' are set in the view.


class PositiveAmountMixin:
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        return amount


class IncomeDataForm(PositiveAmountMixin, forms.ModelForm):
    class Meta:
        model = Income
        fields = ['date', 'category', 'item_name', 'amount', 'description']


class ExpenseDataForm(PositiveAmountMixin, forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['date', 'category', 'item_name', 'quantity', 'unit', 'amount', 'description']


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['category', 'limit_amount', 'month']


class RegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=150, label='Full Name')
    email = forms.EmailField()
    phone = forms.CharField(max_length=15, required=True)

    currency = forms.ChoiceField(
        choices=[
            ('INR', 'INR (₹)'),
            ('USD', 'USD ($)'),
            ('EUR', 'EUR (€)'),
            ('GBP', 'GBP (£)'),
        ],
        initial='INR',
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
            'password2',
        ]

    def clean_email(self):
        email = self.cleaned_data['email']

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already registered.')

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