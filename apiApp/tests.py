# apiApp/tests.py
import unittest
from unittest.mock import patch  # For efficient mocking of externals
from django.test import TestCase
from django.urls import reverse
from apiApp.helpers.env import EnvHelpers, StellarNetwork
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers


class SwaggerUIViewTestCase(TestCase):

    def test_swagger_ui(self):
        """Test Swagger UI renders OK."""
        response = self.client.get(reverse('apiApp:swagger-ui'))
        self.assertEqual(response.status_code, 200)


class CheckAllUrlsViewTestCase(TestCase):

    def test_check_all_urls(self):
        """Test URL checker returns 200."""
        response = self.client.get(reverse('apiApp:check_all_urls'))
        self.assertEqual(response.status_code, 200)


class SetNetworkViewTestCase(TestCase):

    def test_set_network_valid(self):
        """Test valid network set returns success."""
        response = self.client.get(
            reverse('apiApp:set_network', kwargs={'network': 'testnet'}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('success', response.json())

    def test_set_network_invalid(self):
        """Test invalid network returns error."""
        response = self.client.get(
            reverse('apiApp:set_network', kwargs={'network': 'invalid'}))
        self.assertEqual(response.status_code, 400)


class LineageStellarAccountViewTestCase(TestCase):

    @patch('apiApp.views.LineageHelpers'
           )  # Mock external helper for isolation/efficiency
    def test_lineage_stellar_account(self, mock_helpers):
        """Test lineage view with mocked data."""
        mock_instance = mock_helpers.return_value
        mock_instance.main.return_value = {
            'upstream_lineage': []
        }  # Stub response
        response = self.client.get(
            reverse(
                'apiApp:lineage_stellar_account',
                kwargs={
                    'network':
                    'testnet',
                    'stellar_account_address':
                    'GBRPYHIL2CI3FNQ4BXLFMNDLFJUNPU2HY3ZMFSHONUCEOASW7QC7OX2H'
                }))
        self.assertEqual(response.status_code, 200)


# ... (existing TestStellarNetwork, TestEnvHelpers, TestStellarMapValidatorHelpers remain; added assertions for getters)
class TestStellarNetwork(unittest.TestCase):

    def test_init_valid(self):
        """Test valid network init."""
        network = StellarNetwork('testnet')
        self.assertEqual(network.env_helpers.get_network(), 'testnet')

    def test_init_invalid(self):
        """Test invalid network raises ValueError."""
        with self.assertRaises(ValueError):
            StellarNetwork('invalid')


# Add similar for EnvHelpers, Validator
