from django.test import TestCase
from unittest.mock import Mock, patch
from apiApp.helpers.sm_utils import StellarMapParsingUtilityHelpers, StellarMapUtilityHelpers


class StellarMapParsingUtilityHelpersTestCase(TestCase):
    
    def test_get_documentid_from_url_address_valid(self):
        url = "https://example.com/document/550e8400-e29b-41d4-a716-446655440000"
        result = StellarMapParsingUtilityHelpers.get_documentid_from_url_address(url)
        self.assertEqual(result, "550e8400-e29b-41d4-a716-446655440000")
    
    def test_get_documentid_from_url_address_no_uuid(self):
        url = "https://example.com/document/no-uuid-here"
        result = StellarMapParsingUtilityHelpers.get_documentid_from_url_address(url)
        self.assertEqual(result, '')
    
    def test_get_documentid_from_url_address_multiple_uuids(self):
        url = "https://example.com/550e8400-e29b-41d4-a716-446655440000/document/123e4567-e89b-12d3-a456-426614174000"
        result = StellarMapParsingUtilityHelpers.get_documentid_from_url_address(url)
        self.assertEqual(result, "550e8400-e29b-41d4-a716-446655440000")
    
    def test_get_documentid_from_url_address_empty_string(self):
        result = StellarMapParsingUtilityHelpers.get_documentid_from_url_address("")
        self.assertEqual(result, '')


class StellarMapUtilityHelpersTestCase(TestCase):
    
    @patch('apiApp.helpers.sm_utils.StellarMapCronHelpers')
    @patch('apiApp.helpers.sm_utils.sentry_sdk')
    def test_on_retry_failure(self, mock_sentry, mock_cron_helpers):
        mock_retry_state = Mock()
        mock_retry_state.outcome.exception.return_value = Exception("Test exception")
        
        util_helpers = StellarMapUtilityHelpers()
        cron_name = "test_cron"
        
        util_helpers.on_retry_failure(mock_retry_state, cron_name)
        
        mock_sentry.capture_exception.assert_called_once()
        mock_cron_helpers.assert_called_once_with(cron_name=cron_name)
