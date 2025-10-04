from django.test import TestCase
from unittest.mock import patch, Mock
from apiApp.helpers.sm_cron import StellarMapCronHelpers


class StellarMapCronHelpersTestCase(TestCase):
    
    def setUp(self):
        self.cron_helpers = StellarMapCronHelpers()
    
    @patch('apiApp.helpers.sm_cron.logging')
    def test_log_cron_start(self, mock_logging):
        cron_name = "test_cron_job"
        self.cron_helpers.log_cron_start(cron_name)
        self.assertIsNotNone(self.cron_helpers.logger)
    
    @patch('apiApp.helpers.sm_cron.logging')
    def test_log_cron_end(self, mock_logging):
        cron_name = "test_cron_job"
        self.cron_helpers.log_cron_end(cron_name)
        self.assertIsNotNone(self.cron_helpers.logger)
    
    def test_check_cron_health(self):
        cron_name = "test_cron_job"
        result = self.cron_helpers.check_cron_health(cron_name)
        self.assertIsInstance(result, bool)
        self.assertTrue(result)
    
    @patch('apiApp.helpers.sm_cron.sentry_sdk')
    def test_log_cron_start_handles_exception(self, mock_sentry):
        self.cron_helpers.logger = Mock()
        self.cron_helpers.logger.info.side_effect = Exception("Test error")
        
        self.cron_helpers.log_cron_start("test_cron")
        mock_sentry.capture_exception.assert_called_once()
