from django.contrib import admin
from .models import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    ManagementCronHealth,
    StellarAccountStageExecution,
)


@admin.register(StellarAccountSearchCache)
class StellarAccountSearchCacheAdmin(admin.ModelAdmin):
    list_display = ('stellar_account', 'network_name', 'status', 'last_fetched_at', 
                    'retry_count', 'updated_at')
    list_filter = ('network_name', 'status')
    search_fields = ('stellar_account',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ()  # Disable ordering to work with Cassandra constraints
    show_full_result_count = False  # Disable count queries that use distinct()
    list_per_page = 50  # Limit results to improve performance
    
    def get_queryset(self, request):
        """Override to limit results and avoid complex Cassandra queries."""
        qs = super().get_queryset(request)
        return qs[:100]  # Limit to 100 records
    
    fieldsets = (
        ('Account Information', {
            'fields': ('stellar_account', 'network_name')
        }),
        ('Status & Cache', {
            'fields': ('status', 'cached_json', 'last_fetched_at')
        }),
        ('Error Tracking', {
            'fields': ('retry_count', 'last_error')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StellarCreatorAccountLineage)
class StellarCreatorAccountLineageAdmin(admin.ModelAdmin):
    list_display = ('stellar_account', 'network_name', 'stellar_creator_account', 
                    'xlm_balance', 'status', 'updated_at')
    list_filter = ('network_name', 'status')
    search_fields = ('stellar_account', 'stellar_creator_account', 'home_domain')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ()  # Disable ordering to work with Cassandra constraints
    show_full_result_count = False  # Disable count queries that use distinct()
    list_per_page = 50  # Limit results to improve performance
    
    def get_queryset(self, request):
        """Override to limit results and avoid complex Cassandra queries."""
        qs = super().get_queryset(request)
        return qs[:100]  # Limit to 100 records
    
    fieldsets = (
        ('Account Information', {
            'fields': ('id', 'stellar_account', 'network_name')
        }),
        ('Lineage Data', {
            'fields': ('stellar_creator_account', 'stellar_account_created_at', 
                      'home_domain', 'xlm_balance')
        }),
        ('Horizon API', {
            'fields': ('horizon_accounts_doc_api_href',)
        }),
        ('Status & Errors', {
            'fields': ('status', 'retry_count', 'last_error')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ManagementCronHealth)
class ManagementCronHealthAdmin(admin.ModelAdmin):
    list_display = ('cron_name', 'status', 'created_at', 'reason')
    list_filter = ('status', 'cron_name')
    search_fields = ('cron_name', 'reason')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ()  # Disable ordering to work with Cassandra constraints
    show_full_result_count = False  # Disable count queries that use distinct()
    list_per_page = 50  # Limit results to improve performance
    
    def get_queryset(self, request):
        """Override to limit results and avoid complex Cassandra queries."""
        qs = super().get_queryset(request)
        return qs[:100]  # Limit to 100 records
    
    fieldsets = (
        ('Cron Information', {
            'fields': ('id', 'cron_name', 'status')
        }),
        ('Details', {
            'fields': ('reason',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StellarAccountStageExecution)
class StellarAccountStageExecutionAdmin(admin.ModelAdmin):
    list_display = ('stellar_account', 'network_name', 'stage_number', 'cron_name', 
                    'status', 'execution_time_ms', 'created_at')
    list_filter = ('network_name', 'status', 'stage_number')
    search_fields = ('stellar_account', 'cron_name', 'error_message')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ()  # Disable ordering to work with Cassandra constraints
    show_full_result_count = False  # Disable count queries that use distinct()
    list_per_page = 50  # Limit results to improve performance
    
    def get_queryset(self, request):
        """Override to limit results and avoid complex Cassandra queries."""
        qs = super().get_queryset(request)
        return qs[:100]  # Limit to 100 records
    
    fieldsets = (
        ('Account Information', {
            'fields': ('stellar_account', 'network_name')
        }),
        ('Stage Execution', {
            'fields': ('stage_number', 'cron_name', 'status', 'execution_time_ms')
        }),
        ('Error Details', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
