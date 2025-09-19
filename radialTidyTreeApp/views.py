# radialTidyTreeApp/views.py
import json
from django.shortcuts import render
from django.core.cache import cache  # For efficient caching
from django.http import Http404  # For secure error handling
import sentry_sdk
from apiApp.helpers.sm_creatoraccountlineage import StellarMapCreatorAccountLineageHelpers
from apiApp.helpers.sm_validator import StellarMapValidatorHelpers  # For secure validation


def radial_tidy_tree_view(request):
  """
    Render radial tidy tree view with dynamic tree data.

    Fetches/validates account/network from GET params, generates tree using helpers,
    caches for efficiency, and passes to template.

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

  # Efficient caching: Key based on params, 5min timeout
  cache_key = f"tree_data_{account}_{network}"
  tree_data = cache.get(cache_key)
  if not tree_data:
    try:
      helpers = StellarMapCreatorAccountLineageHelpers()
      genealogy_df = helpers.get_account_genealogy(stellar_account=account,
                                                   network_name=network)
      tree_data = helpers.generate_tidy_radial_tree_genealogy(genealogy_df)
      cache.set(cache_key, tree_data, 300)  # Cache for efficiency
    except Exception as e:
      sentry_sdk.capture_exception(e)
      tree_data = {
          'name': 'Root',
          'node_type': 'ISSUER',
          'children': []
      }  # Graceful fallback

  context = {
      'tree_data': json.dumps(tree_data),  # Safe JSON dump
      'radial_tidy_tree_variable': 'Hello World!',  # Placeholder
      'account': account,
      'network': network,
  }
  return render(request, 'radialTidyTreeApp/radial_tidy_tree.html', context)
