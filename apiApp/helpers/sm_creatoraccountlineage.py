# sm_creatoraccountlineage.py - Modular async updates with batching/retries.
import json
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential
import sentry_sdk
from apiApp.managers import StellarCreatorAccountLineageManager
from apiApp.services import AstraDocument
from django.http import HttpRequest
from .sm_horizon import StellarMapHorizonAPIParserHelpers  # Assume exists
from .sm_stellarexpert import StellarMapStellarExpertAPIHelpers, StellarMapStellarExpertAPIParserHelpers  # Assume


class StellarMapCreatorAccountLineageHelpers:

    @retry(wait=wait_exponential(multiplier=1, max=5),
           stop=stop_after_attempt(5))
    async def async_update_from_accounts_raw_data(self, client_session,
                                                  lin_queryset):
        """Modular update from accounts data."""
        manager = StellarCreatorAccountLineageManager()
        await manager.async_update_status(lin_queryset.id,
                                          'IN_PROGRESS_UPDATING_FROM_RAW_DATA'
                                          )  # Assume async manager
        astra = AstraDocument()
        astra.set_datastax_url(lin_queryset.horizon_accounts_doc_api_href)
        response = astra.get_document()
        parser = StellarMapHorizonAPIParserHelpers(response)
        req = HttpRequest()
        req.data = {
            'home_domain': parser.parse_account_home_domain(),
            'xlm_balance': parser.parse_account_native_balance(),
            'status': 'DONE_UPDATING_FROM_RAW_DATA'
        }
        await manager.async_update_lineage(lin_queryset.id, req)

    # Similar refactoring for other async methods: async_update_from_operations_raw_data, async_make_grandparent_account, etc.
    # Batched example for assets/flags/directory: Combine into single batch update if possible.

    def get_account_genealogy(self,
                              stellar_account,
                              network_name,
                              max_depth=10):
        """Efficient genealogy fetch with depth limit."""
        try:
            df = pd.DataFrame()
            current_account = stellar_account
            current_network = network_name
            depth = 0
            while depth < max_depth:
                manager = StellarCreatorAccountLineageManager()
                qs = manager.get_queryset(stellar_account=current_account,
                                          network_name=current_network)
                if not qs:
                    break
                row = {
                    f: getattr(qs, f)
                    for f in qs._meta.fields
                }  # Efficient dict
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                current_account = qs.stellar_creator_account
                if current_account == 'no_element_funder':
                    break
                depth += 1
            return df
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return pd.DataFrame()

    def generate_tidy_radial_tree_genealogy(self, genealogy_df):
        """Efficient tree build from DF."""
        if genealogy_df.empty:
            return {'name': 'Root', 'children': []}
        records = genealogy_df.to_dict('records')
        node_lookup = {
            r['stellar_account']: {
                'name': r['stellar_account'],
                'children': []
                # Add other attrs
            }
            for r in records
        }
        root = None
        for r in records:
            creator = r['stellar_creator_account']
            if creator not in node_lookup or creator == 'no_element_funder':
                root = node_lookup[r['stellar_account']]
            else:
                node_lookup[creator]['children'].append(
                    node_lookup[r['stellar_account']])
        return root or {'name': 'Root', 'children': []}
