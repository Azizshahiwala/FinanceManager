from django.core.management.base import BaseCommand

from Finance.models import Expense, Income, TransactionLogs


class Command(BaseCommand):
    help = 'Backfill source_id values for legacy transaction logs.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show candidate matches without saving them.',
        )

    def _matching_transactions(self, log):
        record = (log.record or '').strip()
        if log.type == 'income':
            model = Income
        elif log.type == 'expense':
            model = Expense
        else:
            return []

        queryset = model.objects.filter(user=log.user, date=log.date, amount=log.amount)
        names = set()
        if record and record != 'N/A':
            names.add(record)
            if ' - ' in record:
                names.add(record.split(' - ', 1)[0].strip())

        matches = queryset.none()
        for name in names:
            matches = matches | queryset.filter(item_name__iexact=name)
        return matches.distinct()

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        unmatched = 0
        logs = TransactionLogs.objects.filter(source_id__isnull=True).order_by('user_id', 'date', 'amount')

        for log in logs:
            matches = self._matching_transactions(log)
            if len(matches) == 1:
                match = matches[0]
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Would link log {log.pk} ({log.type}) to {match.__class__.__name__} {match.pk}"
                        )
                    )
                else:
                    log.source_id = match.pk
                    log.save(update_fields=['source_id'])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Linked log {log.pk} ({log.type}) to {match.__class__.__name__} {match.pk}"
                        )
                    )
            else:
                unmatched += 1

        self.stdout.write(self.style.NOTICE(f'Unmatched logs: {unmatched}'))
