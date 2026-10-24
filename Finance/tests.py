from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Profile, TransactionLogs


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

        response = self.client.get(f'{link.path}?{link.query}')

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

    def test_export_page_renders_controls(self):
        response = self.client.get(reverse('exportArea'))

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

        response = self.client.get(reverse('exportArea'))

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode(),
            r'<button[^>]*class="btn-danger"[^>]*>Revoke live link</button>'
        )

    def test_export_form_downloads_csv_with_safe_filename(self):
        response = self.client.get(
            reverse('exportArea'),
            {'export_dropdown': 'csv', 'filename': 'My transactions'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('filename="My_transactions.csv"', response['Content-Disposition'])
        self.assertIn('Salary', response.content.decode())
