import asyncio
from django.db import transaction
from apiApp.models import UserInquirySearchHistory
import sentry_sdk


class AsyncStellarInquiryCreator:
    """
    Async creator for Stellar inquiries.

    Note: Django ORM is sync; uses run_in_threadpool for async compatibility.
    Run via asyncio.run() or create_task().
    """

    async def create_inquiry(self, stellar_account: str, network_name: str,
                             status: str):
        """
        Create inquiry async.

        Args:
            stellar_account (str): Address (validate externally).
            network_name (str): Network name.
            status (str): Initial status.

        Returns:
            UserInquirySearchHistory: Created object or error.

        Raises:
            Exception: On DB failure.
        """
        try:

            def sync_create():
                with transaction.atomic():  # Sync transaction
                    inquiry = UserInquirySearchHistory(
                        stellar_account=stellar_account,
                        network_name=network_name,
                        status=status)
                    inquiry.save()
                    return inquiry

            return await asyncio.get_running_loop().run_in_executor(
                None, sync_create)  # True async via executor
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return e
