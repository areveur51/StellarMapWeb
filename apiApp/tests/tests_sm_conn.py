from django.test import TestCase
from unittest.mock import patch, Mock, AsyncMock
import asyncio
from apiApp.helpers.sm_conn import SiteChecker, AsyncStellarMapHTTPHelpers


class SiteCheckerTestCase(TestCase):
    
    def setUp(self):
        self.site_checker = SiteChecker()
    
    @patch('apiApp.helpers.sm_conn.requests.get')
    def test_check_url_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = self.site_checker.check_url("https://example.com")
        self.assertTrue(result)
    
    @patch('apiApp.helpers.sm_conn.requests.get')
    def test_check_url_failure(self, mock_get):
        mock_get.side_effect = Exception("Connection error")
        
        result = self.site_checker.check_url("https://invalid-url.com")
        self.assertFalse(result)
    
    @patch('apiApp.helpers.sm_conn.requests.get')
    def test_check_all_urls(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = self.site_checker.check_all_urls()
        self.assertIsInstance(result, str)


class AsyncStellarMapHTTPHelpersTestCase(TestCase):
    
    def setUp(self):
        self.http_helpers = AsyncStellarMapHTTPHelpers()
    
    @patch('aiohttp.ClientSession.get')
    async def test_get_success(self, mock_get):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"key": "value"})
        mock_get.return_value.__aenter__.return_value = mock_response
        
        result = await self.http_helpers.get("https://example.com/api")
        self.assertEqual(result, {"key": "value"})
    
    def test_get_async(self):
        async def run_test():
            with patch('aiohttp.ClientSession') as mock_session:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value={"data": "test"})
                mock_response.raise_for_status = Mock()
                
                mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
                
                result = await self.http_helpers.get("https://example.com")
                self.assertIsInstance(result, dict)
        
        asyncio.run(run_test())
