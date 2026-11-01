"""Goal money rules. 
Balance = income - expenses. 
Funds in active goals are locked."""
from decimal import Decimal, InvalidOperation
from datetime import date
from django.db import transaction as db_transaction
from django.db.models import Sum
from Finance.models import Income, Expense, FinanceGoal
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from Finance.services.transaction_sync import create_or_update_transaction_log
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from Finance.services import goals as goal_service

LOW_BALANCE = 'Low on balance. Cannot allocate funds.'
ZERO = Decimal('0')

def balance(user):
    income = Income.objects.filter(user=user).aggregate(s=Sum('amount'))['s'] or ZERO
    spent = Expense.objects.filter(user=user).aggregate(s=Sum('amount'))['s'] or ZERO
    return income - spent


def locked(user):
    active = FinanceGoal.objects.filter(user=user, status='active')
    return active.aggregate(s=Sum('allocated'))['s'] or ZERO

def available(user):
    return balance(user) - locked(user)

@login_required
@require_POST
def allocateGoal(request, pk):
    goal = get_object_or_404(FinanceGoal, pk=pk, user=request.user, mode='manual', status='active')
    try:
        amount = Decimal(request.POST.get('amount', ''))
    except InvalidOperation:
        amount = Decimal('0')
    error = goal_service.allocate_amount(goal, amount)
    if error:
        messages.error(request, error)
    else:
        messages.success(request, 'Funds allocated.')
    return redirect('goalsHome')

def allocate_amount(goal, amount):
    """Lock `amount` from available balance into the goal. Returns an error text or None."""
    if not amount.is_finite() or amount <= 0:
        return 'Enter an amount greater than 0.'
    if amount > goal.remaining:
        return 'Amount is more than the remaining target.'
    # shortcut: no row lock, two simultaneous requests could overspend; upgrade to select_for_update for multi-user traffic
    with db_transaction.atomic():
        if amount > available(goal.user):
            return LOW_BALANCE
        goal.allocated += amount
        goal.save(update_fields=['allocated'])
    return None


def run_auto_allocation(user):
    """First come first serve. Each Auto goal gets its full remaining target, or waits."""
    waiting = FinanceGoal.objects.filter(user=user, mode='auto', status='active')
    for goal in waiting:
        if allocate_amount(goal, goal.remaining):
            break


def buy_goal(goal):
    """Turn a funded goal into one Expense. Returns an error text or None."""
    if goal.allocated < goal.target_amount:
        return 'Goal is not fully funded yet.'
    with db_transaction.atomic():
        expense = Expense.objects.create(
            user=goal.user,
            date=date.today(),
            category='Other',
            item_name=goal.title,
            amount=goal.target_amount,
        )
        create_or_update_transaction_log(goal.user, expense, 'expense')
        goal.status = 'completed'
        goal.save(update_fields=['status'])
    return None