# StellarMapWeb/testrunner.py
"""
Custom Test Runner for StellarMapWeb.

Overrides DB setup/teardown for non-DB tests (e.g., unit tests without models).
Efficiency: Skips unnecessary DB ops for faster tests.
Security: Limits to non-DB contexts; document usage to avoid accidental skips.
"""

from django.test.runner import DiscoverRunner


class NoDbTestRunner(DiscoverRunner):
    """
    TestRunner subclass that skips test database creation/destruction.

    Useful for tests not requiring DB (e.g., pure unit tests).
    Caution: Use only for non-model tests; otherwise, use default runner.
    """

    def setup_databases(self, **kwargs):
        """Override: Skip test DB creation."""
        return []  # Return empty to indicate no DBs created

    def teardown_databases(self, old_config, **kwargs):
        """Override: Skip test DB destruction."""
        pass
