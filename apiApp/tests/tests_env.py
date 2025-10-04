from django.test import TestCase
from apiApp.helpers.env import EnvHelpers, StellarNetwork


class EnvHelpersTestCase(TestCase):
    
    def setUp(self):
        self.env_helpers = EnvHelpers()
    
    def test_init_defaults_to_testnet(self):
        self.assertEqual(self.env_helpers.network, 'testnet')
        self.assertIn('testnet', self.env_helpers.base_horizon)
    
    def test_set_testnet_network(self):
        self.env_helpers.set_testnet_network()
        self.assertEqual(self.env_helpers.network, 'testnet')
        self.assertEqual(self.env_helpers.debug, 'True')
        self.assertIn('testnet', self.env_helpers.base_horizon)
        self.assertIn('testnet', self.env_helpers.base_site_network)
    
    def test_set_public_network(self):
        self.env_helpers.set_public_network()
        self.assertEqual(self.env_helpers.network, 'public')
        self.assertEqual(self.env_helpers.debug, 'False')
        self.assertNotIn('testnet', self.env_helpers.base_horizon)
        self.assertIn('public', self.env_helpers.base_site_network)
    
    def test_base_network_urls_set_correctly(self):
        self.env_helpers.set_public_network()
        self.assertIsNotNone(self.env_helpers.base_site_network)
        self.assertIsNotNone(self.env_helpers.base_site_network_account)
        self.assertIsNotNone(self.env_helpers.base_se_network)
        self.assertIsNotNone(self.env_helpers.base_horizon_account)
        self.assertIn('public', self.env_helpers.base_se_network)


class StellarNetworkTestCase(TestCase):
    
    def test_init_with_testnet(self):
        stellar_network = StellarNetwork('testnet')
        self.assertEqual(stellar_network.env_helpers.network, 'testnet')
    
    def test_init_with_public(self):
        stellar_network = StellarNetwork('public')
        self.assertEqual(stellar_network.env_helpers.network, 'public')
    
    def test_init_with_invalid_network_raises_error(self):
        with self.assertRaises(ValueError):
            StellarNetwork('invalid_network')
