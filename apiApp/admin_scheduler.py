"""
Admin configuration for Scheduler Configuration.
Separated into its own file for cleaner organization.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import SchedulerConfig


@admin.register(SchedulerConfig)
class SchedulerConfigAdmin(admin.ModelAdmin):
    """
    Admin interface for Scheduler Configuration.
    
    This is a singleton configuration model - only one configuration record should exist.
    Controls all scheduler behavior, cron schedule, and batch processing settings.
    """
    
    # Allow editing for this model
    def has_add_permission(self, request):
        # Only allow adding if no configuration exists
        try:
            return not SchedulerConfig.objects.all().count()
        except Exception:
            # If table doesn't exist or query fails, allow adding
            return True
    
    def has_delete_permission(self, request, obj=None):
        return False  # Never allow deleting the configuration
    
    def has_change_permission(self, request, obj=None):
        return True  # Allow editing
    
    # Organize fields into logical sections
    fieldsets = (
        ('⚙️ Scheduler Control', {
            'fields': ('scheduler_enabled', 'cron_schedule', 'batch_limit'),
            'description': format_html(
                '<div style="background:#e7f5ff;border-left:4px solid #228be6;padding:12px;margin:10px 0;color:#333;">'
                '<strong>📅 SCHEDULER SETTINGS:</strong> Control when and how the pipeline runs.<br>'
                '<strong>Current Schedule:</strong> Every 2 hours (default)<br><br>'
                '<strong>Common Schedules:</strong><br>'
                '• <code>0 */2 * * *</code> - Every 2 hours (recommended)<br>'
                '• <code>*/30 * * * *</code> - Every 30 minutes<br>'
                '• <code>0 */6 * * *</code> - Every 6 hours<br>'
                '• <code>0 0 * * *</code> - Once per day at midnight<br>'
                '</div>'
            ),
        }),
        ('▶️ Execution Options', {
            'fields': ('run_on_startup',),
            'description': format_html(
                '<div style="background:#f0f9ff;border-left:4px solid#0ea5e9;padding:12px;margin:10px 0;color:#333;">'
                '<strong>🚀 STARTUP BEHAVIOR:</strong><br>'
                '• Enabled: Pipeline runs immediately when deployed (then follows schedule)<br>'
                '• Disabled: Only runs on schedule<br>'
                '</div>'
            ),
        }),
        ('📊 Monitoring & Statistics', {
            'fields': (
                'last_run_at',
                'last_run_status',
                'last_run_processed',
                'last_run_failed',
            ),
            'description': format_html(
                '<div style="background:#f3f4f6;border-left:4px solid #6b7280;padding:12px;margin:10px 0;color:#333;">'
                '<strong>📈 RUN STATISTICS:</strong> These fields are updated automatically after each pipeline run.<br>'
                'Check these to monitor scheduler health and performance.'
                '</div>'
            ),
        }),
        ('📝 Metadata', {
            'fields': ('updated_by', 'notes'),
            'classes': ('collapse',),
        }),
    )
    
    # List display
    list_display = (
        'config_id',
        'scheduler_status_display',
        'schedule_display',
        'batch_limit',
        'last_run_display',
        'updated_at',
    )
    
    # Read-only fields (system-managed)
    readonly_fields = (
        'last_run_at',
        'last_run_status',
        'last_run_processed',
        'last_run_failed',
        'created_at',
        'updated_at',
    )
    
    def scheduler_status_display(self, obj):
        """Display scheduler status with color coding."""
        if obj.scheduler_enabled:
            return format_html(
                '<span style="color:green;font-weight:bold">● Enabled</span>'
            )
        else:
            return format_html(
                '<span style="color:red;font-weight:bold">○ Disabled</span>'
            )
    scheduler_status_display.short_description = 'Status'
    
    def schedule_display(self, obj):
        """Display cron schedule with human-readable description."""
        schedule_map = {
            '0 */2 * * *': 'Every 2 hours',
            '*/30 * * * *': 'Every 30 minutes',
            '0 */6 * * *': 'Every 6 hours',
            '0 0 * * *': 'Daily at midnight',
            '0 */1 * * *': 'Every hour',
        }
        
        description = schedule_map.get(obj.cron_schedule, 'Custom')
        
        return format_html(
            '<code>{}</code><br><small style="color:#666">{}</small>',
            obj.cron_schedule,
            description
        )
    schedule_display.short_description = 'Schedule'
    
    def last_run_display(self, obj):
        """Display last run information with status color."""
        if not obj.last_run_at:
            return format_html('<span style="color:#999">Never run</span>')
        
        # Color code based on status
        if obj.last_run_status == 'SUCCESS':
            color = 'green'
            icon = '✓'
        elif obj.last_run_status == 'FAILED':
            color = 'red'
            icon = '✗'
        else:
            color = 'orange'
            icon = '⚠'
        
        from django.utils import timezone
        from datetime import timedelta
        
        # Calculate time since last run
        now = timezone.now()
        time_diff = now - obj.last_run_at
        
        if time_diff < timedelta(hours=1):
            time_str = f'{int(time_diff.total_seconds() / 60)} min ago'
        elif time_diff < timedelta(days=1):
            time_str = f'{int(time_diff.total_seconds() / 3600)} hours ago'
        else:
            time_str = f'{time_diff.days} days ago'
        
        return format_html(
            '<span style="color:{}">{} {}</span><br>'
            '<small>Processed: {} | Failed: {}</small><br>'
            '<small style="color:#666">{}</small>',
            color,
            icon,
            obj.last_run_status or 'Unknown',
            obj.last_run_processed,
            obj.last_run_failed,
            time_str
        )
    last_run_display.short_description = 'Last Run'
    
    def save_model(self, request, obj, form, change):
        """Auto-populate updated_by field with current user."""
        obj.updated_by = request.user.username
        super().save_model(request, obj, form, change)
    
    def changelist_view(self, request, extra_context=None):
        """Override to show single config or creation form."""
        try:
            config_exists = SchedulerConfig.objects.filter(config_id='default').exists()
            
            if not config_exists:
                # Redirect to add form if no config exists
                from django.shortcuts import redirect
                from django.urls import reverse
                return redirect(reverse('admin:apiApp_schedulerconfig_add'))
        except:
            pass
        
        return super().changelist_view(request, extra_context=extra_context)
