from django.test import TestCase
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from apiApp.helpers.async_stellar_account_inquiry_history import AsyncStellarInquiryCreator


class AsyncStellarInquiryCreatorTestCase(TestCase):
    
    def setUp(self):
        self.inquiry_creator = AsyncStellarInquiryCreator()
    
    @patch('apiApp.helpers.async_stellar_account_inquiry_history.UserInquirySearchHistory')
    async def test_create_inquiry_success(self, mock_inquiry_model):
        mock_inquiry = Mock()
        mock_inquiry.save = Mock()
        mock_inquiry_model.return_value = mock_inquiry
        
        stellar_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        network_name = "testnet"
        status = "PENDING"
        
        async def run_test():
            with patch('asyncio.get_running_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_inquiry)
                result = await self.inquiry_creator.create_inquiry(
                    stellar_account, network_name, status
                )
                self.assertIsNotNone(result)
        
        await run_test()
    
    def test_create_inquiry_async(self):
        async def run_test():
            stellar_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
            network_name = "testnet"
            status = "PENDING"
            
            with patch('asyncio.get_running_loop') as mock_loop:
                mock_inquiry = Mock()
                mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_inquiry)
                
                result = await self.inquiry_creator.create_inquiry(
                    stellar_account, network_name, status
                )
                
                self.assertIsNotNone(result)
        
        asyncio.run(run_test())
    
    @patch('apiApp.helpers.async_stellar_account_inquiry_history.sentry_sdk')
    async def test_create_inquiry_handles_exception(self, mock_sentry):
        async def run_test():
            with patch('asyncio.get_running_loop') as mock_loop:
                mock_loop.return_value.run_in_executor.side_effect = Exception("DB Error")
                
                result = await self.inquiry_creator.create_inquiry(
                    "ACCOUNT", "testnet", "PENDING"
                )
                
                self.assertIsInstance(result, Exception)
                mock_sentry.capture_exception.assert_called()
        
        await run_test()
