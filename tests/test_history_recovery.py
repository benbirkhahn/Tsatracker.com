"""Offline archive-build checks (optional pandas/pyarrow tooling, not runtime deps)."""
import unittest
try:
    from scripts.recover_airport_history import recover
    import pandas as pd
except ImportError:
    recover = None


@unittest.skipIf(recover is None, 'Archive build tooling requires pandas')
class RecoveryTests(unittest.TestCase):
    def test_timezone_lane_exclusions_duplicates_and_coverage(self):
        rows = []
        for minute in range(30):
            base = dict(terminal='Terminal A North', queue_type='standard', wait_minutes=10,
                        status='open', is_open=True, wait_is_estimated=False,
                        scraped_at=f'2026-10-01T19:{minute:02d}:00Z')
            rows += [base, dict(base), dict(base, terminal='Terminal C North Premier', queue_type='precheck', wait_minutes=100),
                     dict(base, terminal='Closed', status='closed', is_open=False, wait_minutes=0),
                     dict(base, terminal='Text derived', wait_is_estimated=True, wait_minutes=100),
                     dict(base, terminal='Unknown', status='unknown', wait_minutes=100),
                     dict(base, terminal='Terminal E', queue_type='precheck', wait_minutes=0)]
        result = recover(pd.DataFrame(rows), 'IAH')
        self.assertEqual(len(result), 2)
        self.assertEqual({r['hour'] for r in result}, {14})
        by_lane = {r['lane']: r for r in result}
        self.assertEqual(by_lane['STANDARD']['mean'], 10)
        self.assertEqual(by_lane['PRECHECK']['mean'], 0)
        self.assertEqual(by_lane['STANDARD']['samples'], 30)
        # Florida has a different local hour for exactly the same UTC readings.
        self.assertEqual({r['hour'] for r in recover(pd.DataFrame(rows), 'MCO')}, {15})
        short = [r for r in rows if r['scraped_at'] != '2026-10-01T19:29:00Z']
        self.assertEqual(recover(pd.DataFrame(short), 'IAH'), [])
