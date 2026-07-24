"""
Unit tests for CASSANDRA_READ_ONLY lab wiring (settings + cache guards).

Does not require a live Astra connection — only flag/helper behavior.
"""
from django.test import SimpleTestCase, override_settings


class CassandraReadOnlyFlagTests(SimpleTestCase):
    def test_sm_cache_create_pending_skips_when_ro(self):
        from apiApp.helpers import sm_cache as sm_cache_mod

        with override_settings(CASSANDRA_READ_ONLY=True):
            # DoesNotExist path → None without writing
            class _DoesNotExist(Exception):
                pass

            class FakeQS:
                DoesNotExist = _DoesNotExist

                def get(self, **kwargs):
                    raise _DoesNotExist()

            class FakeModel:
                objects = FakeQS()
                DoesNotExist = _DoesNotExist

            original = sm_cache_mod.StellarAccountSearchCache
            try:
                sm_cache_mod.StellarAccountSearchCache = FakeModel
                helpers = sm_cache_mod.StellarMapCacheHelpers()
                result = helpers.create_pending_entry("G" + "A" * 55, "public")
                self.assertIsNone(result)
            finally:
                sm_cache_mod.StellarAccountSearchCache = original

    def test_guard_raises_permission_error(self):
        from apiApp import models_cassandra as mc

        with override_settings(CASSANDRA_READ_ONLY=True):
            with self.assertRaises(PermissionError):
                mc._guard_cassandra_write("TestModel")

    def test_guard_allows_when_not_ro(self):
        from apiApp import models_cassandra as mc

        with override_settings(CASSANDRA_READ_ONLY=False):
            mc._guard_cassandra_write("TestModel")  # no raise
