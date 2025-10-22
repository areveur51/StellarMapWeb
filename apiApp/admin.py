from django.contrib import admin
from django.contrib.admin import helpers as admin_helpers
from django.shortcuts import render
from django.utils.html import format_html
from django.conf import settings
from django.contrib import messages
from .models import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    ManagementCronHealth,
    StellarAccountStageExecution,
    BigQueryPipelineConfig,
    SchedulerConfig,
)
from .helpers.sm_conn import CassandraConnectionsHelpers
from .helpers.sm_enrichment import StellarMapEnrichmentHelper

# Import SchedulerConfig admin registration
from .admin_scheduler import SchedulerConfigAdmin

# Environment-based admin selection
ENV = settings.ENV if hasattr(settings, 'ENV') else 'development'
USE_CASSANDRA_ADMIN = (ENV in ['production', 'replit'])


class CassandraAdminMixin:
    """Mixin to handle Cassandra-specific admin functionality with action support."""
    
    def changelist_view(self, request, extra_context=None):
        """
        Override changelist view to use raw CQL queries via CassandraConnectionsHelpers.
        
        Supports POST actions (e.g., refresh_enrichment_data) by detecting POST requests
        and calling the action handler before rendering.
        """
        
        # ============================================================
        # STEP 1: Handle POST actions (e.g., refresh_enrichment_data)
        # ============================================================
        if request.method == 'POST' and 'action' in request.POST:
            # Get the action name
            action = request.POST.get('action')
            
            # Get selected items (checkbox IDs from admin form)
            selected = request.POST.getlist(admin_helpers.ACTION_CHECKBOX_NAME)
            
            # Find the action method
            if hasattr(self, action) and action in [a for a, _ in self.get_actions(request).items()]:
                # Build a queryset from selected items by fetching actual Django model instances
                queryset = []
                
                for item_id in selected:
                    # item_id is in format "account|network" (composite key)
                    try:
                        parts = item_id.split('|')
                        if len(parts) == 2:
                            account, network = parts
                            
                            # Fetch the actual Django model instance using Cassandra ORM
                            try:
                                # Query the model directly using the ORM
                                obj = self.model.objects.filter(
                                    stellar_account=account,
                                    network_name=network
                                ).first()
                                
                                if obj:
                                    queryset.append(obj)
                            except Exception as e:
                                # If ORM query fails, log but continue
                                import traceback
                                self.message_user(
                                    request,
                                    f"Error fetching account {account}: {str(e)}",
                                    level=messages.ERROR
                                )
                    except Exception as e:
                        pass
                
                # Call the action with the queryset
                if queryset:
                    action_method = getattr(self, action)
                    response = action_method(request, queryset)
                    
                    # If the action returns a response (e.g., file download), return it
                    if response:
                        return response
                    
                    # Otherwise, redirect back to changelist
                    from django.http import HttpResponseRedirect
                    return HttpResponseRedirect(request.path)
        
        # ============================================================
        # STEP 2: Render normal changelist view
        # ============================================================
        try:
            conn_helpers = CassandraConnectionsHelpers()
            cql_query = f"SELECT * FROM {self.get_table_name()} LIMIT 100 ALLOW FILTERING;"
            
            conn_helpers.set_cql_query(cql_query)
            rows = conn_helpers.execute_cql()
            
            # Convert rows to list of dictionaries and process through display methods
            results = []
            processed_rows = []
            for row in rows:
                row_dict = dict(row._asdict())
                results.append(row_dict)
            
            # Get column headers and processed row data
            column_names = []
            combined_rows = []  # List of (processed_row, raw_row) tuples
            if self.list_display:
                for display_field in self.list_display:
                    # Get the display method or field
                    if hasattr(self, display_field):
                        method = getattr(self, display_field)
                        # Use the short_description if available, otherwise use the field name
                        if hasattr(method, 'short_description'):
                            column_names.append(method.short_description)
                        else:
                            column_names.append(display_field.replace('_', ' ').title())
                    else:
                        column_names.append(display_field.replace('_', ' ').title())
                
                # Process each row through the display methods
                for row_dict in results:
                    processed_row = []
                    for display_field in self.list_display:
                        if hasattr(self, display_field):
                            # Call the display method with the row dict
                            method = getattr(self, display_field)
                            value = method(row_dict)
                        else:
                            # Just get the raw value
                            value = row_dict.get(display_field, '')
                        processed_row.append(value)
                    processed_rows.append(processed_row)
                    combined_rows.append((processed_row, row_dict))
            
            conn_helpers.close_connection()
            
            # Build action choices for the dropdown
            action_choices = []
            if hasattr(self, 'actions'):
                for action in self.actions:
                    if hasattr(self, action):
                        action_method = getattr(self, action)
                        description = getattr(action_method, 'short_description', action.replace('_', ' ').title())
                        action_choices.append((action, description))
            
            context = {
                'title': f'Select {self.model._meta.verbose_name}',
                'results': processed_rows,
                'raw_results': results,  # For checkbox values
                'combined_rows': combined_rows,  # List of (processed_row, raw_row) tuples
                'column_names': column_names,
                'opts': self.model._meta,
                'has_add_permission': False,
                'app_label': self.model._meta.app_label,
                'cl': None,
                'action_choices': action_choices,
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


if USE_CASSANDRA_ADMIN:
    # Production mode: Use Cassandra admin with read-only functionality
    @admin.register(StellarAccountSearchCache)
    class StellarAccountSearchCacheAdmin(CassandraAdminMixin, admin.ModelAdmin):
        list_display = ('stellar_account_link', 'network_name', 'status')

        def stellar_account_link(self, obj):
            """Display stellar_account as clickable link to search page."""
            account = obj.get('stellar_account', '') if isinstance(obj, dict) else getattr(obj, 'stellar_account', '')
            network = obj.get('network_name', 'public') if isinstance(obj, dict) else getattr(obj, 'network_name', 'public')
            url = f"/search/?account={account}&network={network}"
            return format_html('<a href="{}" target="_blank" title="{}">{}</a>', url, account, account[:8] + '...' + account[-8:] if len(account) > 20 else account)
        stellar_account_link.short_description = 'Stellar Account'

        def get_table_name(self):
            return 'stellar_account_search_cache'

    @admin.register(StellarCreatorAccountLineage)
    class StellarCreatorAccountLineageAdmin(CassandraAdminMixin, admin.ModelAdmin):
        list_display = ('stellar_account_link', 'network_name', 'creator_account_link', 'xlm_balance', 'is_hva', 'tags', 'status', 'refresh_action')
        actions = ['refresh_enrichment_data']

        def stellar_account_link(self, obj):
            """Display stellar_account as clickable link to search page."""
            account = obj.get('stellar_account', '') if isinstance(obj, dict) else getattr(obj, 'stellar_account', '')
            network = obj.get('network_name', 'public') if isinstance(obj, dict) else getattr(obj, 'network_name', 'public')
            url = f"/search/?account={account}&network={network}"
            return format_html('<a href="{}" target="_blank" title="{}">{}</a>', url, account, account[:8] + '...' + account[-8:] if len(account) > 20 else account)
        stellar_account_link.short_description = 'Stellar Account'

        def creator_account_link(self, obj):
            """Display stellar_creator_account as clickable link to search page."""
            creator = obj.get('stellar_creator_account', '') if isinstance(obj, dict) else getattr(obj, 'stellar_creator_account', '')
            if not creator:
                return '-'
            network = obj.get('network_name', 'public') if isinstance(obj, dict) else getattr(obj, 'network_name', 'public')
            url = f"/search/?account={creator}&network={network}"
            return format_html('<a href="{}" target="_blank" title="{}">{}</a>', url, creator, creator[:8] + '...' + creator[-8:] if len(creator) > 20 else creator)
        creator_account_link.short_description = 'Creator Account'

        def refresh_action(self, obj):
            """Display refresh link for manual enrichment refresh."""
            account = obj.get('stellar_account', '') if isinstance(obj, dict) else getattr(obj, 'stellar_account', '')
            network = obj.get('network_name', 'public') if isinstance(obj, dict) else getattr(obj, 'network_name', 'public')
            account_id = obj.get('id', '') if isinstance(obj, dict) else getattr(obj, 'id', '')
            return format_html('<a href="#" onclick="alert(\'Cassandra admin is read-only. Use the action dropdown to refresh selected accounts.\'); return false;">Refresh</a>')
        refresh_action.short_description = 'Actions'

        def refresh_enrichment_data(self, request, queryset):
            """
            Admin action to refresh enrichment data for selected accounts.
            
            Note: For Cassandra, we need to re-query the accounts since queryset is dict-based.
            """
            success_count = 0
            error_count = 0
            
            for row in queryset:
                try:
                    account = row.get('stellar_account', '') if isinstance(row, dict) else row.stellar_account
                    network = row.get('network_name', 'public') if isinstance(row, dict) else row.network_name
                    
                    # Fetch the actual object from Cassandra
                    account_obj = StellarCreatorAccountLineage.objects.filter(
                        stellar_account=account,
                        network_name=network
                    ).first()
                    
                    if account_obj:
                        result = StellarMapEnrichmentHelper.refresh_account_enrichment(
                            account_obj, network_name=network
                        )
                        
                        if result['success']:
                            success_count += 1
                        else:
                            error_count += 1
                            self.message_user(request, f"Error refreshing {account}: {result.get('error', 'Unknown error')}", level=messages.ERROR)
                    else:
                        error_count += 1
                        self.message_user(request, f"Could not find account {account} in database", level=messages.ERROR)
                        
                except Exception as e:
                    error_count += 1
                    self.message_user(request, f"Error refreshing account: {str(e)}", level=messages.ERROR)
            
            if success_count > 0:
                self.message_user(request, f"Successfully refreshed enrichment data for {success_count} account(s)", level=messages.SUCCESS)
            if error_count > 0:
                self.message_user(request, f"Failed to refresh {error_count} account(s)", level=messages.WARNING)
        
        refresh_enrichment_data.short_description = "Refresh Enrichment Data (balance, home_domain, flags, assets)"

        def get_table_name(self):
            return 'stellar_creator_account_lineage'

    @admin.register(ManagementCronHealth)
    class ManagementCronHealthAdmin(CassandraAdminMixin, admin.ModelAdmin):
        list_display = ('cron_name', 'status', 'created_at')

        def get_table_name(self):
            return 'management_cron_health'

    @admin.register(StellarAccountStageExecution)
    class StellarAccountStageExecutionAdmin(CassandraAdminMixin, admin.ModelAdmin):
        list_display = ('stellar_account_link', 'network_name', 'stage_number', 'status')

        def stellar_account_link(self, obj):
            """Display stellar_account as clickable link to search page."""
            account = obj.get('stellar_account', '') if isinstance(obj, dict) else getattr(obj, 'stellar_account', '')
            network = obj.get('network_name', 'public') if isinstance(obj, dict) else getattr(obj, 'network_name', 'public')
            url = f"/search/?account={account}&network={network}"
            return format_html('<a href="{}" target="_blank" title="{}">{}</a>', url, account, account[:8] + '...' + account[-8:] if len(account) > 20 else account)
        stellar_account_link.short_description = 'Stellar Account'

        def get_table_name(self):
            return 'stellar_account_stage_execution'

else:
    # Local development mode: Use standard Django admin with full CRUD
    @admin.register(StellarAccountSearchCache)
    class StellarAccountSearchCacheAdmin(admin.ModelAdmin):
        list_display = ('stellar_account_link', 'network_name', 'status', 'last_fetched_at', 'retry_count')
        list_filter = ('network_name', 'status')
        search_fields = ('stellar_account',)
        readonly_fields = ('created_at', 'updated_at')

        def stellar_account_link(self, obj):
            """Display stellar_account as clickable link to search page."""
            account = obj.stellar_account
            network = obj.network_name
            url = f"/search/?account={account}&network={network}"
            return format_html('<a href="{}" target="_blank" title="{}">{}</a>', url, account, account[:8] + '...' + account[-8:] if len(account) > 20 else account)
        stellar_account_link.short_description = 'Stellar Account'

    @admin.register(StellarCreatorAccountLineage)
    class StellarCreatorAccountLineageAdmin(admin.ModelAdmin):
        list_display = ('stellar_account_link', 'network_name', 'creator_account_link', 'xlm_balance', 'is_hva', 'status')
        list_filter = ('network_name', 'status', 'is_hva')
        search_fields = ('stellar_account', 'stellar_creator_account')
        readonly_fields = ('created_at', 'updated_at')
        actions = ['refresh_enrichment_data']

        def stellar_account_link(self, obj):
            """Display stellar_account as clickable link to search page."""
            account = obj.stellar_account
            network = obj.network_name
            url = f"/search/?account={account}&network={network}"
            return format_html('<a href="{}" target="_blank" title="{}">{}</a>', url, account, account[:8] + '...' + account[-8:] if len(account) > 20 else account)
        stellar_account_link.short_description = 'Stellar Account'

        def creator_account_link(self, obj):
            """Display stellar_creator_account as clickable link to search page."""
            if not obj.stellar_creator_account:
                return '-'
            creator = obj.stellar_creator_account
            network = obj.network_name
            url = f"/search/?account={creator}&network={network}"
            return format_html('<a href="{}" target="_blank" title="{}">{}</a>', url, creator, creator[:8] + '...' + creator[-8:] if len(creator) > 20 else creator)
        creator_account_link.short_description = 'Creator Account'

        def refresh_enrichment_data(self, request, queryset):
            """
            Admin action to refresh enrichment data for selected accounts.
            
            Fetches fresh data from Horizon API (balance, home_domain, flags) and
            Stellar Expert API (assets, trustlines).
            """
            success_count = 0
            error_count = 0
            
            for account_obj in queryset:
                try:
                    result = StellarMapEnrichmentHelper.refresh_account_enrichment(
                        account_obj, network_name=account_obj.network_name
                    )
                    
                    if result['success']:
                        success_count += 1
                    else:
                        error_count += 1
                        self.message_user(
                            request,
                            f"Error refreshing {account_obj.stellar_account}: {result.get('error', 'Unknown error')}",
                            level=messages.ERROR
                        )
                        
                except Exception as e:
                    error_count += 1
                    self.message_user(
                        request,
                        f"Error refreshing {account_obj.stellar_account}: {str(e)}",
                        level=messages.ERROR
                    )
            
            if success_count > 0:
                self.message_user(
                    request,
                    f"Successfully refreshed enrichment data for {success_count} account(s)",
                    level=messages.SUCCESS
                )
            if error_count > 0:
                self.message_user(
                    request,
                    f"Failed to refresh {error_count} account(s)",
                    level=messages.WARNING
                )
        
        refresh_enrichment_data.short_description = "Refresh Enrichment Data (balance, home_domain, flags, assets)"

    @admin.register(ManagementCronHealth)
    class ManagementCronHealthAdmin(admin.ModelAdmin):
        list_display = ('cron_name', 'status', 'created_at')
        list_filter = ('status',)
        search_fields = ('cron_name',)
        readonly_fields = ('created_at', 'updated_at')

    @admin.register(StellarAccountStageExecution)
    class StellarAccountStageExecutionAdmin(admin.ModelAdmin):
        list_display = ('stellar_account_link', 'network_name', 'stage_number', 'status', 'created_at')
        list_filter = ('network_name', 'status', 'stage_number')
        search_fields = ('stellar_account', 'cron_name')
        readonly_fields = ('created_at', 'updated_at')

        def stellar_account_link(self, obj):
            """Display stellar_account as clickable link to search page."""
            account = obj.stellar_account
            network = obj.network_name
            url = f"/search/?account={account}&network={network}"
            return format_html('<a href="{}" target="_blank" title="{}">{}</a>', url, account, account[:8] + '...' + account[-8:] if len(account) > 20 else account)
        stellar_account_link.short_description = 'Stellar Account'


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
        try:
            return not BigQueryPipelineConfig.objects.all().count()
        except Exception:
            # If table doesn't exist or query fails, allow adding
            return True
    
    def has_delete_permission(self, request, obj=None):
        return False  # Never allow deleting the configuration
    
    def has_change_permission(self, request, obj=None):
        return True  # Allow editing
    
    # Organize fields into logical sections
    fieldsets = (
        ('📊 BigQuery Cost Controls', {
            'fields': ('bigquery_enabled', 'cost_limit_usd', 'size_limit_mb'),
            'description': format_html(
                '<div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px;margin:10px 0;color:#333;">'
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
                '<div style="background:#d1ecf1;border-left:4px solid #17a2b8;padding:12px;margin:10px 0;color:#333;">'
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
                '<div style="background:#d4edda;border-left:4px solid #28a745;padding:12px;margin:10px 0;color:#333;">'
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
                '<div style="background:#f8d7da;border-left:4px solid #dc3545;padding:12px;margin:10px 0;color:#333;">'
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
                '<div style="background:#e2e3e5;border-left:4px solid #6c757d;padding:12px;margin:10px 0;color:#333;">'
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
                '<div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px;margin:10px 0;color:#333;">'
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
        
        ('💎 High Value Account (HVA) Settings', {
            'fields': ('hva_threshold_xlm',),
            'description': format_html(
                '<div style="background:#d4edda;border-left:4px solid #28a745;padding:12px;margin:10px 0;color:#333;">'
                '<strong>💰 HVA THRESHOLD CONFIGURATION:</strong><br><br>'
                '<strong>hva_threshold_xlm (Default: 100,000 XLM)</strong><br>'
                '• Minimum XLM balance for an account to be considered "High Value"<br>'
                '• Accounts meeting this threshold are automatically tagged as HVA<br>'
                '• Used for: HVA Leaderboard, Query Builder filters, ranking system<br><br>'
                '<strong>💡 Examples:</strong><br>'
                '• <code>100000</code> → 100K XLM (CURRENT DEFAULT)<br>'
                '• <code>500000</code> → 500K XLM (more selective)<br>'
                '• <code>1000000</code> → 1M XLM (previous hardcoded value)<br>'
                '• <code>50000</code> → 50K XLM (less selective)<br><br>'
                '<strong>🎯 Impact:</strong><br>'
                '• Changes take effect immediately across all queries<br>'
                '• Query Builder descriptions auto-update<br>'
                '• Existing accounts re-evaluated on next pipeline run<br>'
                '</div>'
            )
        }),
        
        ('📝 Metadata', {
            'fields': ('updated_by', 'notes', 'created_at', 'updated_at'),
            'description': format_html(
                '<div style="background:#d1ecf1;border-left:4px solid #17a2b8;padding:12px;margin:10px 0;color:#333;">'
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
