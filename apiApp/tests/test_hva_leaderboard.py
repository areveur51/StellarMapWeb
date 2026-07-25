"""
Unit tests for HVA leaderboard performance path.

Guards against regressions that caused multi-minute page loads:
- full-table list() on Cassandra lineage
- unbounded rank-change N+1 enrichment
- missing response cache
"""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apiApp.helpers.hva_leaderboard import (
    _fetch_cassandra_top_records,
    build_hva_leaderboard,
    cache_key,
    invalidate_hva_leaderboard_cache,
)


def _fake_account(addr, balance, network="public", is_hva=True, tags="HVA"):
    return SimpleNamespace(
        stellar_account=addr,
        network_name=network,
        xlm_balance=balance,
        is_hva=is_hva,
        tags=tags,
        stellar_creator_account="GCREATOR",
        home_domain="example.com",
        status="COMPLETE",
        created_at=None,
        updated_at=None,
    )


class HvaLeaderboardUnitTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_settings(USE_CASSANDRA=False, HVA_CACHE_TTL_SEC=60, HVA_DISPLAY_LIMIT=10)
    @patch("apiApp.helpers.hva_ranking.HVARankingHelper.get_supported_thresholds")
    @patch("apiApp.helpers.hva_ranking.HVARankingHelper.get_hva_threshold")
    @patch("apiApp.helpers.hva_leaderboard._fetch_sql_records")
    def test_sql_path_uses_top_n_and_threshold(
        self, mock_sql, mock_threshold, mock_supported
    ):
        mock_threshold.return_value = 100000.0
        mock_supported.return_value = [10000.0, 100000.0, 1000000.0]
        mock_sql.return_value = [
            _fake_account("GAAA", 500000),
            _fake_account("GBBB", 200000),
        ]

        payload = build_hva_leaderboard(
            network_name="public",
            selected_threshold=100000,
            display_limit=10,
            use_cache=False,
            enrich_rank_changes=False,
        )

        mock_sql.assert_called_once()
        args = mock_sql.call_args[0]
        self.assertEqual(args[0], "public")
        self.assertEqual(args[1], 100000.0)
        self.assertEqual(args[2], 10)
        self.assertEqual(payload["total_hva_count"], 2)
        self.assertEqual(payload["hva_accounts"][0]["stellar_account"], "GAAA")
        self.assertEqual(payload["hva_accounts"][0]["current_rank"], 1)
        self.assertEqual(payload["meta"]["backend"], "sql")

    @override_settings(
        USE_CASSANDRA=True,
        HVA_CACHE_TTL_SEC=60,
        HVA_DISPLAY_LIMIT=5,
        HVA_CASSANDRA_MAX_SCAN=50,
        HVA_RANK_ENRICH_LIMIT=0,
    )
    @patch("apiApp.helpers.hva_ranking.HVARankingHelper.get_supported_thresholds")
    @patch("apiApp.helpers.hva_ranking.HVARankingHelper.get_hva_threshold")
    @patch("apiApp.helpers.hva_leaderboard._fetch_cassandra_top_records")
    def test_cassandra_path_uses_bounded_scan(
        self, mock_cass, mock_threshold, mock_supported
    ):
        mock_threshold.return_value = 100000.0
        mock_supported.return_value = [100000.0]
        mock_cass.return_value = (
            [_fake_account("GCCC", 900000)],
            {"scanned": 40, "hit_scan_limit": False, "qualifying_seen": 1},
        )

        payload = build_hva_leaderboard(
            network_name="public",
            selected_threshold=100000,
            use_cache=False,
            enrich_rank_changes=False,
        )

        mock_cass.assert_called_once()
        # Positional: (network, threshold, limit, max_scan, max_seconds)
        args = mock_cass.call_args[0]
        self.assertEqual(args[2], 5)  # limit
        self.assertEqual(args[3], 50)  # max_scan
        self.assertEqual(payload["meta"]["backend"], "cassandra")
        self.assertEqual(payload["meta"]["scanned"], 40)
        self.assertEqual(payload["total_hva_count"], 1)

    @override_settings(USE_CASSANDRA=False, HVA_CACHE_TTL_SEC=120)
    @patch("apiApp.helpers.hva_ranking.HVARankingHelper.get_supported_thresholds")
    @patch("apiApp.helpers.hva_ranking.HVARankingHelper.get_hva_threshold")
    @patch("apiApp.helpers.hva_leaderboard._fetch_sql_records")
    def test_cache_hit_avoids_second_db_fetch(
        self, mock_sql, mock_threshold, mock_supported
    ):
        mock_threshold.return_value = 100000.0
        mock_supported.return_value = [100000.0]
        mock_sql.return_value = [_fake_account("GDDD", 150000)]

        first = build_hva_leaderboard(
            network_name="public",
            selected_threshold=100000,
            display_limit=10,
            use_cache=True,
            enrich_rank_changes=False,
        )
        second = build_hva_leaderboard(
            network_name="public",
            selected_threshold=100000,
            display_limit=10,
            use_cache=True,
            enrich_rank_changes=False,
        )

        self.assertEqual(mock_sql.call_count, 1)
        self.assertFalse(first["meta"]["cache_hit"])
        self.assertTrue(second["meta"]["cache_hit"])
        self.assertEqual(second["hva_accounts"][0]["stellar_account"], "GDDD")

    def test_cassandra_scan_respects_max_scan_and_top_n(self):
        """Heap keeps highest balances without materializing full sorted table."""
        rows = [
            _fake_account(f"G{i:04d}", float(i * 1000), is_hva=True)
            for i in range(1, 101)
        ]
        # balances 1000..100000 — top 3 should be 100k, 99k, 98k

        mock_qs = MagicMock()
        mock_qs.iterator.return_value = iter(rows)

        with patch(
            "apiApp.model_loader.StellarCreatorAccountLineage"
        ) as mock_model:
            mock_model.objects.filter.return_value = mock_qs
            top, meta = _fetch_cassandra_top_records(
                network_name="public",
                threshold=50000,
                limit=3,
                max_scan=1000,
            )

        self.assertEqual(len(top), 3)
        balances = [r.xlm_balance for r in top]
        self.assertEqual(balances, [100000.0, 99000.0, 98000.0])
        self.assertFalse(meta["hit_scan_limit"])
        self.assertEqual(meta["scanned"], 100)

    def test_cassandra_scan_stops_at_max_scan(self):
        def endless():
            i = 0
            while True:
                i += 1
                yield _fake_account(f"G{i}", 200000.0)

        mock_qs = MagicMock()
        mock_qs.iterator.return_value = endless()

        with patch(
            "apiApp.model_loader.StellarCreatorAccountLineage"
        ) as mock_model:
            mock_model.objects.filter.return_value = mock_qs
            top, meta = _fetch_cassandra_top_records(
                network_name="public",
                threshold=100000,
                limit=5,
                max_scan=30,
                max_seconds=30.0,
            )

        self.assertTrue(meta["hit_scan_limit"])
        self.assertEqual(meta["scanned"], 31)  # break after exceeding
        self.assertEqual(len(top), 5)

    def test_cassandra_scan_stops_at_time_budget(self):
        """Wall-clock budget must stop iteration even if max_scan is huge."""

        def slow_endless():
            i = 0
            while True:
                i += 1
                time.sleep(0.05)
                yield _fake_account(f"G{i}", 200000.0)

        mock_qs = MagicMock()
        mock_qs.iterator.return_value = slow_endless()

        with patch(
            "apiApp.model_loader.StellarCreatorAccountLineage"
        ) as mock_model:
            mock_model.objects.filter.return_value = mock_qs
            t0 = time.monotonic()
            top, meta = _fetch_cassandra_top_records(
                network_name="public",
                threshold=100000,
                limit=50,
                max_scan=100000,
                max_seconds=0.2,
            )
            elapsed = time.monotonic() - t0

        self.assertTrue(meta["hit_time_limit"])
        self.assertLess(elapsed, 1.5)
        self.assertGreaterEqual(len(top), 1)

    @override_settings(USE_CASSANDRA=True, HVA_RANK_ENRICH_LIMIT=0)
    @patch("apiApp.helpers.hva_ranking.HVARankingHelper.get_supported_thresholds")
    @patch("apiApp.helpers.hva_ranking.HVARankingHelper.get_hva_threshold")
    @patch("apiApp.helpers.hva_leaderboard._enrich_rank_changes")
    @patch("apiApp.helpers.hva_leaderboard._fetch_cassandra_top_records")
    def test_rank_enrichment_skipped_on_cassandra_by_default(
        self, mock_cass, mock_enrich, mock_threshold, mock_supported
    ):
        mock_threshold.return_value = 100000.0
        mock_supported.return_value = [100000.0]
        mock_cass.return_value = (
            [_fake_account("GEEE", 300000)],
            {"scanned": 1, "hit_scan_limit": False, "qualifying_seen": 1},
        )
        mock_enrich.return_value = {}

        build_hva_leaderboard(
            network_name="public",
            selected_threshold=100000,
            use_cache=False,
            # default enrich_rank_changes is False when USE_CASSANDRA
        )

        # Called with enrich_limit 0
        mock_enrich.assert_called_once()
        self.assertEqual(mock_enrich.call_args[0][3], 0)

    def test_cache_key_stable(self):
        self.assertEqual(
            cache_key("public", 100000.0, 100),
            "hva_lb:v2:public:100000:100",
        )

    def test_invalidate_cache_helper(self):
        ck = cache_key("public", 100000.0, 100)
        cache.set(ck, {"x": 1}, 60)
        invalidate_hva_leaderboard_cache("public", 100000.0)
        self.assertIsNone(cache.get(ck))

    @override_settings(USE_CASSANDRA=False)
    @patch("apiApp.helpers.hva_ranking.HVARankingHelper.get_supported_thresholds")
    @patch("apiApp.helpers.hva_ranking.HVARankingHelper.get_hva_threshold")
    @patch("apiApp.helpers.hva_leaderboard._fetch_sql_records")
    def test_snaps_threshold_to_supported(
        self, mock_sql, mock_threshold, mock_supported
    ):
        mock_threshold.return_value = 100000.0
        mock_supported.return_value = [10000.0, 100000.0, 1000000.0]
        mock_sql.return_value = []

        payload = build_hva_leaderboard(
            network_name="public",
            selected_threshold=120000,  # closest is 100000
            use_cache=False,
            enrich_rank_changes=False,
        )
        self.assertEqual(payload["selected_threshold"], 100000.0)


class HvaPageViewContractTests(SimpleTestCase):
    """View should not reintroduce full-table list() patterns."""

    def test_view_delegates_to_leaderboard_helper(self):
        from pathlib import Path

        views = (
            Path(__file__).resolve().parents[2]
            / "webApp"
            / "views.py"
        ).read_text()
        self.assertIn("build_hva_leaderboard", views)
        # Old anti-pattern must not return
        self.assertNotIn(
            "StellarCreatorAccountLineage.objects.filter(\n"
            "                is_hva=True,\n"
            "                network_name=network_name,\n"
            "            )\n"
            "            records = list(qs)",
            views,
        )
        self.assertIn("high_value_accounts_view", views)

    def test_helper_module_has_scan_cap(self):
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[1]
            / "helpers"
            / "hva_leaderboard.py"
        ).read_text()
        self.assertIn("DEFAULT_CASSANDRA_MAX_SCAN", src)
        self.assertIn("heapq", src)
        self.assertIn("cache_hit", src)
