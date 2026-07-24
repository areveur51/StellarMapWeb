"""
PR2B: flag-gated write-time projection rebuild on pipeline complete.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apiApp.helpers.sm_lineage_aggregate import (
    maybe_rebuild_projection_on_complete,
    write_projection_enabled,
)


class WriteProjectionFlagTests(SimpleTestCase):
    @override_settings(LINEAGE_WRITE_PROJECTION=False)
    def test_flag_off(self):
        self.assertFalse(write_projection_enabled())

    @override_settings(LINEAGE_WRITE_PROJECTION=True)
    def test_flag_on(self):
        self.assertTrue(write_projection_enabled())


class MaybeRebuildTests(SimpleTestCase):
    @override_settings(LINEAGE_WRITE_PROJECTION=False)
    @patch("apiApp.helpers.sm_lineage_aggregate.LineageAggregateService")
    def test_noop_when_flag_off(self, mock_svc_cls):
        result = maybe_rebuild_projection_on_complete("GABC", "public")
        self.assertIsNone(result)
        mock_svc_cls.assert_not_called()

    @override_settings(LINEAGE_WRITE_PROJECTION=True)
    @patch("apiApp.helpers.sm_lineage_aggregate.LineageAggregateService")
    def test_calls_rebuild_when_flag_on(self, mock_svc_cls):
        mock_svc = MagicMock()
        mock_svc.rebuild_and_cache.return_value = {
            "schema_version": 1,
            "account": "GABC",
            "nodes": {},
        }
        mock_svc_cls.return_value = mock_svc

        result = maybe_rebuild_projection_on_complete(
            "GABC", "public", cache_status="DONE_MAKE_PARENT_LINEAGE"
        )

        self.assertIsNotNone(result)
        mock_svc.rebuild_and_cache.assert_called_once_with(
            "GABC",
            "public",
            cache_status="DONE_MAKE_PARENT_LINEAGE",
        )

    @override_settings(LINEAGE_WRITE_PROJECTION=True)
    @patch("apiApp.helpers.sm_lineage_aggregate.LineageAggregateService")
    def test_swallows_rebuild_errors(self, mock_svc_cls):
        mock_svc = MagicMock()
        mock_svc.rebuild_and_cache.side_effect = RuntimeError("db down")
        mock_svc_cls.return_value = mock_svc

        result = maybe_rebuild_projection_on_complete("GABC", "public")
        self.assertIsNone(result)


class PipelineHookSourceGuardTests(SimpleTestCase):
    """Call sites must invoke maybe_rebuild after complete (API, BQ, SDK)."""

    def test_api_pipeline_hooks_rebuild(self):
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[2]
            / "apiApp/management/commands/api_pipeline.py"
        ).read_text()
        self.assertIn("maybe_rebuild_projection_on_complete", text)

    def test_bigquery_pipeline_hooks_rebuild(self):
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[2]
            / "apiApp/management/commands/bigquery_pipeline.py"
        ).read_text()
        self.assertIn("maybe_rebuild_projection_on_complete", text)

    def test_sdk_pipeline_hooks_sync_and_rebuild(self):
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[2]
            / "apiApp/management/commands/stellar_sdk_pipeline.py"
        ).read_text()
        self.assertIn("maybe_rebuild_projection_on_complete", text)
        self.assertIn("sync_status_back_to_cache", text)
        # COMPLETE path should sync search cache
        self.assertIn("status='COMPLETE'", text)

    def test_cron_parent_lineage_uses_flag_branch(self):
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[2]
            / "apiApp/management/commands/cron_make_parent_account_lineage.py"
        ).read_text()
        self.assertIn("write_projection_enabled", text)
        self.assertIn("maybe_rebuild_projection_on_complete", text)
        # Legacy path still present when flag off
        self.assertIn("get_account_genealogy", text)


class UpdateCacheJsonOnlyTests(SimpleTestCase):
    @patch("apiApp.helpers.sm_cache.StellarAccountSearchCache.objects")
    def test_update_cache_rejects_python_repr_string(self, mock_objects):
        from apiApp.helpers.sm_cache import StellarMapCacheHelpers

        mock_objects.get.side_effect = Exception("not found")
        # DoesNotExist path — need real exception type
        from apiApp.model_loader import StellarAccountSearchCache

        mock_objects.get.side_effect = StellarAccountSearchCache.DoesNotExist
        mock_objects.create = MagicMock()

        helpers = StellarMapCacheHelpers()
        with self.assertRaises(ValueError):
            helpers.update_cache(
                "GABC",
                "public",
                "{'xlm_balance': 1.0}",  # invalid non-JSON body
            )

    @patch("apiApp.helpers.sm_cache.StellarAccountSearchCache.objects")
    def test_update_cache_accepts_dict_as_json(self, mock_objects):
        from apiApp.helpers.sm_cache import StellarMapCacheHelpers
        from apiApp.model_loader import StellarAccountSearchCache
        import json

        mock_objects.get.side_effect = StellarAccountSearchCache.DoesNotExist
        created = MagicMock()
        mock_objects.create.return_value = created

        helpers = StellarMapCacheHelpers()
        helpers.update_cache(
            "GABC",
            "public",
            {"schema_version": 1, "nodes": {}, "tree": {"name": "GABC", "children": []}},
        )

        args, kwargs = mock_objects.create.call_args
        body = kwargs.get("cached_json") or (
            args[0] if args else None
        )
        # create was called with cached_json=
        self.assertTrue(mock_objects.create.called)
        call_kwargs = mock_objects.create.call_args.kwargs
        parsed = json.loads(call_kwargs["cached_json"])
        self.assertEqual(parsed["schema_version"], 1)
