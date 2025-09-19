# apiApp/urls.py
from django.urls import path  # Use path over re_path for simplicity/efficiency
from rest_framework.urlpatterns import format_suffix_patterns
from apiApp.views import (check_all_urls, set_network, lineage_stellar_account,
                          UserInquirySearchHistoryViewSet,
                          UserInquirySearchHistoryListCreateAPIView,
                          UserInquirySearchHistoryListAPIView,
                          GetAccountGenealogy)

app_name = 'apiApp'
urlpatterns = [
    path('check_all_urls/', check_all_urls, name='check_all_urls'),
    path('set_network/<str:network>/', set_network, name='set_network'),
    path(
        'lineage/network/<str:network>/stellar_address/<str:stellar_account_address>/',
        lineage_stellar_account,
        name='lineage_stellar_account'),
    path('stellar-inquiries/',
         UserInquirySearchHistoryViewSet.as_view({'post': 'create'}),
         name='stellar-inquiries'),
    path(
        'account-genealogy/network/<str:network>/stellar_address/<str:stellar_account_address>/',
        GetAccountGenealogy.as_view(),
        name='account-genealogy'),
    path('inquiries-viewset/',
         UserInquirySearchHistoryViewSet.as_view({'get': 'list'}),
         name='inquiries_viewset_api'),
    path('inquiries-listcreate/',
         UserInquirySearchHistoryListCreateAPIView.as_view(),
         name='inquiries_listcreate_api'),
    path('inquiries-listview/',
         UserInquirySearchHistoryListAPIView.as_view(),
         name='inquiries_listview_api'),
]

urlpatterns = format_suffix_patterns(
    urlpatterns)  # Keep for API format support
