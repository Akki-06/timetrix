"""Unit tests for RejectionLog and RunTimer."""
import time

from django.test import SimpleTestCase

from scheduler.engine.observability import RejectionLog, RunTimer


class RejectionLogTests(SimpleTestCase):

    def test_records_and_normalizes(self):
        log = RejectionLog()
        log.record(7, "faculty 17 busy at MON S3")
        log.record(7, "faculty 9 busy at TUE S1")
        log.record(7, "room 42 busy at WED S4")
        top = log.top(7, n=5)
        reasons = {k: v for k, v in top}
        self.assertIn("faculty busy", reasons)
        self.assertEqual(reasons["faculty busy"], 2)
        self.assertEqual(reasons["room busy"], 1)

    def test_global_summary(self):
        log = RejectionLog()
        log.record(1, "faculty 3 at weekly limit 18")
        log.record(2, "faculty 4 at weekly limit 18")
        log.record(3, "room 99 busy at MON S1")
        sm = dict(log.summary(5))
        self.assertEqual(sm["faculty at weekly cap"], 2)
        self.assertEqual(sm["room busy"], 1)

    def test_empty_reason_ignored(self):
        log = RejectionLog()
        log.record(1, "")
        self.assertEqual(log.top(1), [])


class RunTimerTests(SimpleTestCase):

    def test_phase_records_time(self):
        t = RunTimer()
        with t.phase("load"):
            time.sleep(0.01)
        with t.phase("save"):
            time.sleep(0.01)
        d = t.as_dict()
        self.assertIn("load", d)
        self.assertIn("save", d)
        self.assertIn("total", d)
        self.assertGreaterEqual(d["load"], 0.0)

    def test_same_phase_accumulates(self):
        t = RunTimer()
        with t.phase("repeat"):
            time.sleep(0.005)
        with t.phase("repeat"):
            time.sleep(0.005)
        self.assertGreater(t.as_dict()["repeat"], 0.005)
