"""
PR3: search_view unified aggregate path (LINEAGE_UNIFIED_AGGREGATE).
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from webApp.views import (
    _is_terminal_search_cache_status,
    _search_ssr_via_unified_aggregate,
    _skeleton_tree,
)


class TerminalStatusTests(SimpleTestCase):
    def test_done_and_complete(self):
        self.assertTrue(_is_terminal_search_cache_status("DONE_MAKE_PARENT_LINEAGE"))
        self.assertTrue(_is_terminal_search_cache_status("COMPLETE"))
        self.assertTrue(_is_terminal_search_cache_status("BIGQUERY_COMPLETE"))
        self.assertTrue(_is_terminal_search_cache_status("API_COMPLETE"))

    def test_pending_not_terminal(self):
        self.assertFalse(_is_terminal_search_cache_status("PENDING"))
        self.assertFalse(_is_terminal_search_cache_status("PROCESSING"))
        self.assertFalse(_is_terminal_search_cache_status("IN_PROGRESS_MAKE_PARENT_LINEAGE"))
        self.assertFalse(_is_terminal_search_cache_status(None))


class SkeletonTreeTests(SimpleTestCase):
    def test_shape(self):
        t = _skeleton_tree("GABC")
        self.assertEqual(t["name"], "GABC")
        self.assertEqual(t["node_type"], "ISSUER")
        self.assertEqual(t["children"], [])


class UnifiedSsrPathTests(SimpleTestCase):
    @override_settings(
        LINEAGE_UNIFIED_AGGREGATE=True,
        LINEAGE_WRITE_PROJECTION=False,
        LINEAGE_SSR_INCLUDE_SIBLINGS=False,
        LIGHT_MODE=True,
    )
    @patch("webApp.views.initialize_stage_executions")
    @patch("webApp.views.StellarMapCacheHelpers")
    @patch("apiApp.helpers.sm_lineage_aggregate.LineageAggregateService")
    def test_terminal_invalid_body_rebuilds_without_pending(
        self, mock_svc_cls, mock_cache_cls, mock_stages
    ):
        """COMPLETE + str(dict) body must not call create_pending_entry."""
        cache_entry = SimpleNamespace(
            stellar_account="GABC",
            network_name="public",
            status="DONE_MAKE_PARENT_LINEAGE",
            cached_json="{'xlm_balance': 1.0}",
            last_fetched_at=None,
            created_at=None,
            updated_at=None,
        )
        helpers = MagicMock()
        helpers.check_cache_freshness.return_value = (False, cache_entry)
        helpers.create_pending_entry = MagicMock()
        mock_cache_cls.return_value = helpers

        svc = MagicMock()
        proj = {
            "account": "GABC",
            "network": "public",
            "lineage_path": ["GROOT", "GABC"],
            "nodes": {
                "GROOT": {
                    "stellar_account": "GROOT",
                    "stellar_creator_account": None,
                    "network_name": "public",
                    "xlm_balance": 0,
                    "assets": [],
                    "status": "COMPLETE",
                    "is_issuer": False,
                    "in_lineage_path": True,
                },
                "GABC": {
                    "stellar_account": "GABC",
                    "stellar_creator_account": "GROOT",
                    "network_name": "public",
                    "xlm_balance": 0,
                    "assets": [],
                    "status": "COMPLETE",
                    "is_issuer": False,
                    "in_lineage_path": True,
                },
            },
            "siblings_by_creator": {},
            "tree": {
                "name": "GROOT",
                "node_type": "ISSUER",
                "stellar_account": "GROOT",
                "children": [],
            },
            "meta": {"db_only": True},
        }
        svc.build_projection.return_value = proj
        svc.to_tree.return_value = proj["tree"]
        svc.to_table_rows.return_value = [
            {"stellar_account": "GROOT"},
            {"stellar_account": "GABC"},
        ]
        mock_svc_cls.return_value = svc

        with patch(
            "apiApp.helpers.sm_lineage_aggregate.maybe_rebuild_projection_on_complete",
            return_value=None,
        ):
            result = _search_ssr_via_unified_aggregate("GABC", "public")

        helpers.create_pending_entry.assert_not_called()
        mock_stages.assert_not_called()
        svc.build_projection.assert_called()
        self.assertTrue(result["is_fresh"])
        self.assertFalse(result["is_refreshing"])
        self.assertEqual(len(result["account_lineage_data"]), 2)
        self.assertEqual(result["genealogy_data"]["tree_data"]["name"], "GROOT")

    @override_settings(
        LINEAGE_UNIFIED_AGGREGATE=True,
        LINEAGE_WRITE_PROJECTION=False,
        LINEAGE_SSR_INCLUDE_SIBLINGS=False,
    )
    @patch("webApp.views.initialize_stage_executions")
    @patch("webApp.views.StellarMapCacheHelpers")
    @patch("apiApp.helpers.sm_lineage_aggregate.LineageAggregateService")
    def test_new_account_creates_pending(
        self, mock_svc_cls, mock_cache_cls, mock_stages
    ):
        helpers = MagicMock()
        helpers.check_cache_freshness.return_value = (False, None)
        pending_entry = SimpleNamespace(
            stellar_account="GNEW",
            network_name="public",
            status="PENDING",
            cached_json="",
            last_fetched_at=None,
            created_at=None,
            updated_at=None,
        )
        helpers.create_pending_entry.return_value = pending_entry
        mock_cache_cls.return_value = helpers

        svc = MagicMock()
        svc.build_projection.return_value = {
            "account": "GNEW",
            "network": "public",
            "lineage_path": [],
            "nodes": {},
            "siblings_by_creator": {},
            "tree": {"name": "GNEW", "node_type": "ISSUER", "children": []},
            "meta": {},
        }
        svc.to_tree.return_value = {"name": "GNEW", "node_type": "ISSUER", "children": []}
        svc.to_table_rows.return_value = []
        mock_svc_cls.return_value = svc

        result = _search_ssr_via_unified_aggregate("GNEW", "public")

        helpers.create_pending_entry.assert_called_once()
        mock_stages.assert_called_once()
        self.assertTrue(result["is_refreshing"])
        self.assertEqual(result["account_lineage_data"], [])

    @override_settings(LINEAGE_UNIFIED_AGGREGATE=True)
    @patch("webApp.views.StellarMapCacheHelpers")
    @patch("apiApp.helpers.sm_lineage_aggregate.LineageAggregateService")
    def test_fresh_projection_from_cache(self, mock_svc_cls, mock_cache_cls):
        tree = {"name": "GABC", "node_type": "ISSUER", "children": []}
        proj = {
            "schema_version": 1,
            "account": "GABC",
            "network": "public",
            "nodes": {"GABC": {"stellar_account": "GABC", "in_lineage_path": True}},
            "lineage_path": ["GABC"],
            "siblings_by_creator": {},
            "tree": tree,
            "meta": {"cached": True},
        }
        cache_entry = SimpleNamespace(
            stellar_account="GABC",
            network_name="public",
            status="DONE_MAKE_PARENT_LINEAGE",
            cached_json=json.dumps(proj),
            last_fetched_at=None,
            created_at=None,
            updated_at=None,
        )
        helpers = MagicMock()
        helpers.check_cache_freshness.return_value = (True, cache_entry)
        helpers.create_pending_entry = MagicMock()
        mock_cache_cls.return_value = helpers

        svc = MagicMock()
        svc.get_projection.return_value = proj
        svc.to_tree.return_value = tree
        svc.to_table_rows.return_value = [{"stellar_account": "GABC"}]
        mock_svc_cls.return_value = svc

        result = _search_ssr_via_unified_aggregate("GABC", "public")

        helpers.create_pending_entry.assert_not_called()
        svc.get_projection.assert_called()
        self.assertEqual(result["genealogy_data"]["tree_data"]["name"], "GABC")
        self.assertEqual(len(result["account_lineage_data"]), 1)


class SearchViewFlagRoutingTests(SimpleTestCase):
    """Ensure search_view chooses unified helper when flag is on."""

    @override_settings(LINEAGE_UNIFIED_AGGREGATE=True)
    @patch("webApp.views._search_ssr_via_unified_aggregate")
    def test_search_view_calls_unified(self, mock_unified):
        mock_unified.return_value = {
            "genealogy_data": {
                "account_genealogy_items": [],
                "tree_data": _skeleton_tree("GABC"),
            },
            "account_lineage_data": [{"stellar_account": "GABC"}],
            "is_fresh": False,
            "is_refreshing": True,
            "cache_entry": None,
            "meta": {},
        }

        from django.test import RequestFactory
        from webApp.views import search_view

        factory = RequestFactory()
        request = factory.get(
            "/search/",
            {
                "account": "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB",
                "network": "public",
            },
        )

        with patch("webApp.views.render") as mock_render:
            resp = MagicMock()
            resp.__setitem__ = MagicMock()
            mock_render.return_value = resp
            with patch(
                "webApp.views.StellarMapValidatorHelpers.validate_stellar_account_address",
                return_value=True,
            ):
                with patch("django.core.cache.cache") as mock_cache:
                    mock_cache.get.return_value = None
                    search_view(request)

        mock_unified.assert_called_once()
        self.assertTrue(mock_render.called)
        ctx = mock_render.call_args[0][2]
        self.assertTrue(ctx.get("lineage_unified_aggregate"))
        self.assertIn("tree_data", ctx)
        self.assertIn("account_lineage_data", ctx)
        self.assertEqual(ctx["account_lineage_data"][0]["stellar_account"], "GABC")
