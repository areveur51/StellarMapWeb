"""
Regression: QueueSynchronizer.sync_status_back_to_cache must never leave
non-JSON in cached_json (PR2A — unconditional cache clobber stop).

Historical bug: callers passed a summary dict which was stored as str(dict)
(Python repr). That broke json.loads and could re-PENDING COMPLETE accounts.
"""
import json
from datetime import datetime
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apiApp.helpers.queue_sync import QueueSynchronizer


class QueueSyncStatusOnlyTests(SimpleTestCase):
    """Unit tests with mocked Search Cache ORM."""

    def setUp(self):
        self.account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        self.network = "public"
        self.tree_json = json.dumps({
            "name": self.account,
            "node_type": "ISSUER",
            "children": [],
        })
        self.fetched_at = datetime(2026, 1, 15, 12, 0, 0)

    def _mock_cache_record(self, status="IN_PROGRESS_MAKE_PARENT_LINEAGE"):
        record = Mock()
        record.stellar_account = self.account
        record.network_name = self.network
        record.status = status
        record.cached_json = self.tree_json
        record.last_fetched_at = self.fetched_at
        record.updated_at = datetime(2026, 1, 14, 0, 0, 0)
        record.save = Mock()
        return record

    @patch("apiApp.helpers.queue_sync.StellarAccountSearchCache.objects")
    def test_complete_sync_preserves_valid_tree_json(self, mock_objects):
        """Complete pipeline sync must leave valid JSON tree body intact."""
        cache_record = self._mock_cache_record()
        mock_objects.filter.return_value.first.return_value = cache_record

        ok = QueueSynchronizer.sync_status_back_to_cache(
            stellar_account=self.account,
            network_name=self.network,
            status="API_COMPLETE",
        )

        self.assertTrue(ok)
        self.assertEqual(cache_record.status, "DONE_MAKE_PARENT_LINEAGE")
        self.assertEqual(cache_record.cached_json, self.tree_json)
        # Must still be parseable JSON (not Python repr)
        parsed = json.loads(cache_record.cached_json)
        self.assertEqual(parsed["name"], self.account)
        self.assertEqual(cache_record.last_fetched_at, self.fetched_at)
        cache_record.save.assert_called()

    @patch("apiApp.helpers.queue_sync.StellarAccountSearchCache.objects")
    def test_complete_sync_never_writes_str_dict_repr(self, mock_objects):
        """Deprecated cached_json summary must not be written as str(dict)."""
        cache_record = self._mock_cache_record()
        mock_objects.filter.return_value.first.return_value = cache_record

        summary = {
            "xlm_balance": 12.5,
            "creator_account": "GCREATOR",
            "home_domain": "example.com",
            "pipeline_source": "API",
        }

        ok = QueueSynchronizer.sync_status_back_to_cache(
            stellar_account=self.account,
            network_name=self.network,
            status="BIGQUERY_COMPLETE",
            cached_json=summary,
        )

        self.assertTrue(ok)
        body = cache_record.cached_json
        self.assertNotEqual(body, str(summary))
        self.assertFalse(body.startswith("{'") or body.startswith("{'xlm"))
        # Prior tree preserved
        self.assertEqual(body, self.tree_json)
        json.loads(body)  # must not raise
        self.assertEqual(cache_record.status, "DONE_MAKE_PARENT_LINEAGE")
        self.assertEqual(cache_record.last_fetched_at, self.fetched_at)

    @patch("apiApp.helpers.queue_sync.StellarAccountSearchCache.objects")
    def test_status_only_does_not_set_last_fetched_at(self, mock_objects):
        """Status ticks must not pretend a full payload was written."""
        cache_record = self._mock_cache_record()
        cache_record.last_fetched_at = None
        mock_objects.filter.return_value.first.return_value = cache_record

        QueueSynchronizer.sync_status_back_to_cache(
            stellar_account=self.account,
            network_name=self.network,
            status="PROCESSING",
        )

        self.assertIsNone(cache_record.last_fetched_at)
        self.assertEqual(cache_record.status, "IN_PROGRESS_MAKE_PARENT_LINEAGE")
        # Empty/null body must stay empty — never invent non-JSON
        self.assertEqual(cache_record.cached_json, self.tree_json)

    @patch("apiApp.helpers.queue_sync.StellarAccountSearchCache.objects")
    def test_empty_body_stays_empty_not_python_repr(self, mock_objects):
        """If there was no tree yet, do not invent a str(dict) body."""
        cache_record = self._mock_cache_record()
        cache_record.cached_json = None
        mock_objects.filter.return_value.first.return_value = cache_record

        ok = QueueSynchronizer.sync_status_back_to_cache(
            stellar_account=self.account,
            network_name=self.network,
            status="API_COMPLETE",
            cached_json={"xlm_balance": 1.0},
        )

        self.assertTrue(ok)
        self.assertIsNone(cache_record.cached_json)
        self.assertEqual(cache_record.status, "DONE_MAKE_PARENT_LINEAGE")

    @patch("apiApp.helpers.queue_sync.StellarAccountSearchCache.objects")
    def test_no_cache_record_returns_false(self, mock_objects):
        mock_objects.filter.return_value.first.return_value = None

        ok = QueueSynchronizer.sync_status_back_to_cache(
            stellar_account=self.account,
            network_name=self.network,
            status="API_COMPLETE",
        )

        self.assertFalse(ok)

    @patch("apiApp.helpers.queue_sync.StellarAccountSearchCache.objects")
    def test_sdk_complete_maps_to_done(self, mock_objects):
        cache_record = self._mock_cache_record()
        mock_objects.filter.return_value.first.return_value = cache_record

        ok = QueueSynchronizer.sync_status_back_to_cache(
            stellar_account=self.account,
            network_name=self.network,
            status="COMPLETE",
        )

        self.assertTrue(ok)
        self.assertEqual(cache_record.status, "DONE_MAKE_PARENT_LINEAGE")
        self.assertEqual(cache_record.cached_json, self.tree_json)

    def test_pipeline_call_sites_do_not_pass_cached_json_summary(self):
        """
        Source guard: completion hooks must not pass summary dicts.
        (Callers cleaned in PR2A; method still ignores if something passes one.)
        """
        from pathlib import Path

        app_root = Path(__file__).resolve().parents[2]
        for rel in (
            "apiApp/management/commands/api_pipeline.py",
            "apiApp/management/commands/bigquery_pipeline.py",
        ):
            text = (app_root / rel).read_text()
            # Fail if a sync_status_back_to_cache call still passes cached_json=
            # (simple heuristic: cached_json= within 20 lines after sync call)
            idx = 0
            while True:
                pos = text.find("sync_status_back_to_cache", idx)
                if pos < 0:
                    break
                window = text[pos : pos + 400]
                self.assertNotIn(
                    "cached_json=",
                    window,
                    msg=f"{rel} still passes cached_json= near sync_status_back_to_cache",
                )
                idx = pos + 1
