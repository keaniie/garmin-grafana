import os
import sys
import types
import datetime

# Stub external modules before importing method_test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.modules['pytz'] = types.SimpleNamespace(UTC=datetime.timezone.utc)
sys.modules['garminconnect'] = types.SimpleNamespace(Garmin=object)

import method_test
import unittest
from unittest.mock import patch

class TestCalculateVo2MaxRatio(unittest.TestCase):
    def test_valid(self):
        stats = {'restingHeartRate': 40, 'maxHeartRate': 160}
        self.assertAlmostEqual(method_test.calculate_vo2max_ratio(stats), 61.2)

    def test_invalid(self):
        stats = {'restingHeartRate': 60, 'maxHeartRate': 55}
        self.assertIsNone(method_test.calculate_vo2max_ratio(stats))

class TestPredictRaceTimesFromVo2(unittest.TestCase):
    def test_predictions(self):
        result = method_test.predict_race_times_from_vo2(50)
        expected = {
            '5K': 1364,
            '10K': 2892,
            'Half Marathon': 6492,
            'Marathon': 14892
        }
        self.assertEqual(result, expected)

class FakeGarmin:
    def __init__(self, data):
        self.data = data

    def get_activities_by_date(self, start_date, end_date):
        return self.data.get(start_date, [])

def make_fake_activity(z1, z2, z3, z4, z5):
    return {
        'hrTimeInZone_1': z1,
        'hrTimeInZone_2': z2,
        'hrTimeInZone_3': z3,
        'hrTimeInZone_4': z4,
        'hrTimeInZone_5': z5,
    }

class TestCalculateTrainingLoadFocus(unittest.TestCase):
    def test_focus_single_day(self):
        data = {'2023-01-01': [make_fake_activity(10, 20, 30, 40, 0)]}
        focus = method_test.calculate_training_load_focus(FakeGarmin(data), '2023-01-01', days=1)
        self.assertEqual(focus, {
            'low_aerobic': 30.0,
            'high_aerobic': 70.0,
            'anaerobic': 0.0
        })

class TestFetchVo2Max(unittest.TestCase):
    @patch('method_test.calculate_vo2max_segmented', return_value=None)
    def test_ratio_fallback(self, mock_seg):
        class G:
            def get_stats(self, d):
                return {'restingHeartRate': 40, 'maxHeartRate': 160}
        self.assertEqual(method_test.fetch_vo2max(G(), '2023-01-01'), 61.2)

if __name__ == '__main__':
    unittest.main()
