# apiApp/helpers/sm_async.py
import asyncio
import aiohttp
import logging

logger = logging.getLogger(__name__)


class StellarMapAsyncHelpers:
    """
    Helper class to execute async operations on Django querysets.
    
    Provides a simple interface to run async methods on multiple records efficiently.
    """
    
    def execute_async(self, queryset, async_method):
        """
        Execute an async method for each item in the queryset.
        
        Args:
            queryset: Iterable of model instances to process
            async_method: Async method to call for each item (takes client_session and item)
        """
        asyncio.run(self._run_async_batch(queryset, async_method))
    
    async def _run_async_batch(self, queryset, async_method):
        """
        Internal method to run async operations with aiohttp session.
        
        Processes each item in the queryset by calling the async_method.
        """
        async with aiohttp.ClientSession() as session:
            tasks = [async_method(session, item) for item in queryset]
            await asyncio.gather(*tasks, return_exceptions=True)
