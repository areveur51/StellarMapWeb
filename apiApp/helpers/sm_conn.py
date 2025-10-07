# sm_conn.py - Secure async HTTP, Cassandra conn with env.
import aiohttp
import json
import logging
import requests
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from decouple import config
from tenacity import retry, stop_after_attempt, wait_exponential
import sentry_sdk

logger = logging.getLogger(__name__)
APP_PATH = config('APP_PATH')
CASSANDRA_KEYSPACE = config('CASSANDRA_KEYSPACE')
# CASSANDRA_HOST no longer needed with cloud connection
# Removed CLIENT_ID and CLIENT_SECRET - now using ASTRA_DB_TOKEN for authentication


class SiteChecker:

    @retry(wait=wait_exponential(multiplier=1, max=5),
           stop=stop_after_attempt(5))
    def check_url(self, url: str) -> bool:
        """Secure URL check with timeout."""
        try:
            response = requests.get(url,
                                    timeout=5,
                                    headers={'User-Agent': 'StellarMap/1.0'})
            response.raise_for_status()
            return True
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return False

    def check_all_urls(self):
        sites_dict = {  # Your sites
            "stellar_github": "https://github.com/stellar",
            # ... add others
        }
        results = {
            site: self.check_url(url)
            for site, url in sites_dict.items()
        }
        return json.dumps(results)


class AsyncStellarMapHTTPHelpers:  # Made primary; sync deprecated

    async def get(self, url: str) -> dict:
        """Secure async GET with headers/timeout."""
        headers = {'User-Agent': 'StellarMap/1.0'}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=10) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise ValueError(f'Error: {e}')


class CassandraConnectionsHelpers:

    def __init__(self):
        self.cloud_config = {
            'secure_connect_bundle':
            f"{APP_PATH}/secure-connect-stellarmapwebastradb.zip"
        }
        self.auth_provider = PlainTextAuthProvider("token", config('ASTRA_DB_TOKEN'))
        self.cluster = Cluster(cloud=self.cloud_config,
                               auth_provider=self.auth_provider,
                               )
        self.session = self.cluster.connect(CASSANDRA_KEYSPACE)
        self.cql_query = None

    def set_cql_query(self, cql_query: str):
        self.cql_query = cql_query

    def execute_cql(self):
        try:
            return self.session.execute(self.cql_query)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise e

    def close_connection(self):
        self.session.shutdown()
        self.cluster.shutdown()
