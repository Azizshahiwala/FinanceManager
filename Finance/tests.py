from datetime import date
from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Budget, Expense, Income, Profile, TransactionLogs
from .reports.services import build_report_data
from .reports.insights import generate_insights


# ══════════════════════════════════════════════════════════════════════════════
# Existing live-link tests — behaviour unchanged; only page URL/heading updated
# ══════════════════════════════════════════════════════════════════════════════

class LiveTransactionLinkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='live-link-user', password='test-password')
        self.client.force_login(self.user)
        TransactionLogs.objects.create(
            user=self.user,
            type='income',
            date='2026-10-24',
            amount='125.50',
            record='Salary',
            description='Monthly salary'
        )

    def generate_link(self):
        response = self.client.post(
            reverse('generateLiveLink'),
            {'ttl': '1h'}
        )
        self.assertEqual(response.status_code, 200)
        return urlparse(response.json()['url'])

    def test_generated_link_returns_current_transaction_data(self):
        link = self.generate_link()

        response = self.client.get(f'{link.path}?{link.query}&format=json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['record'], 'Salary')
        self.assertTrue(Profile.objects.get(user=self.user).streaming_data)
        self.assertIn('no-store', response['Cache-Control'])

    def test_revoke_invalidates_generated_link(self):
        link = self.generate_link()

        response = self.client.post(reverse('revokeLiveLink'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Profile.objects.get(user=self.user).streaming_data)
        self.assertEqual(self.client.get(f'{link.path}?{link.query}').status_code, 404)

    def test_invalid_ttl_is_rejected(self):
        response = self.client.post(reverse('generateLiveLink'), {'ttl': '90d'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Profile.objects.filter(user=self.user).exists())

    def test_reports_page_renders_controls(self):
        """exportArea now redirects to reportsHome which has the same controls."""
        response = self.client.get(reverse('reportsHome'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Download transactions')
        self.assertContains(response, 'Generate live link')
        self.assertContains(response, 'name="export_dropdown"')
        self.assertContains(response, 'name="ttl"')
        self.assertContains(response, 'Revoke live link')
        self.assertRegex(
            response.content.decode(),
            r'<button[^>]*class="btn-danger"[^>]*disabled'
        )

    def test_revoke_button_is_enabled_after_reloading_with_active_link(self):
        self.generate_link()

        response = self.client.get(reverse('reportsHome'))

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode(),
            r'<button[^>]*class="btn-danger"[^>]*>Revoke live link</button>'
        )

    def test_export_form_downloads_csv_with_safe_filename(self):
        response = self.client.get(
            reverse('reportsHome'),
            {'export_dropdown': 'csv', 'filename': 'My transactions'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('filename="My_transactions.csv"', response['Content-Disposition'])
        self.assertIn('Salary', response.content.decode())

    def test_old_export_area_url_still_works(self):
        """export-area/ must still work (redirects to reportsHome when no export type)."""
        response = self.client.get(reverse('exportArea'))
        # Redirect to reports/
        self.assertIn(response.status_code, [301, 302, 200])


# ══════════════════════════════════════════════════════════════════════════════
# Report data tests
# ══════════════════════════════════════════════════════════════════════════════

class BuildReportDataTests(TestCase):
    """Unit tests for build_report_data()."""

    def setUp(self):
        self.user = User.objects.create_user(username='report-user', password='pw')
        self.start = date(2026, 10, 1)
        self.end = date(2026, 10, 31)

        Income.objects.create(
            user=self.user, type='income', category='Salary',
            date=date(2026, 10, 5), amount='5000.00'
        )
        Expense.objects.create(
            user=self.user, type='expense', category='Food',
            item_name='Groceries', date=date(2026, 10, 10), amount='800.00'
        )
        Expense.objects.create(
            user=self.user, type='expense', category='Transport',
            item_name='Bus pass', date=date(2026, 10, 15), amount='200.00'
        )

    def test_totals_are_correct(self):
        data = build_report_data(self.user, self.start, self.end)
        self.assertAlmostEqual(data['total_income'], 5000.0)
        self.assertAlmostEqual(data['total_expense'], 1000.0)
        self.assertAlmostEqual(data['balance'], 4000.0)

    def test_savings_rate(self):
        data = build_report_data(self.user, self.start, self.end)
        self.assertIsNotNone(data['savings_rate'])
        self.assertAlmostEqual(data['savings_rate'], 80.0)

    def test_by_category_sorted_desc(self):
        data = build_report_data(self.user, self.start, self.end)
        cats = [c['category'] for c in data['by_category']]
        self.assertEqual(cats[0], 'Food')

    def test_previous_period_populated(self):
        data = build_report_data(self.user, self.start, self.end)
        self.assertIn('total_income', data['previous'])
        self.assertIn('total_expense', data['previous'])

    def test_no_data_period_still_returns_dict(self):
        data = build_report_data(self.user, date(2025, 1, 1), date(2025, 1, 31))
        self.assertEqual(data['total_income'], 0.0)
        self.assertEqual(data['total_expense'], 0.0)

    def test_data_isolation(self):
        """Another user's transactions must not appear in this user's report."""
        other = User.objects.create_user(username='other-user', password='pw2')
        Expense.objects.create(
            user=other, type='expense', category='Other',
            item_name='Secret', date=date(2026, 10, 20), amount='99999.00'
        )
        data = build_report_data(self.user, self.start, self.end)
        self.assertAlmostEqual(data['total_expense'], 1000.0)


# ══════════════════════════════════════════════════════════════════════════════
# Insight tests
# ══════════════════════════════════════════════════════════════════════════════

class InsightTests(TestCase):
    """At least 3 rules produce the expected text."""

    def _base_data(self):
        return {
            'period': {'label': 'October 2026'},
            'total_income': 5000.0,
            'total_expense': 3000.0,
            'savings_rate': 40.0,  # above 30% → good
            'by_category': [{'category': 'Food', 'total': 3000, 'pct': 100.0, 'color': '#E85D91'}],
            'budget_status': [],
            'top_expenses': [{'item_name': 'Groceries', 'category': 'Food', 'amount': 3000, 'date': date(2026, 10, 10)}],
            'previous': {
                'label': 'September 2026',
                'total_income': 5000.0,
                'total_expense': 2000.0,  # expense went up → warn
                'savings_rate': 60.0,
                'by_category': [],
                'balance': 3000.0,
            },
            'projected_month_end': None,
        }

    def test_spending_up_insight(self):
        data = self._base_data()
        insights = generate_insights(data)
        texts = [i['text'] for i in insights]
        self.assertTrue(any('up' in t and '%' in t for t in texts))

    def test_good_savings_insight(self):
        data = self._base_data()
        insights = generate_insights(data)
        good = [i for i in insights if i['level'] == 'good']
        self.assertTrue(len(good) >= 1)

    def test_budget_exceeded_insight(self):
        data = self._base_data()
        data['budget_status'] = [{
            'category': 'Food',
            'month': date(2026, 10, 1),
            'limit': 1000.0,
            'spent': 1500.0,
            'pct': 150.0,
        }]
        insights = generate_insights(data)
        warn_texts = [i['text'] for i in insights if i['level'] == 'warn']
        self.assertTrue(any('exceeded' in t for t in warn_texts))

    def test_low_savings_warn(self):
        data = self._base_data()
        data['savings_rate'] = 5.0
        data['total_income'] = 5000.0
        insights = generate_insights(data)
        warn_texts = [i['text'] for i in insights if i['level'] == 'warn']
        self.assertTrue(any('savings rate' in t.lower() for t in warn_texts))

    def test_no_income_warn(self):
        data = self._base_data()
        data['total_income'] = 0.0
        data['savings_rate'] = None
        data['previous']['total_income'] = 0.0
        data['previous']['total_expense'] = 0.0
        insights = generate_insights(data)
        warn_texts = [i['text'] for i in insights if i['level'] == 'warn']
        self.assertTrue(any('No income' in t for t in warn_texts))

    def test_max_6_insights(self):
        data = self._base_data()
        # Add many budget alerts
        data['budget_status'] = [
            {'category': f'Cat{i}', 'month': date(2026, 10, 1),
             'limit': 100.0, 'spent': 200.0, 'pct': 200.0}
            for i in range(10)
        ]
        insights = generate_insights(data)
        self.assertLessEqual(len(insights), 6)


# ══════════════════════════════════════════════════════════════════════════════
# View integration tests
# ══════════════════════════════════════════════════════════════════════════════

class ReportViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='view-user', password='pw')
        self.client.force_login(self.user)
        Income.objects.create(
            user=self.user, type='income', category='Salary',
            date=date(2026, 10, 5), amount='5000.00'
        )

    def test_reports_home_returns_200(self):
        response = self.client.get(reverse('reportsHome'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Generate report')
        self.assertContains(response, 'Export data')

    def test_preview_monthly_returns_200_with_period_label(self):
        response = self.client.get(
            reverse('reportPreview'),
            {'type': 'monthly', 'month': '2026-10'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'October 2026')

    def test_preview_yearly_returns_200(self):
        response = self.client.get(
            reverse('reportPreview'),
            {'type': 'yearly', 'year': '2026'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2026')

    def test_preview_custom_range_returns_200(self):
        response = self.client.get(
            reverse('reportPreview'),
            {'type': 'custom', 'from_date': '2026-10-01', 'to_date': '2026-10-31'}
        )
        self.assertEqual(response.status_code, 200)

    def test_preview_custom_range_swaps_dates_when_reversed(self):
        """If from > to, they should be swapped rather than erroring."""
        response = self.client.get(
            reverse('reportPreview'),
            {'type': 'custom', 'from_date': '2026-10-31', 'to_date': '2026-10-01'}
        )
        self.assertEqual(response.status_code, 200)

    def test_preview_invalid_type_redirects(self):
        response = self.client.get(
            reverse('reportPreview'),
            {'type': 'invalid'}
        )
        self.assertIn(response.status_code, [301, 302])

    def test_pdf_returns_application_pdf(self):
        try:
            import weasyprint  # noqa: F401
        except ImportError:
            self.skipTest('WeasyPrint not installed')
        response = self.client.get(
            reverse('reportPdf'),
            {'type': 'monthly', 'month': '2026-10'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_report_data_isolation(self):
        """User A's report must not include user B's transactions."""
        user_b = User.objects.create_user(username='user-b', password='pw')
        Expense.objects.create(
            user=user_b, type='expense', category='Other',
            item_name='Secret', date=date(2026, 10, 20), amount='99999.00'
        )
        response = self.client.get(
            reverse('reportPreview'),
            {'type': 'monthly', 'month': '2026-10'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '99999')

    def test_empty_period_renders_with_notice(self):
        """A period with no data should still render, not 500."""
        response = self.client.get(
            reverse('reportPreview'),
            {'type': 'monthly', 'month': '2020-01'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No transactions in this period')


class TransactionEditDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='txn-user', password='pw')
        self.other_user = User.objects.create_user(username='txn-other', password='pw')
        self.client.force_login(self.user)

    def _create_income(self):
        income = Income.objects.create(
            user=self.user,
            type='income',
            category='Salary',
            date=date(2026, 10, 5),
            item_name='Salary',
            amount='5000.00',
            description='Monthly pay',
        )
        TransactionLogs.objects.create(
            user=self.user,
            type='income',
            source_id=income.pk,
            date=income.date,
            amount=income.amount,
            record='Salary',
            description='Salary - Monthly pay',
        )
        return income

    def _create_expense(self):
        expense = Expense.objects.create(
            user=self.user,
            type='expense',
            category='Food',
            item_name='Groceries',
            date=date(2026, 10, 10),
            amount='150.00',
            description='Weekly shop',
        )
        TransactionLogs.objects.create(
            user=self.user,
            type='expense',
            source_id=expense.pk,
            date=expense.date,
            amount=expense.amount,
            record='Groceries',
            description='Groceries - Weekly shop',
        )
        return expense

    def test_edit_income_updates_source_row_and_log(self):
        income = self._create_income()

        response = self.client.post(
            reverse('editTransaction', args=['income', income.pk]),
            {
                'date': '2026-10-06',
                'category': 'Salary',
                'item_name': 'Bonus salary',
                'amount': '5500.00',
                'description': 'Monthly pay',
            },
        )

        self.assertEqual(response.status_code, 302)
        income.refresh_from_db()
        self.assertEqual(income.item_name, 'Bonus salary')
        log = TransactionLogs.objects.get(user=self.user, type='income', source_id=income.pk)
        self.assertEqual(log.record, 'Bonus salary')
        self.assertEqual(str(log.amount), '5500.00')

    def test_edit_expense_updates_source_row_and_log(self):
        expense = self._create_expense()

        response = self.client.post(
            reverse('editTransaction', args=['expense', expense.pk]),
            {
                'date': '2026-10-11',
                'category': 'Food',
                'item_name': 'Fresh groceries',
                'quantity': '2',
                'unit': 'bags',
                'amount': '180.00',
                'description': 'Weekly shopping',
            },
        )

        self.assertEqual(response.status_code, 302)
        expense.refresh_from_db()
        self.assertEqual(expense.item_name, 'Fresh groceries')
        log = TransactionLogs.objects.get(user=self.user, type='expense', source_id=expense.pk)
        self.assertEqual(log.record, 'Fresh groceries')
        self.assertEqual(str(log.amount), '180.00')

    def test_delete_expense_removes_source_row_and_log(self):
        expense = self._create_expense()
        response = self.client.post(reverse('deleteTransaction', args=['expense', expense.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Expense.objects.filter(pk=expense.pk, user=self.user).exists())
        self.assertFalse(TransactionLogs.objects.filter(user=self.user, type='expense', source_id=expense.pk).exists())

    def test_other_user_transaction_returns_404(self):
        other_expense = Expense.objects.create(
            user=self.other_user,
            type='expense',
            category='Travel',
            item_name='Ticket',
            date=date(2026, 10, 12),
            amount='90.00',
            description='Flight',
        )

        edit_response = self.client.get(reverse('editTransaction', args=['expense', other_expense.pk]))
        delete_response = self.client.get(reverse('deleteTransaction', args=['expense', other_expense.pk]))

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)

    def test_get_delete_does_not_delete_row(self):
        expense = self._create_expense()
        response = self.client.get(reverse('deleteTransaction', args=['expense', expense.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Expense.objects.filter(pk=expense.pk, user=self.user).exists())

    def test_invalid_transaction_type_returns_404(self):
        response = self.client.get(reverse('editTransaction', args=['transfer', 1]))
        self.assertEqual(response.status_code, 404)

    def test_invalid_amount_shows_form_errors_and_keeps_values(self):
        income = self._create_income()

        response = self.client.post(
            reverse('editTransaction', args=['income', income.pk]),
            {
                'date': '2026-10-06',
                'category': 'Salary',
                'item_name': 'Bonus salary',
                'amount': '0',
                'description': 'Monthly pay',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Amount must be greater than zero.')
        income.refresh_from_db()
        self.assertEqual(income.item_name, 'Salary')
