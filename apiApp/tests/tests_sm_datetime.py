from django.test import TestCase
from datetime import datetime
import pytz
from apiApp.helpers.sm_datetime import StellarMapDateTimeHelpers


class StellarMapDateTimeHelpersTestCase(TestCase):
    
    def setUp(self):
        self.datetime_helpers = StellarMapDateTimeHelpers()
    
    def test_set_and_get_datetime_obj(self):
        self.datetime_helpers.set_datetime_obj()
        datetime_obj = self.datetime_helpers.get_datetime_obj()
        self.assertIsInstance(datetime_obj, datetime)
        self.assertIsNotNone(datetime_obj)
    
    def test_get_date_str(self):
        self.datetime_helpers.set_datetime_obj()
        date_str = self.datetime_helpers.get_date_str()
        self.assertIsInstance(date_str, str)
        self.assertRegex(date_str, r'^\d{4}-\d{2}-\d{2}$')
    
    def test_convert_horizon_datetime_str_to_obj(self):
        horizon_datetime_str = "2023-10-15T12:30:45Z"
        result = self.datetime_helpers.convert_horizon_datetime_str_to_obj(horizon_datetime_str)
        self.assertIsNotNone(result)
    
    def test_convert_horizon_datetime_str_to_obj_invalid(self):
        invalid_str = "invalid-datetime"
        with self.assertRaises(ValueError):
            self.datetime_helpers.convert_horizon_datetime_str_to_obj(invalid_str)
    
    def test_datetime_obj_is_ny_timezone(self):
        self.datetime_helpers.set_datetime_obj()
        datetime_obj = self.datetime_helpers.get_datetime_obj()
        self.assertIsInstance(datetime_obj, datetime)
