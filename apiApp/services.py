# apiApp/services.py
import json
import requests
import sentry_sdk
from decouple import config
from django.http import HttpRequest
from tenacity import retry, stop_after_attempt, wait_exponential
from apiApp.managers import ManagementCronHealthManager

# Secure env var loading
ASTRA_DB_ID = config('ASTRA_DB_ID')
ASTRA_DB_REGION = config('ASTRA_DB_REGION')
ASTRA_DB_KEYSPACE = config('ASTRA_DB_KEYSPACE', default=config('CASSANDRA_KEYSPACE'))
ASTRA_DB_APPLICATION_TOKEN = config('ASTRA_DB_APPLICATION_TOKEN', default=config('ASTRA_DB_TOKEN'))


class AstraDocument:
    """
    Helper for Astra DB document operations via REST API.

    Manages PATCH/GET with retries; maps collections to attributes.
    """

    def __init__(self):
        """Initialize headers with token."""
        self.headers = {
            "X-Cassandra-Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json",
            "User-Agent": "StellarMap/1.0"  # Secure identification
        }
        self.collections_name = "default"
        self.document_id = "default"
        self.url = ""

    def set_document_id(self, document_id: str):
        """Set document ID."""
        self.document_id = document_id

    def set_collections_name(self, collections_name: str):
        """
        Set collection name and update URL.

        Args:
            collections_name (str): e.g., 'horizon_accounts'.
        """
        self.collections_name = collections_name
        self.url = (
            f"https://{ASTRA_DB_ID}-{ASTRA_DB_REGION}.apps.astra.datastax.com"
            f"/api/rest/v2/namespaces/{ASTRA_DB_KEYSPACE}/collections/"
            f"{self.collections_name}/{self.document_id}")

    @retry(wait=wait_exponential(multiplier=1, max=7),
           stop=stop_after_attempt(7))
    def patch_document(self, stellar_account: str, network_name: str,
                       external_url: str, raw_data: dict,
                       cron_name: str) -> dict:
        """
        PATCH document with data.

        Args:
            stellar_account (str): Account address.
            network_name (str): Network.
            external_url (str): External URL.
            raw_data (dict): Raw data to store.
            cron_name (str): Cron for health tracking.

        Returns:
            dict: {'documentId': str, 'href': str}

        Raises:
            Exception: On failure (retried 7x).
        """
        data = {
            "stellar_account": stellar_account,
            "network_name": network_name,
            "external_url": external_url,
            "raw_data": raw_data
        }
        try:
            response = requests.patch(self.url,
                                      headers=self.headers,
                                      json=data,
                                      timeout=10)  # Secure JSON/timeout
            if response.status_code == 200:
                doc_id = response.json().get("documentId", "")
                return {"documentId": doc_id, "href": self.url}
            raise Exception(f"Failed to PATCH: {response.content}")
        except Exception as e:
            sentry_sdk.capture_exception(e)
            # Create health record
            req = HttpRequest()
            req.data = {
                'cron_name': cron_name,
                'status': 'UNHEALTHY_RATE_LIMITED_BY_CASSANDRA_DOCUMENT_API',
                'reason': str(e)
            }
            ManagementCronHealthManager().create_cron_health(req)
            raise

    def set_datastax_url(self, datastax_url: str):
        """Set custom Datastax URL."""
        self.datastax_url = datastax_url

    @retry(wait=wait_exponential(multiplier=1, max=7),
           stop=stop_after_attempt(7))
    def get_document(self) -> dict:
        """
        GET document by URL.

        Returns:
            dict: JSON response.

        Raises:
            Exception: On failure.
        """
        try:
            response = requests.get(self.datastax_url,
                                    headers=self.headers,
                                    timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise
