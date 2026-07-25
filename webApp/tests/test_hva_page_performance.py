"""
HVA page view performance contracts.

Ensures the page stays fast under Cassandra RO and never reintroduces
full-table materialization of lineage.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, SimpleTestCase, override_settings


class HVAPagePerformanceViewTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_settings(
        USE_CASSANDRA=True,
        CASSANDRA_READ_ONLY=True,
        HVA_CACHE_TTL_SEC=60,
        HVA_CASSANDRA_MAX_SCAN=100,
        HVA_DISPLAY_LIMIT=20,
        HVA_RANK_ENRICH_LIMIT=0,
    )
    @patch("apiApp.helpers.hva_leaderboard.build_hva_leaderboard")
    def test_hva_page_uses_leaderboard_builder(self, mock_build):
        mock_build.return_value = {
            "hva_accounts": [
                {
                    "stellar_account": "GTESTACCOUNT123456789012345678901234567890",
                    "network_name": "public",
                    "xlm_balance": 250000.0,
                    "stellar_creator_account": "GCREATOR",
                    "home_domain": "",
                    "tags": ["HVA"],
                    "status": "COMPLETE",
                    "created_at": None,
                    "updated_at": None,
                    "current_rank": 1,
                    "rank_change": 0,
                    "event_type": None,
                    "previous_rank": None,
                    "balance_change_pct": 0.0,
                }
            ],
            "total_hva_count": 1,
            "total_hva_balance": 250000.0,
            "selected_threshold": 100000.0,
            "supported_thresholds": [100000.0],
            "admin_default_threshold": 100000.0,
            "hva_display_limit": 20,
            "meta": {"cache_hit": False, "backend": "cassandra"},
        }

        response = self.client.get("/web/high-value-accounts/")
        self.assertEqual(response.status_code, 200)
        mock_build.assert_called_once()
        self.assertContains(response, "High Value Accounts Leaderboard")
        self.assertContains(response, "GTESTACCOUNT")

    @override_settings(USE_CASSANDRA=True)
    @patch("apiApp.helpers.hva_leaderboard.build_hva_leaderboard")
    def test_hva_page_passes_threshold_query_param(self, mock_build):
        mock_build.return_value = {
            "hva_accounts": [],
            "total_hva_count": 0,
            "total_hva_balance": 0,
            "selected_threshold": 50000.0,
            "supported_thresholds": [50000.0, 100000.0],
            "admin_default_threshold": 100000.0,
            "hva_display_limit": 100,
            "meta": {},
        }
        response = self.client.get(
            "/web/high-value-accounts/", {"threshold": "50000", "network": "testnet"}
        )
        self.assertEqual(response.status_code, 200)
        kwargs = mock_build.call_args.kwargs
        self.assertEqual(kwargs["network_name"], "testnet")
        self.assertEqual(kwargs["selected_threshold"], 50000.0)

    @override_settings(USE_CASSANDRA=True)
    @patch("apiApp.helpers.hva_leaderboard.build_hva_leaderboard")
    def test_hva_page_survives_builder_errors(self, mock_build):
        mock_build.side_effect = RuntimeError("cassandra timeout")
        response = self.client.get("/web/high-value-accounts/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "High Value Accounts")

    def test_no_full_table_list_in_view_source(self):
        from pathlib import Path

        src = (Path(__file__).resolve().parents[1] / "views.py").read_text()
        # View must delegate; no local full-table list of is_hva
        self.assertIn("build_hva_leaderboard", src)
        self.assertNotIn("records = list(qs)", src)
