"""
PR4: lineage APIs via aggregator, process-local response cache, rate limits.
"""
import inspect
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.test import Client

from apiApp import views as api_views
from apiApp.helpers import sm_lineage_response_cache as resp_cache


class RateLimitDecoratorPresenceTests(SimpleTestCase):
    def test_siblings_api_has_ratelimit(self):
        # django-ratelimit wraps the function; original often on __wrapped__
        fn = api_views.lineage_with_siblings_api
        source = inspect.getsource(api_views)
        # Decorator applied in module source
        idx = source.find("def lineage_with_siblings_api")
        window = source[max(0, idx - 200) : idx]
        self.assertIn("@ratelimit", window)
        self.assertIn("30/m", window)

    def test_account_lineage_api_has_ratelimit(self):
        source = inspect.getsource(api_views)
        idx = source.find("def account_lineage_api")
        window = source[max(0, idx - 200) : idx]
        self.assertIn("@ratelimit", window)
        self.assertIn("20/m", window)


class ResponseCacheUnitTests(SimpleTestCase):
    def setUp(self):
        resp_cache.clear_all()

    def tearDown(self):
        resp_cache.clear_all()

    @override_settings(LINEAGE_API_RESPONSE_CACHE=True, POLL_INTERVAL_MS=60000, LIGHT_MODE=True)
    def test_roundtrip_and_lru(self):
        self.assertEqual(resp_cache.lineage_response_ttl_seconds(), 60)
        self.assertEqual(resp_cache.lineage_response_max_entries(), 32)

        key = resp_cache.cache_key("GABC", "public", kind="siblings")
        payload = {"account": "GABC", "lineage_path": ["GABC"], "meta": {}}
        self.assertTrue(resp_cache.set_cached(key, payload))
        data, hit = resp_cache.get_cached(key)
        self.assertTrue(hit)
        self.assertEqual(data["account"], "GABC")

    @override_settings(LINEAGE_API_RESPONSE_CACHE=False)
    def test_disabled(self):
        key = resp_cache.cache_key("GABC", "public")
        self.assertFalse(resp_cache.set_cached(key, {"a": 1}))
        data, hit = resp_cache.get_cached(key)
        self.assertFalse(hit)
        self.assertIsNone(data)

    @override_settings(LINEAGE_API_RESPONSE_CACHE=True)
    def test_skip_oversized(self):
        key = resp_cache.cache_key("GABC", "public")
        big = {"blob": "x" * (600 * 1024)}
        self.assertFalse(resp_cache.set_cached(key, big))


class SiblingsApiAggregatorTests(SimpleTestCase):
    def setUp(self):
        resp_cache.clear_all()
        self.client = Client()

    def tearDown(self):
        resp_cache.clear_all()

    @override_settings(LINEAGE_API_RESPONSE_CACHE=True, POLL_INTERVAL_MS=30000)
    @patch("apiApp.views.LineageAggregateService", create=True)
    def test_siblings_uses_aggregator_shape(self, _unused):
        # Patch where the view imports from
        mock_proj = {
            "account": "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB",
            "network": "public",
            "lineage_path": ["GROOT", "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"],
            "nodes": {},
            "siblings_by_creator": {},
            "tree": {"name": "GROOT", "children": []},
            "meta": {"build_ms": 5, "db_only": True},
            "schema_version": 1,
            "source": "database",
        }

        with patch(
            "apiApp.helpers.sm_lineage_aggregate.LineageAggregateService"
        ) as mock_cls:
            svc = MagicMock()
            svc.get_projection.return_value = mock_proj
            svc.to_siblings_response.return_value = {
                "account": mock_proj["account"],
                "network": "public",
                "lineage_path": mock_proj["lineage_path"],
                "siblings_by_creator": {},
                "all_account_data": {},
                "total_accounts": 0,
                "total_siblings": 0,
                "tree": mock_proj["tree"],
                "meta": dict(mock_proj["meta"]),
            }
            mock_cls.return_value = svc

            with patch(
                "apiApp.helpers.sm_validator.StellarMapValidatorHelpers.validate_stellar_account_address",
                return_value=True,
            ):
                r1 = self.client.get(
                    "/api/lineage-with-siblings/",
                    {
                        "account": mock_proj["account"],
                        "network": "public",
                    },
                )
                self.assertEqual(r1.status_code, 200)
                body1 = r1.json()
                self.assertIn("lineage_path", body1)
                self.assertIn("tree", body1)
                self.assertIn("meta", body1)
                self.assertFalse(body1["meta"].get("cached"))

                # Second request should hit process-local cache (no second build)
                r2 = self.client.get(
                    "/api/lineage-with-siblings/",
                    {
                        "account": mock_proj["account"],
                        "network": "public",
                    },
                )
                self.assertEqual(r2.status_code, 200)
                body2 = r2.json()
                self.assertTrue(body2["meta"].get("cached"))
                self.assertEqual(svc.get_projection.call_count, 1)

    def test_missing_params_400(self):
        r = self.client.get("/api/lineage-with-siblings/")
        self.assertEqual(r.status_code, 400)

    @override_settings(LINEAGE_API_RESPONSE_CACHE=True)
    def test_account_lineage_feature_frozen_fields(self):
        mock_proj = {
            "account": "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB",
            "network": "public",
            "lineage_path": ["G1"],
            "nodes": {
                "G1": {
                    "stellar_account": "G1",
                    "stellar_creator_account": None,
                    "network_name": "public",
                    "xlm_balance": 0,
                    "assets": [],
                    "status": "COMPLETE",
                    "is_issuer": False,
                    "in_lineage_path": True,
                }
            },
            "siblings_by_creator": {},
            "meta": {"db_only": True},
            "source": "database",
        }
        with patch(
            "apiApp.helpers.sm_lineage_aggregate.LineageAggregateService"
        ) as mock_cls:
            svc = MagicMock()
            svc.get_projection.return_value = mock_proj
            svc.to_lineage_api_response.return_value = {
                "account": mock_proj["account"],
                "network": "public",
                "lineage": [{"stellar_account": "G1", "hierarchy_level": 0}],
                "total_records": 1,
                "source": "database",
            }
            mock_cls.return_value = svc
            with patch(
                "apiApp.helpers.sm_validator.StellarMapValidatorHelpers.validate_stellar_account_address",
                return_value=True,
            ):
                r = self.client.get(
                    "/api/account-lineage/",
                    {
                        "account": mock_proj["account"],
                        "network": "public",
                    },
                )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body.get("deprecated"))
        self.assertEqual(body.get("prefer"), "/api/lineage-with-siblings/")
        self.assertIn("lineage", body)
        self.assertTrue(body.get("meta", {}).get("feature_frozen"))


class NoHorizonInLineageApisTests(SimpleTestCase):
    def test_account_lineage_source_has_no_horizon_age_path(self):
        source = inspect.getsource(api_views.account_lineage_api)
        self.assertNotIn("Skip_BigQuery", source)
        self.assertNotIn("horizon.stellar.org", source)
        self.assertIn("LineageAggregateService", source)

    def test_siblings_source_uses_aggregate(self):
        source = inspect.getsource(api_views.lineage_with_siblings_api)
        self.assertIn("LineageAggregateService", source)
        self.assertIn("to_siblings_response", source)
