# apiApp/urls.py
from django.urls import path
from . import views

app_name = 'apiApp'

urlpatterns = [
    path('', views.api_home, name='api_home'),
    path('pending-accounts/', views.pending_accounts_api, name='pending_accounts_api'),
    path('stage-executions/', views.stage_executions_api, name='stage_executions_api'),
    path('account-lineage/', views.account_lineage_api, name='account_lineage_api'),
    path('lineage-with-siblings/', views.lineage_with_siblings_api, name='lineage_with_siblings_api'),
    path('fetch-toml/', views.fetch_toml_api, name='fetch_toml_api'),
    path('retry-failed-account/', views.retry_failed_account_api, name='retry_failed_account_api'),
    path('refresh-enrichment/', views.refresh_enrichment_api, name='refresh_enrichment_api'),
    path('server-logs/', views.server_logs_api, name='server_logs_api'),
    path('error-logs/', views.error_logs_api, name='error_logs_api'),
    path('bulk-queue-accounts/', views.bulk_queue_accounts_api, name='bulk_queue_accounts_api'),
    path('cassandra-query/', views.cassandra_query_api, name='cassandra_query_api'),
    path('pipeline-stats/', views.pipeline_stats_api, name='pipeline_stats_api'),
]