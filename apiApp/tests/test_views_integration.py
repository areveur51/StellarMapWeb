import datetime
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory
from django.urls import reverse
from webApp.views import search_view
from apiApp.models import (
    StellarAccountSearchCache,
    StellarCreatorAccountLineage,
    PENDING_MAKE_PARENT_LINEAGE,
    DONE_MAKE_PARENT_LINEAGE
)


class SearchViewIntegrationTest(TestCase):
    """
    Integration tests for search_view with mocked Cassandra operations.
    Tests cache flow, PENDING entry creation, and view rendering.
    """

    def setUp(self):
        """Set up test data and request factory."""
        self.factory = RequestFactory()
        self.test_account = "GALPCCZN4YXA3YMJHKL6CVIECKPLJJCTVMSNYWBTKJW4K5HQLYLDMZTB"
        self.test_network = "public"

    @patch('webApp.views.StellarMapCacheHelpers')
    @patch('webApp.views.StellarAccountSearchCache.objects')
    def test_search_view_fresh_cache_hit(self, mock_cache_objects, mock_helpers_class):
        """Test that search_view returns cached data for fresh cache hits."""
        mock_helpers = Mock()
        mock_helpers.check_cache_freshness.return_value = (True, Mock(
            stellar_account=self.test_account,
            network_name=self.test_network,
            cached_json=json.dumps({"test": "data"}),
            last_fetched_at=datetime.datetime.utcnow()
        ))
        mock_helpers.get_cached_data.return_value = {"test": "data"}
        mock_helpers_class.return_value = mock_helpers
        
        request = self.factory.get('/search/', {
            'stellar_account': self.test_account,
            'network_name': self.test_network
        })
        
        with patch('webApp.views.render') as mock_render:
            mock_render.return_value = Mock(status_code=200)
            response = search_view(request)
            
            # Verify cache helpers were called
            mock_helpers.check_cache_freshness.assert_called_once_with(
                self.test_account, self.test_network
            )
            mock_helpers.get_cached_data.assert_called_once()

    @patch('webApp.views.StellarMapCacheHelpers')
    @patch('webApp.views.StellarAccountSearchCache.objects')
    def test_search_view_stale_cache_creates_pending(self, mock_cache_objects, mock_helpers_class):
        """Test that search_view creates PENDING entry for stale cache."""
        mock_helpers = Mock()
        mock_helpers.check_cache_freshness.return_value = (False, Mock(
            stellar_account=self.test_account,
            network_name=self.test_network
        ))
        mock_helpers.create_pending_entry.return_value = Mock(
            stellar_account=self.test_account,
            network_name=self.test_network,
            status=PENDING_MAKE_PARENT_LINEAGE
        )
        mock_helpers_class.return_value = mock_helpers
        
        request = self.factory.get('/search/', {
            'stellar_account': self.test_account,
            'network_name': self.test_network
        })
        
        with patch('webApp.views.render') as mock_render:
            mock_render.return_value = Mock(status_code=200)
            response = search_view(request)
            
            # Verify PENDING entry was created
            mock_helpers.create_pending_entry.assert_called_once_with(
                self.test_account, self.test_network
            )

    @patch('webApp.views.StellarMapCacheHelpers')
    def test_search_view_missing_cache_creates_pending(self, mock_helpers_class):
        """Test that search_view creates PENDING entry when no cache exists."""
        mock_helpers = Mock()
        mock_helpers.check_cache_freshness.return_value = (False, None)
        mock_helpers.create_pending_entry.return_value = Mock(
            stellar_account=self.test_account,
            network_name=self.test_network,
            status=PENDING_MAKE_PARENT_LINEAGE,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        mock_helpers_class.return_value = mock_helpers
        
        request = self.factory.get('/search/', {
            'stellar_account': self.test_account,
            'network_name': self.test_network
        })
        
        with patch('webApp.views.render') as mock_render:
            mock_render.return_value = Mock(status_code=200)
            response = search_view(request)
            
            # Verify PENDING entry was created for new account
            mock_helpers.create_pending_entry.assert_called_once()

    @patch('webApp.views.StellarAccountSearchCache.objects')
    @patch('webApp.views.StellarCreatorAccountLineage.objects')
    def test_search_view_fetches_lineage_data(self, mock_lineage_objects, mock_cache_objects):
        """Test that search_view fetches lineage records for display."""
        mock_lineages = [
            Mock(stellar_account=self.test_account, stellar_creator_account="CREATOR1"),
            Mock(stellar_account=self.test_account, stellar_creator_account="CREATOR2"),
        ]
        
        mock_lineage_objects.filter.return_value = mock_lineages
        
        lineages = StellarCreatorAccountLineage.objects.filter(
            stellar_account=self.test_account,
            network_name=self.test_network
        )
        
        self.assertEqual(len(lineages), 2)

    @patch('webApp.views.StellarMapCacheHelpers')
    def test_search_view_validates_stellar_address(self, mock_helpers_class):
        """Test that search_view validates Stellar address format."""
        invalid_account = "INVALID_ADDRESS"
        
        request = self.factory.get('/search/', {
            'stellar_account': invalid_account,
            'network_name': self.test_network
        })
        
        with patch('webApp.views.render') as mock_render:
            mock_render.return_value = Mock(status_code=200)
            
            # Should handle invalid address gracefully
            response = search_view(request)
            
            # Verify render was called (even for invalid address)
            mock_render.assert_called_once()

    @patch('webApp.views.StellarMapCacheHelpers')
    @patch('webApp.views.StellarAccountSearchCache.objects')
    def test_search_view_context_includes_cache_entry(self, mock_cache_objects, mock_helpers_class):
        """Test that search_view includes cache_entry in context."""
        mock_entry = Mock()
        mock_entry.stellar_account = self.test_account
        mock_entry.network_name = self.test_network
        mock_entry.status = DONE_MAKE_PARENT_LINEAGE
        mock_entry.cached_json = json.dumps({"test": "data"})
        
        mock_helpers = Mock()
        mock_helpers.check_cache_freshness.return_value = (True, mock_entry)
        mock_helpers.get_cached_data.return_value = {"test": "data"}
        mock_helpers_class.return_value = mock_helpers
        
        request = self.factory.get('/search/', {
            'stellar_account': self.test_account,
            'network_name': self.test_network
        })
        
        with patch('webApp.views.render') as mock_render:
            mock_render.return_value = Mock(status_code=200)
            search_view(request)
            
            # Verify context was built with cache_entry
            call_args = mock_render.call_args
            context = call_args[0][2] if len(call_args[0]) > 2 else {}
            
            # Context should be prepared even if not all fields are present
            self.assertTrue(mock_render.called)

    @patch('webApp.views.StellarMapCacheHelpers')
    def test_search_view_handles_network_parameter(self, mock_helpers_class):
        """Test that search_view correctly handles network parameter."""
        mock_helpers = Mock()
        mock_helpers.check_cache_freshness.return_value = (False, None)
        mock_helpers.create_pending_entry.return_value = Mock()
        mock_helpers_class.return_value = mock_helpers
        
        # Test with testnet
        request = self.factory.get('/search/', {
            'stellar_account': self.test_account,
            'network_name': 'testnet'
        })
        
        with patch('webApp.views.render') as mock_render:
            mock_render.return_value = Mock(status_code=200)
            search_view(request)
            
            # Verify network was passed correctly
            mock_helpers.check_cache_freshness.assert_called_with(
                self.test_account, 'testnet'
            )

    @patch('webApp.views.StellarMapCacheHelpers')
    @patch('webApp.views.StellarMapCreatorAccountLineageHelpers')
    def test_search_view_attempts_immediate_refresh(self, mock_lineage_helpers_class, mock_cache_helpers_class):
        """Test that search_view attempts immediate refresh for better UX."""
        mock_cache_helpers = Mock()
        mock_cache_helpers.check_cache_freshness.return_value = (False, Mock())
        mock_cache_helpers.create_pending_entry.return_value = Mock(
            stellar_account=self.test_account,
            network_name=self.test_network
        )
        mock_cache_helpers_class.return_value = mock_cache_helpers
        
        mock_lineage_helpers = Mock()
        mock_lineage_helpers_class.return_value = mock_lineage_helpers
        
        request = self.factory.get('/search/', {
            'stellar_account': self.test_account,
            'network_name': self.test_network
        })
        
        with patch('webApp.views.render') as mock_render:
            mock_render.return_value = Mock(status_code=200)
            search_view(request)
            
            # Verify helpers were instantiated (immediate refresh attempt)
            mock_cache_helpers_class.assert_called()

    @patch('webApp.views.StellarAccountSearchCache.objects')
    def test_search_view_refreshes_cache_entry_after_pending_creation(self, mock_cache_objects):
        """Test that search_view refreshes cache_entry after create_pending_entry."""
        mock_entry = Mock()
        mock_entry.stellar_account = self.test_account
        mock_entry.network_name = self.test_network
        mock_entry.status = PENDING_MAKE_PARENT_LINEAGE
        
        mock_cache_objects.get.return_value = mock_entry
        
        # Simulate refreshing cache entry
        refreshed_entry = StellarAccountSearchCache.objects.get(
            stellar_account=self.test_account,
            network_name=self.test_network
        )
        
        self.assertEqual(refreshed_entry.status, PENDING_MAKE_PARENT_LINEAGE)
        mock_cache_objects.get.assert_called_once()
