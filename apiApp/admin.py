from django.contrib import admin
from django.shortcuts import render
from apiApp.helpers.sm_conn import CassandraConnectionsHelpers
from .models import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    ManagementCronHealth,
    StellarAccountStageExecution,
)


class CassandraAdminMixin:
    """Mixin to handle Cassandra-specific admin functionality - READ ONLY."""
    
    def changelist_view(self, request, extra_context=None):
        """Override changelist view to use raw CQL queries via CassandraConnectionsHelpers."""
        try:
            conn_helpers = CassandraConnectionsHelpers()
            cql_query = f"SELECT * FROM {self.get_table_name()} LIMIT 100 ALLOW FILTERING;"
            
            conn_helpers.set_cql_query(cql_query)
            rows = conn_helpers.execute_cql()
            
            # Convert rows to list of dictionaries
            results = []
            column_names = []
            for row in rows:
                row_dict = dict(row._asdict())
                results.append(row_dict)
                if not column_names and row_dict:
                    column_names = list(row_dict.keys())
            
            conn_helpers.close_connection()
            
            context = {
                'title': f'Select {self.model._meta.verbose_name}',
                'results': results,
                'column_names': column_names,
                'opts': self.model._meta,
                'has_add_permission': False,
                'app_label': self.model._meta.app_label,
                'cl': None,
            }
            
            if extra_context:
                context.update(extra_context)
            
            return render(request, 'admin/cassandra_changelist.html', context)
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            
            context = {
                'title': f'Select {self.model._meta.verbose_name}',
                'error': str(e),
                'error_detail': error_detail,
                'opts': self.model._meta,
                'app_label': self.model._meta.app_label,
            }
            return render(request, 'admin/cassandra_error.html', context)
    
    def get_table_name(self):
        """Get the Cassandra table name for this model."""
        raise NotImplementedError("Subclasses must implement get_table_name()")
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(StellarAccountSearchCache)
class StellarAccountSearchCacheAdmin(CassandraAdminMixin, admin.ModelAdmin):
    list_display = ('stellar_account', 'network_name', 'status')
    
    def get_table_name(self):
        return 'stellar_account_search_cache'


@admin.register(StellarCreatorAccountLineage)
class StellarCreatorAccountLineageAdmin(CassandraAdminMixin, admin.ModelAdmin):
    list_display = ('stellar_account', 'network_name', 'stellar_creator_account')
    
    def get_table_name(self):
        return 'stellar_creator_account_lineage'


@admin.register(ManagementCronHealth)
class ManagementCronHealthAdmin(CassandraAdminMixin, admin.ModelAdmin):
    list_display = ('cron_name', 'status', 'created_at')
    
    def get_table_name(self):
        return 'management_cron_health'


@admin.register(StellarAccountStageExecution)
class StellarAccountStageExecutionAdmin(CassandraAdminMixin, admin.ModelAdmin):
    list_display = ('stellar_account', 'network_name', 'stage_number', 'status')
    
    def get_table_name(self):
        return 'stellar_account_stage_execution'
