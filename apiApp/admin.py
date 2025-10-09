from django.contrib import admin
from django.shortcuts import render
from django.utils.html import format_html
from apiApp.helpers.sm_conn import CassandraConnectionsHelpers
from .models import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    ManagementCronHealth,
    StellarAccountStageExecution,
    BigQueryPipelineConfig,
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


@admin.register(BigQueryPipelineConfig)
class BigQueryPipelineConfigAdmin(admin.ModelAdmin):
    """
    Admin interface for BigQuery Pipeline Configuration.
    
    This is a singleton configuration model - only one configuration record should exist.
    Controls all BigQuery pipeline behavior, cost limits, and API fallback settings.
    """
    
    # Allow editing for this model (unlike other Cassandra models)
    def has_add_permission(self, request):
        # Only allow adding if no configuration exists
        return not BigQueryPipelineConfig.objects.all().count()
    
    def has_delete_permission(self, request, obj=None):
        return False  # Never allow deleting the configuration
    
    def has_change_permission(self, request, obj=None):
        return True  # Allow editing
    
    # Organize fields into logical sections
    fieldsets = (
        ('📊 BigQuery Cost Controls', {
            'fields': ('bigquery_enabled', 'cost_limit_usd', 'size_limit_mb'),
            'description': format_html(
                '<div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px;margin:10px 0;">'
                '<strong>⚠️ COST PROTECTION:</strong> These settings prevent runaway BigQuery costs.<br>'
                '<strong>Current Limits:</strong><br>'
                '• Cost: $0.71 per query (processes ~145GB of data)<br>'
                '• Typical query cost: $0.18-0.35 for accounts with full lineage<br>'
                '• Queries exceeding limits automatically fall back to free APIs<br><br>'
                '<strong>💡 Examples:</strong><br>'
                '• <code>cost_limit_usd=0.71</code> → Allows $0.71 queries (RECOMMENDED)<br>'
                '• <code>cost_limit_usd=0.10</code> → Very restrictive, most queries blocked<br>'
                '• <code>cost_limit_usd=5.00</code> → Allows expensive historical queries<br>'
                '• <code>size_limit_mb=148900</code> → 145GB limit (RECOMMENDED)<br>'
                '</div>'
            )
        }),
        
        ('🔧 Pipeline Strategy', {
            'fields': ('pipeline_mode',),
            'description': format_html(
                '<div style="background:#d1ecf1;border-left:4px solid #17a2b8;padding:12px;margin:10px 0;">'
                '<strong>📋 PIPELINE MODES:</strong><br><br>'
                '<strong>1. BIGQUERY_WITH_API_FALLBACK</strong> (RECOMMENDED)<br>'
                '• Tries BigQuery first for fast, comprehensive data<br>'
                '• Falls back to Horizon/Stellar Expert APIs if cost blocked<br>'
                '• Best balance of speed and cost control<br><br>'
                '<strong>2. BIGQUERY_ONLY</strong><br>'
                '• Uses only BigQuery (no API fallback)<br>'
                '• Fails if query exceeds cost limits<br>'
                '• Use for batch processing with high cost limits<br><br>'
                '<strong>3. API_ONLY</strong><br>'
                '• Uses only Horizon/Stellar Expert APIs (no BigQuery)<br>'
                '• Slower but completely free<br>'
                '• Subject to API rate limits<br>'
                '</div>'
            )
        }),
        
        ('📅 Age Restrictions', {
            'fields': ('instant_query_max_age_days', 'cache_ttl_hours'),
            'description': format_html(
                '<div style="background:#d4edda;border-left:4px solid #28a745;padding:12px;margin:10px 0;">'
                '<strong>⏰ AGE-BASED QUERY OPTIMIZATION:</strong><br><br>'
                '<strong>instant_query_max_age_days (Default: 365)</strong><br>'
                '• Accounts younger than this: Instant BigQuery queries<br>'
                '• Accounts older than this with data: Use existing database records<br>'
                '• Accounts older than this without data: Queue for batch pipeline<br><br>'
                '<strong>💡 Why?</strong> Old accounts (5-10 years) generate EXPENSIVE queries ($8-15)<br>'
                '• Setting to 365 days prevents costly historical queries<br>'
                '• Existing data is reused (no BigQuery cost)<br><br>'
                '<strong>cache_ttl_hours (Default: 12)</strong><br>'
                '• How long data is considered fresh before refresh<br>'
                '• Lower = more frequent updates, higher BigQuery costs<br>'
                '• Higher = less frequent updates, lower BigQuery costs<br>'
                '</div>'
            )
        }),
        
        ('🔌 API Fallback Settings', {
            'fields': ('api_fallback_enabled', 'horizon_max_operations', 'horizon_child_max_pages'),
            'description': format_html(
                '<div style="background:#f8d7da;border-left:4px solid #dc3545;padding:12px;margin:10px 0;">'
                '<strong>🚨 API FALLBACK BEHAVIOR:</strong><br><br>'
                '<strong>api_fallback_enabled</strong><br>'
                '• If TRUE: Falls back to APIs when BigQuery blocked by cost controls<br>'
                '• If FALSE: Pipeline fails when BigQuery blocked (not recommended)<br><br>'
                '<strong>horizon_max_operations (Default: 200)</strong><br>'
                '• Max Horizon operations to fetch for creator discovery<br>'
                '• Higher = more comprehensive but slower<br>'
                '• 200 operations covers 99% of accounts<br><br>'
                '<strong>horizon_child_max_pages (Default: 5)</strong><br>'
                '• Max pages (200 ops each) to fetch for child account discovery<br>'
                '• 5 pages = 1000 operations scanned<br>'
                '• Increase if accounts have many children (high-fanout)<br>'
                '</div>'
            )
        }),
        
        ('👶 Child Account Collection', {
            'fields': ('bigquery_max_children', 'bigquery_child_page_size'),
            'description': format_html(
                '<div style="background:#e2e3e5;border-left:4px solid #6c757d;padding:12px;margin:10px 0;">'
                '<strong>🔗 CHILD ACCOUNT DISCOVERY:</strong><br><br>'
                '<strong>bigquery_max_children (Default: 100,000)</strong><br>'
                '• Maximum child accounts to discover per parent via BigQuery<br>'
                '• Prevents massive queries for high-fanout accounts<br>'
                '• 100K is sufficient for 99.9% of accounts<br><br>'
                '<strong>bigquery_child_page_size (Default: 10,000)</strong><br>'
                '• Pagination size for child account queries<br>'
                '• Larger = fewer queries but higher memory usage<br>'
                '• 10K balances performance and resource usage<br>'
                '</div>'
            )
        }),
        
        ('⚙️ Batch Processing', {
            'fields': ('batch_processing_enabled', 'batch_size'),
            'description': format_html(
                '<div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px;margin:10px 0;">'
                '<strong>📦 BATCH PROCESSING OPTIONS:</strong><br><br>'
                '<strong>batch_processing_enabled</strong><br>'
                '• Controls whether cron job processes PENDING accounts<br>'
                '• Disable to manually control when pipeline runs<br><br>'
                '<strong>batch_size (Default: 100)</strong><br>'
                '• Number of accounts to process per batch run<br>'
                '• Lower = slower but safer (less cost per run)<br>'
                '• Higher = faster but uses more BigQuery quota<br><br>'
                '<strong>💡 Cost Calculation:</strong><br>'
                '• batch_size=100 at $0.35/account = ~$35 per batch<br>'
                '• batch_size=10 at $0.35/account = ~$3.50 per batch<br>'
                '</div>'
            )
        }),
        
        ('📝 Metadata', {
            'fields': ('updated_by', 'notes', 'created_at', 'updated_at'),
            'description': format_html(
                '<div style="background:#d1ecf1;border-left:4px solid #17a2b8;padding:12px;margin:10px 0;">'
                '<strong>📄 CONFIGURATION TRACKING:</strong><br><br>'
                '<strong>updated_by:</strong> Username of admin who last modified settings<br>'
                '<strong>notes:</strong> Document why changes were made<br>'
                '<strong>Timestamps:</strong> Auto-updated on save<br>'
                '</div>'
            )
        }),
    )
    
    list_display = ('config_summary', 'cost_limit_display', 'pipeline_mode', 'updated_at', 'updated_by')
    readonly_fields = ('created_at', 'updated_at')
    
    ordering = ()  # Cassandra doesn't support ordering
    show_full_result_count = False  # Cassandra optimization
    
    def config_summary(self, obj):
        """Display configuration status summary."""
        if obj.bigquery_enabled:
            return format_html('<span style="color:green">✓ BigQuery Enabled</span>')
        else:
            return format_html('<span style="color:red">✗ BigQuery Disabled</span>')
    config_summary.short_description = 'Status'
    
    def cost_limit_display(self, obj):
        """Display cost limit with color coding."""
        if obj.cost_limit_usd >= 1.0:
            color = 'red'
        elif obj.cost_limit_usd >= 0.50:
            color = 'orange'
        else:
            color = 'green'
        
        # Pre-format numeric values to avoid SafeString format code errors
        cost_str = f'${obj.cost_limit_usd:.2f}'
        size_gb_str = f'{obj.size_limit_mb / 1024:.0f} GB'
        
        return format_html(
            '<span style="color:{}"><strong>{}</strong> / <small>{}</small></span>',
            color,
            cost_str,
            size_gb_str
        )
    cost_limit_display.short_description = 'Cost Limit'
    
    def save_model(self, request, obj, form, change):
        """Auto-populate updated_by field with current user."""
        obj.updated_by = request.user.username
        super().save_model(request, obj, form, change)
    
    def changelist_view(self, request, extra_context=None):
        """Override to show single config or creation form."""
        try:
            config_exists = BigQueryPipelineConfig.objects.filter(config_id='default').exists()
            
            if not config_exists:
                # Redirect to add form if no config exists
                from django.shortcuts import redirect
                from django.urls import reverse
                return redirect(reverse('admin:apiApp_bigquerypipelineconfig_add'))
        except:
            pass
        
        return super().changelist_view(request, extra_context=extra_context)
