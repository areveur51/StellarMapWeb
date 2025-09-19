# webApp/views.py
import json
from decouple import config
from django.shortcuts import redirect, render
from django.urls import reverse
from django.conf import settings
from django.core.cache import cache  # For efficient caching
from django.http import Http404  # For secure error handling
import sentry_sdk
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers  # For secure validation


def redirect_to_search_view(request):
    """
    Redirect root to search view.

    Returns:
        HttpResponseRedirect: To search_view.
    """
    return redirect(reverse('webApp:search_view'))


def search_view(request):
    """
    Handle search view: Validate params, fetch genealogy, render with context.

    Uses caching for genealogy data to reduce API/DB load.

    Args:
        request: HttpRequest object.

    Returns:
        HttpResponse: Rendered template.

    Raises:
        Http404: On invalid inputs.
    """
    account = request.GET.get(
        'account', 'GD6WU64OEP5C4LRBH6NK3MHYIA2ADN6K6II6EXPNVUR3ERBXT4AN4ACD'
    )  # Secure default
    network = request.GET.get('network', 'public')  # Secure default

    # Secure validation
    validator = StellarMapValidatorHelpers()
    if not validator.validate_stellar_account_address(account):
        sentry_sdk.capture_message(f"Invalid Stellar account: {account}")
        raise Http404("Invalid Stellar account address")
    if network not in ['public', 'testnet']:
        raise Http404("Invalid network")

    # Efficient caching: Key by params, 5min timeout
    cache_key = f"genealogy_{account}_{network}"
    genealogy_data = cache.get(cache_key)
    if not genealogy_data:
        try:
            lineage_helpers = StellarMapCreatorAccountLineageHelpers()
            genealogy_df = lineage_helpers.get_account_genealogy(
                account, network)
            tree_data = lineage_helpers.generate_tidy_radial_tree_genealogy(
                genealogy_df)
            account_genealogy_items = genealogy_df.to_dict(
                orient='records') if not genealogy_df.empty else []
            genealogy_data = {
                'account_genealogy_items': account_genealogy_items,
                'tree_data': tree_data
            }
            cache.set(cache_key, genealogy_data, 300)  # Cache for efficiency
        except Exception as e:
            sentry_sdk.capture_exception(e)
            genealogy_data = {
                'account_genealogy_items': [],
                'tree_data': {
                    'name': 'Root',
                    'node_type': 'ISSUER',
                    'children': []
                }  # Graceful fallback
            }

    context = {
        'search_variable': 'Hello World!',  # Placeholder
        'ENV': config('ENV'),
        'SENTRY_DSN_VUE': config('SENTRY_DSN_VUE'),
        'account_genealogy_items': genealogy_data['account_genealogy_items'],
        'tree_data': genealogy_data['tree_data'],  # Dict for template
        'query_account': account,
        'network_selected': network,
    }
    return render(request, 'webApp/search.html', context)
