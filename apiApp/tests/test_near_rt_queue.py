"""
Near-RT Phase 1: queue API, settings, worker guard under CASSANDRA_READ_ONLY.
"""
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import Client, SimpleTestCase, override_settings


class NearRtSettingsTests(SimpleTestCase):
    def test_near_rt_settings_present(self):
        from django.conf import settings

        self.assertTrue(hasattr(settings, 'NEAR_RT_ENABLED'))
        self.assertTrue(hasattr(settings, 'NEAR_RT_SEARCH_POLL_MS'))
        self.assertTrue(hasattr(settings, 'NEAR_RT_WORKER_INTERVAL_SEC'))
        self.assertTrue(hasattr(settings, 'NEAR_RT_WORKER_LIMIT'))


class QueueLineageApiTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=False)
        self.valid = 'GD6WU64OEP5C4LRBH6NK3MHYIA2ADN6K6II6EXPNVUR3ERBXT4AN4ACD'

    @override_settings(CASSANDRA_READ_ONLY=True)
    def test_queue_blocked_when_read_only(self):
        resp = self.client.post(
            '/api/queue-lineage/',
            {'account': self.valid, 'network': 'public'},
        )
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json().get('error'), 'read_only')

    @override_settings(CASSANDRA_READ_ONLY=False)
    def test_queue_rejects_invalid_account(self):
        resp = self.client.post(
            '/api/queue-lineage/',
            {'account': 'not-a-key', 'network': 'public'},
        )
        self.assertEqual(resp.status_code, 400)

    @override_settings(CASSANDRA_READ_ONLY=False)
    @patch('apiApp.views.initialize_stage_executions', create=True)
    @patch('apiApp.helpers.sm_stage_execution.initialize_stage_executions')
    @patch('apiApp.helpers.sm_cache.StellarMapCacheHelpers')
    def test_queue_success(self, mock_helpers_cls, mock_stages, _unused):
        mock_entry = MagicMock()
        mock_entry.status = 'PENDING'
        mock_helpers_cls.return_value.create_pending_entry.return_value = mock_entry

        resp = self.client.post(
            '/api/queue-lineage/',
            {'account': self.valid, 'network': 'public'},
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('account'), self.valid)
        mock_helpers_cls.return_value.create_pending_entry.assert_called_once()


class NearRtWorkerCommandTests(SimpleTestCase):
    @override_settings(CASSANDRA_READ_ONLY=True)
    def test_worker_refuses_read_only(self):
        out = StringIO()
        err = StringIO()
        call_command('run_sdk_near_rt_worker', '--once', stdout=out, stderr=err)
        self.assertIn('CASSANDRA_READ_ONLY', err.getvalue())

    @override_settings(CASSANDRA_READ_ONLY=False)
    @patch('apiApp.management.commands.run_sdk_near_rt_worker.call_command')
    def test_worker_once_calls_sdk_pipeline(self, mock_call):
        out = StringIO()
        call_command(
            'run_sdk_near_rt_worker',
            '--once',
            '--limit',
            '2',
            '--concurrent',
            '1',
            stdout=out,
        )
        mock_call.assert_called()
        args, kwargs = mock_call.call_args
        self.assertEqual(args[0], 'stellar_sdk_pipeline')
        self.assertEqual(kwargs.get('limit'), 2)


class SearchShellNearRtTests(SimpleTestCase):
    def test_search_template_has_queue_button_and_poll(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        html = (root / 'webApp/templates/webApp/search.html').read_text()
        self.assertIn('queueLineageRefresh', html)
        self.assertIn('search_poll_interval_ms', html)
        self.assertIn('/api/queue-lineage/', html)
