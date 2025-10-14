# apiApp/managers.py
import pandas as pd
import sentry_sdk
import uuid
from apiApp.helpers.sm_conn import CassandraConnectionsHelpers
from apiApp.helpers.sm_datetime import StellarMapDateTimeHelpers
from apiApp.models import StellarAccountSearchCache, StellarCreatorAccountLineage, ManagementCronHealth
from django.http import HttpRequest  # For mock requests
from django.conf import settings

# Environment-based database selection
ENV = settings.ENV if hasattr(settings, 'ENV') else 'development'


class StellarAccountSearchCacheManager:
    """
    Manager for StellarAccountSearchCache.

    Handles create/update with timestamps.
    """

    def get_queryset(self, **kwargs):
        """Filter queryset; return first or None."""
        try:
            return StellarAccountSearchCache.objects.filter(**kwargs).first()
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise

    def create_inquiry(self, request: HttpRequest):
        """Create inquiry with timestamp."""
        try:
            dt_helpers = StellarMapDateTimeHelpers()
            dt_helpers.set_datetime_obj()
            request.data['created_at'] = dt_helpers.get_datetime_obj()
            return StellarAccountSearchCache.objects.create(**request.data)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise

    def update_inquiry(self, stellar_account: str, network_name: str, status: str):
        """Update status by account and network."""
        try:
            inquiry = self.get_queryset(stellar_account=stellar_account, network_name=network_name)
            if inquiry:
                inquiry.status = status
                inquiry.save()
                return inquiry
            return None
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise


# Similar streamlining for StellarCreatorAccountLineageManager, ManagementCronHealthManager
# Example for ManagementCronHealthManager:
class ManagementCronHealthManager:

    def create_cron_health(self, request: HttpRequest):
        """Create health record with timestamp."""
        try:
            dt_helpers = StellarMapDateTimeHelpers()
            dt_helpers.set_datetime_obj()
            request.data['created_at'] = dt_helpers.get_datetime_obj()
            return ManagementCronHealth.objects.create(**request.data)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise

    def get_latest_cron_health(self, cron_name: str) -> pd.DataFrame:
        """Get latest health for cron; uses appropriate database based on environment."""
        try:
            if ENV == 'production':
                # Production: Use Cassandra CQL
                date_helpers = StellarMapDateTimeHelpers()
                date_helpers.set_datetime_obj()
                date_str = date_helpers.get_date_str()
                conn = CassandraConnectionsHelpers()
                cql = (
                    f"SELECT * FROM management_cron_health WHERE cron_name='{cron_name}' "
                    f"AND created_at >= '{date_str} 00:00:00' AND created_at <= '{date_str} 23:59:59' "
                    f"LIMIT 17 ALLOW FILTERING;")
                conn.set_cql_query(cql)
                rows = conn.execute_cql()
                df = pd.DataFrame(rows)
                conn.close_connection()  # Ensure close
            else:
                # Development: Use Django ORM with SQLite
                from datetime import datetime, time
                today = datetime.now().date()
                start_datetime = datetime.combine(today, time.min)
                end_datetime = datetime.combine(today, time.max)

                queryset = ManagementCronHealth.objects.filter(
                    cron_name=cron_name,
                    created_at__range=(start_datetime, end_datetime)
                ).order_by('-created_at')[:1]  # Get latest only

                if queryset.exists():
                    data = [{
                        'cron_name': obj.cron_name,
                        'status': obj.status,
                        'reason': obj.reason,
                        'created_at': obj.created_at
                    } for obj in queryset]
                    df = pd.DataFrame(data)
                else:
                    df = pd.DataFrame()

            if not df.empty:
                return df.sort_values('created_at', ascending=False).iloc[[0]]  # Latest only
            return pd.DataFrame()
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise

    # ... (get_distinct_cron_names similar; use set for uniques)


class StellarCreatorAccountLineageManager:
    """
    Manager for StellarCreatorAccountLineage.
    
    Handles creation and querying of account lineage data.
    """

    def get_queryset(self, **kwargs):
        """Filter queryset; return first or None."""
        try:
            return StellarCreatorAccountLineage.objects.filter(**kwargs).first()
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise

    def create_lineage(self, request: HttpRequest):
        """Create lineage record with timestamp."""
        try:
            dt_helpers = StellarMapDateTimeHelpers()
            dt_helpers.set_datetime_obj()
            request.data['created_at'] = dt_helpers.get_datetime_obj()
            return StellarCreatorAccountLineage.objects.create(**request.data)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise
    
    def update_status(self, id: uuid.UUID, status: str):
        """Update lineage record status by ID."""
        try:
            lineage = StellarCreatorAccountLineage.objects.filter(id=id).first()
            if lineage:
                lineage.status = status
                lineage.save()
                return lineage
            return None
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise
    
    async def async_update_status(self, id: uuid.UUID, status: str):
        """Async update lineage record status by ID."""
        try:
            lineage = StellarCreatorAccountLineage.objects.filter(id=id).first()
            if lineage:
                lineage.status = status
                lineage.save()
                return lineage
            return None
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise
    
    async def async_update_lineage(self, id: uuid.UUID, request: HttpRequest):
        """Async update lineage record with data from request."""
        try:
            lineage = StellarCreatorAccountLineage.objects.filter(id=id).first()
            if lineage:
                for key, value in request.data.items():
                    setattr(lineage, key, value)
                lineage.save()
                return lineage
            return None
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise

    def get_lineage_by_account(self, account_id: str) -> pd.DataFrame:
        """Get lineage data for account as DataFrame."""
        try:
            queryset = StellarCreatorAccountLineage.objects.filter(account_id=account_id)
            if queryset.exists():
                data = list(queryset.values())
                return pd.DataFrame(data)
            return pd.DataFrame()
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise
