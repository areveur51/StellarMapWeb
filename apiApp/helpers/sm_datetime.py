# sm_datetime.py - Efficient datetime helpers.
from datetime import datetime
import pytz
from cassandra.util import datetime_from_timestamp


class StellarMapDateTimeHelpers:

    def __init__(self):
        self.__datetime_obj = None
        self.__date_only_str = None

    def set_datetime_obj(self):
        tz_NY = pytz.timezone('America/New_York')
        datetime_NY = datetime.now(tz_NY)
        __date_str = datetime_NY.strftime("%Y-%m-%d %H:%M:%S")
        self.__date_only_str = datetime_NY.strftime("%Y-%m-%d")
        self.__datetime_obj = datetime.strptime(__date_str,
                                                "%Y-%m-%d %H:%M:%S")

    def get_datetime_obj(self):
        return self.__datetime_obj

    def get_date_str(self):
        return self.__date_only_str

    def convert_horizon_datetime_str_to_obj(self, horizon_datetime_str):
        dt_obj = datetime.strptime(horizon_datetime_str, '%Y-%m-%dT%H:%M:%SZ')
        timestamp = dt_obj.timestamp()
        return datetime_from_timestamp(timestamp)

    def convert_to_NY_datetime(self, df, column_name):
        """Convert DF column to NY datetime efficiently."""
        tz_NY = pytz.timezone('America/New_York')
        df[column_name] = pd.to_datetime(df[column_name], errors='coerce')
        df = df[df[column_name].notnull()]
        df[column_name] = df[column_name].dt.tz_localize('UTC').dt.tz_convert(
            tz_NY)
        df[column_name] = df[column_name].dt.strftime("%Y-%m-%d %H:%M:%S")
        return df
