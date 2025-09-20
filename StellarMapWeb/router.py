# StellarMapWeb/router.py
"""
Database Router for StellarMapWeb.

Routes models to specific DBs based on app_label via DATABASE_APPS_MAPPING.
Efficiency: Simple lookups; allows relations within same DB.
Security: Prevents cross-DB relations to avoid data leaks/inconsistencies.
Documentation: Methods include docstrings with behavior notes.
"""

from django.conf import settings


class DatabaseAppsRouter:
    """
    Router directing DB operations by app_label.

    Uses settings.DATABASE_APPS_MAPPING (dict: app_label -> db_alias).
    Fallback to 'default' if not mapped.
    """

    def db_for_read(self, model, **hints):
        """Determine read DB for model."""
        return self._get_db_for_app(model._meta.app_label)

    def db_for_write(self, model, **hints):
        """Determine write DB for model."""
        return self._get_db_for_app(model._meta.app_label)

    def _get_db_for_app(self, app_label):
        """Helper: Get DB from mapping or None."""
        return settings.DATABASE_APPS_MAPPING.get(app_label)

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations if objects in same DB."""
        db1 = self._get_db_for_app(obj1._meta.app_label)
        db2 = self._get_db_for_app(obj2._meta.app_label)
        if db1 and db2:
            return db1 == db2
        return None  # Undecided; let other routers decide

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Allow migrations on DB if app mapped to it.
        Security: Restricts migrations to intended DBs.
        """
        mapped_db = self._get_db_for_app(app_label)
        if mapped_db:
            return db == mapped_db
        if db == 'default':
            return mapped_db is None  # Allow on default if not mapped
        return False  # Deny on other DBs
