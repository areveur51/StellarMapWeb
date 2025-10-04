from django.test import TestCase
from django.urls import reverse


class ApiHomeViewTestCase(TestCase):
    
    def test_api_home_returns_200(self):
        response = self.client.get(reverse('apiApp:api_home'))
        self.assertEqual(response.status_code, 200)
    
    def test_api_home_returns_json(self):
        response = self.client.get(reverse('apiApp:api_home'))
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_api_home_contains_success_message(self):
        response = self.client.get(reverse('apiApp:api_home'))
        data = response.json()
        self.assertIn('message', data)
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'success')
    
    def test_api_home_contains_version(self):
        response = self.client.get(reverse('apiApp:api_home'))
        data = response.json()
        self.assertIn('version', data)
