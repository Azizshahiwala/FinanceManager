from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404

from Finance.models import Expense, Income, TransactionLogs


def get_owned_transaction_or_404(request_user, transaction_type, transaction_id):
    if transaction_type not in {"income", "expense"}:
        raise Http404("Invalid transaction type.")

    model = Income if transaction_type == "income" else Expense
    return get_object_or_404(model, pk=transaction_id, user=request_user)


def _build_log_values(transaction_row):
    item_name = getattr(transaction_row, "item_name", None) or "N/A"
    description = getattr(transaction_row, "description", "") or ""
    record = item_name if item_name != "N/A" else "N/A"

    if description:
        log_description = f"{item_name} - {description}" if item_name != "N/A" else description
    else:
        log_description = record

    return record, log_description


def create_or_update_transaction_log(request_user, transaction_row, transaction_type):
    if transaction_type not in {"income", "expense"}:
        raise Http404("Invalid transaction type.")

    record, description = _build_log_values(transaction_row)
    defaults = {
        "user": request_user,
        "type": transaction_type,
        "date": transaction_row.date,
        "amount": transaction_row.amount,
        "record": record,
        "description": description,
    }

    log, created = TransactionLogs.objects.get_or_create(
        user=request_user,
        type=transaction_type,
        source_id=transaction_row.pk,
        defaults=defaults,
    )

    if not created:
        log.date = transaction_row.date
        log.amount = transaction_row.amount
        log.record = record
        log.description = description
        log.save(update_fields=["date", "amount", "record", "description"])

    return log


def delete_transaction_log(request_user, transaction_type, transaction_id):
    if transaction_type not in {"income", "expense"}:
        raise Http404("Invalid transaction type.")

    return TransactionLogs.objects.filter(
        user=request_user,
        type=transaction_type,
        source_id=transaction_id,
    ).delete()


def save_transaction_with_log(request_user, form, transaction_type):
    with transaction.atomic():
        transaction_row = form.save(commit=False)
        transaction_row.user = request_user
        transaction_row.type = transaction_type
        transaction_row.save()
        create_or_update_transaction_log(request_user, transaction_row, transaction_type)
        return transaction_row


def remove_transaction_with_log(request_user, transaction_row, transaction_type):
    with transaction.atomic():
        delete_transaction_log(request_user, transaction_type, transaction_row.pk)
        transaction_row.delete()
        return None
