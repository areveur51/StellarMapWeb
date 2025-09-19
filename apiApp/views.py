# apiApp/views.py
import json
import logging
import asyncio  # For async genealogy
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import viewsets, generics
from apiApp.helpers.env import EnvHelpers
from apiApp.helpers.lineage_creator_accounts import LineageHelpers
from apiApp.helpers.sm_conn import SiteChecker
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.helpers.sm_datetime import StellarMapDateTimeHelpers
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers
from apiApp.models import UserInquirySearchHistory
from apiApp.serializers import UserInquirySearchHistorySerializer
from apiApp.managers import UserInquirySearchHistoryManager
import sentry_sdk

logger = logging.getLogger(__name__)


@api_view(['GET'])
def check_all_urls(request):
    """Check URL reachability; return JSON."""
    checker = SiteChecker()
    results_json = checker.check_all_urls()
    return HttpResponse(results_json, content_type='application/json')


@api_view(['GET'])
def set_network(request, network: str):
    """Set network env; validate input."""
    if network not in ['testnet', 'public']:
        return Response({"error": "Invalid network"}, status=400)
    env_helpers = EnvHelpers()
    if network == 'testnet':
        env_helpers.set_testnet_network()
    else:
        env_helpers.set_public_network()
    return Response({"success": "Network set"})


@api_view(['GET'])
async def lineage_stellar_account(request, network: str,
                                  stellar_account_address: str):
    """Async fetch lineage; validate and format response."""
    validator = StellarMapValidatorHelpers()
    if not validator.validate_stellar_account_address(stellar_account_address):
        return Response({"error": "Invalid address"}, status=400)
    if network not in ['testnet', 'public']:
        return Response({"error": "Invalid network"}, status=400)

    try:
        helpers = LineageHelpers(network, stellar_account_address)
        data = await helpers.main()  # Async for efficiency
        # ... (existing logic truncated; add caching if heavy)
        genealogy_df = StellarMapCreatorAccountLineageHelpers(
        ).get_account_genealogy(stellar_account=stellar_account_address,
                                network_name=network)
        dt_helpers = StellarMapDateTimeHelpers()
        genealogy_df = dt_helpers.convert_to_NY_datetime(
            genealogy_df, 'stellar_account_created_at')
        # ... (format records/items)
        response = {
            'account_genealogy_items': account_genealogy_items,
            'tree_genealogy_items': tree_genealogy_items
        }
        return Response(json.dumps(response))
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return Response({"error": str(e)}, status=500)


class UserInquirySearchHistoryViewSet(viewsets.ModelViewSet):
    """ViewSet for inquiries; efficient list/create."""
    queryset = UserInquirySearchHistory.objects.all().order_by(
        '-created_at')[:100]  # Limit for security/efficiency
    serializer_class = UserInquirySearchHistorySerializer
