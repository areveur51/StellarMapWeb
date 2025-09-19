# webApp/tests.py
from unittest.mock import patch  # For efficient mocking
from django.test import TestCase
from django.urls import reverse


class SearchViewTestCase(TestCase):

    def test_search_view_valid(self):
        """Test search view with valid params returns 200."""
        response = self.client.get(
            reverse('webApp:search_view'), {
                'account':
                'GD6WU64OEP5C4LRBH6NK3MHYIA2ADN6K6II6EXPNVUR3ERBXT4AN4ACD',
                'network': 'public'
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn('account_genealogy_items', response.context)
        self.assertIn('tree_data', response.context)

    @patch('webApp.views.StellarMapCreatorAccountLineageHelpers'
           )  # Mock heavy helper
    def test_search_view_fallback(self, mock_helpers):
        """Test fallback on exception."""
        mock_instance = mock_helpers.return_value
        mock_instance.get_account_genealogy.side_effect = Exception(
            "Test error")
        response = self.client.get(reverse('webApp:search_view'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['account_genealogy_items'], [])

    def test_search_view_invalid_account(self):
        """Test invalid account raises 404."""
        response = self.client.get(reverse('webApp:search_view'),
                                   {'account': 'invalid'})
        self.assertEqual(response.status_code, 404)

    def test_search_view_invalid_network(self):
        """Test invalid network raises 404."""
        response = self.client.get(reverse('webApp:search_view'),
                                   {'network': 'invalid'})
        self.assertEqual(response.status_code, 404)

    def test_redirect_to_search_view(self):
        """Test root redirects to search."""
        response = self.client.get(reverse('webApp:redirect_to_search_view'))
        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertTrue(response.url.endswith('/search/'))
