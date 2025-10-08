# apiApp/services.py
import json
import sentry_sdk
from decouple import config
from django.http import HttpRequest
from tenacity import retry, stop_after_attempt, wait_exponential
from apiApp.managers import ManagementCronHealthManager

# Secure env var loading
ASTRA_DB_KEYSPACE = config('ASTRA_DB_KEYSPACE', default=config('CASSANDRA_KEYSPACE'))


class AstraDocument:
    """
    Helper for storing Horizon JSON data directly in Cassandra TEXT columns.
    
    Replaces REST API Document Collections with direct Cassandra storage.
    Stores JSON data in TEXT columns on StellarCreatorAccountLineage model.
    """

    def __init__(self):
        """Initialize with defaults."""
        self.collections_name = "default"
        self.document_id = "default"
        self.url = ""

    def set_document_id(self, document_id: str):
        """Set document ID (maintained for API compatibility)."""
        self.document_id = document_id

    def set_collections_name(self, collections_name: str):
        """
        Set collection name (maintained for API compatibility).
        
        Args:
            collections_name (str): e.g., 'horizon_accounts', 'horizon_operations', 'horizon_effects'.
        """
        self.collections_name = collections_name

    @retry(wait=wait_exponential(multiplier=1, max=7),
           stop=stop_after_attempt(7))
    def patch_document(self, stellar_account: str, network_name: str,
                       external_url: str, raw_data: dict,
                       cron_name: str) -> dict:
        """
        Store JSON data directly in Cassandra TEXT column.
        
        Args:
            stellar_account (str): Account address.
            network_name (str): Network.
            external_url (str): External URL.
            raw_data (dict): Raw data to store as JSON.
            cron_name (str): Cron for health tracking.
        
        Returns:
            dict: {'documentId': str, 'href': str}
        
        Raises:
            Exception: On failure (retried 7x).
        """
        try:
            from apiApp.models import StellarCreatorAccountLineage
            
            # Get the lineage record
            lineage = StellarCreatorAccountLineage.objects.filter(
                stellar_account=stellar_account,
                network_name=network_name
            ).first()
            
            if not lineage:
                raise Exception(f"Lineage record not found for {stellar_account}")
            
            # Determine which JSON column to update based on collection name
            json_str = json.dumps(raw_data)
            
            # Use queryset.update() for Cassandra compatibility
            queryset = StellarCreatorAccountLineage.objects.filter(
                stellar_account=stellar_account,
                network_name=network_name
            )
            
            if self.collections_name == "horizon_accounts":
                queryset.update(horizon_accounts_json=json_str)
            elif self.collections_name == "horizon_operations":
                queryset.update(horizon_operations_json=json_str)
            elif self.collections_name == "horizon_effects":
                queryset.update(horizon_effects_json=json_str)
            else:
                raise Exception(f"Unknown collection name: {self.collections_name}")
            
            # Build pseudo-URL with actual account ID
            self.url = (
                f"cassandra://{ASTRA_DB_KEYSPACE}/"
                f"{self.collections_name}/{stellar_account}_{network_name}")
            
            # Return format compatible with old REST API response
            doc_id = f"{stellar_account}_{self.collections_name}"
            return {"documentId": doc_id, "href": self.url}
            
        except Exception as e:
            sentry_sdk.capture_exception(e)
            # Create health record
            req = HttpRequest()
            req.data = {
                'cron_name': cron_name,
                'status': 'UNHEALTHY_CASSANDRA_JSON_STORAGE_ERROR',
                'reason': str(e)
            }
            ManagementCronHealthManager().create_cron_health(req)
            raise

    def set_datastax_url(self, datastax_url: str):
        """Set custom Datastax URL (maintained for API compatibility)."""
        self.datastax_url = datastax_url

    @retry(wait=wait_exponential(multiplier=1, max=7),
           stop=stop_after_attempt(7))
    def get_document(self) -> dict:
        """
        Retrieve JSON data from Cassandra TEXT column.
        
        Returns:
            dict: JSON response with structure matching old REST API format.
        
        Raises:
            Exception: On failure.
        """
        try:
            from apiApp.models import StellarCreatorAccountLineage
            
            # Parse pseudo-URL to extract account, network, and collection name
            # Format: cassandra://{keyspace}/{collection_name}/{stellar_account}_{network_name}
            parts = self.datastax_url.split('/')
            account_network = parts[-1]
            collection_name = parts[-2]
            
            # Split account and network (format: ACCOUNT_network)
            if '_' in account_network:
                account_parts = account_network.rsplit('_', 1)
                stellar_account = account_parts[0]
                network_name = account_parts[1]
            else:
                # Fallback for old format without network
                stellar_account = account_network
                network_name = 'public'
            
            # Get the lineage record with network filter
            lineage = StellarCreatorAccountLineage.objects.filter(
                stellar_account=stellar_account,
                network_name=network_name
            ).first()
            
            if not lineage:
                raise Exception(f"Lineage record not found for {stellar_account} on {network_name}")
            
            # Retrieve JSON from appropriate column
            json_str = None
            if collection_name == "horizon_accounts":
                json_str = lineage.horizon_accounts_json
            elif collection_name == "horizon_operations":
                json_str = lineage.horizon_operations_json
            elif collection_name == "horizon_effects":
                json_str = lineage.horizon_effects_json
            else:
                raise Exception(f"Unknown collection name: {collection_name}")
            
            if not json_str:
                raise Exception(f"No JSON data found in {collection_name} for {stellar_account}")
            
            # Parse and return
            data = json.loads(json_str)
            
            # Wrap in format compatible with old REST API response
            return {
                "data": {
                    "stellar_account": stellar_account,
                    "raw_data": data
                }
            }
            
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise
