"""手ぶら旅行デモシナリオAPIテスト"""
import json
import unittest
from http.server import HTTPServer
import threading
import urllib.request

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.sbds.demo_scenario_api import (
    DEMO_TRAVELER, SCENARIO_STEPS, _get_admin_approval_required,
    _start_scenario, _get_scenario, _next_step, _reset_all,
    _scenarios, _build_timeline,
)


class TestDemoScenarioData(unittest.TestCase):
    def test_demo_traveler_name(self):
        self.assertEqual(DEMO_TRAVELER['name'], '田中花子')

    def test_demo_traveler_name_en(self):
        self.assertEqual(DEMO_TRAVELER['name_en'], 'Hanako Tanaka')

    def test_demo_traveler_baggage_count(self):
        self.assertEqual(DEMO_TRAVELER['baggage_count'], 1)

    def test_scenario_steps_count(self):
        self.assertEqual(len(SCENARIO_STEPS), 5)

    def test_scenario_steps_order(self):
        self.assertEqual(SCENARIO_STEPS[0], 'step1_checkin')
        self.assertEqual(SCENARIO_STEPS[-1], 'step5_unlocked')

    def test_admin_approval_required_always_true(self):
        self.assertTrue(_get_admin_approval_required())


class TestDemoScenarioLogic(unittest.TestCase):
    def setUp(self):
        _scenarios.clear()

    def test_start_scenario_returns_dict(self):
        result = _start_scenario(b'{}')
        self.assertIn('scenario_id', result)
        self.assertIn('qr_id', result)

    def test_start_scenario_initial_step(self):
        result = _start_scenario(b'{}')
        self.assertEqual(result['current_step'], SCENARIO_STEPS[0])

    def test_start_scenario_admin_approval_required(self):
        result = _start_scenario(b'{}')
        self.assertTrue(result['admin_approval_required'])

    def test_get_scenario_existing(self):
        created = _start_scenario(b'{}')
        sid = created['scenario_id']
        fetched = _get_scenario(sid)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched['scenario_id'], sid)

    def test_get_scenario_not_found(self):
        result = _get_scenario('NOTEXIST')
        self.assertIsNone(result)

    def test_next_step_advances(self):
        created = _start_scenario(b'{}')
        sid = created['scenario_id']
        result = _next_step(sid)
        self.assertEqual(result['current_step'], SCENARIO_STEPS[1])

    def test_next_step_all_steps(self):
        created = _start_scenario(b'{}')
        sid = created['scenario_id']
        for i in range(1, len(SCENARIO_STEPS)):
            result = _next_step(sid)
            self.assertEqual(result['current_step'], SCENARIO_STEPS[i])

    def test_next_step_stays_at_last(self):
        created = _start_scenario(b'{}')
        sid = created['scenario_id']
        for _ in range(len(SCENARIO_STEPS) + 2):
            result = _next_step(sid)
        self.assertEqual(result['current_step'], SCENARIO_STEPS[-1])

    def test_next_step_not_found(self):
        result = _next_step('NOTEXIST')
        self.assertIsNone(result)

    def test_reset_all(self):
        _start_scenario(b'{}')
        result = _reset_all()
        self.assertIn('status', result)
        self.assertTrue(result['admin_approval_required'])

    def test_timeline_length(self):
        timeline = _build_timeline(0)
        self.assertEqual(len(timeline), len(SCENARIO_STEPS))

    def test_timeline_first_step_done(self):
        timeline = _build_timeline(0)
        self.assertTrue(timeline[0]['done'])
        self.assertFalse(timeline[1]['done'])

    def test_timeline_has_bilingual_labels(self):
        timeline = _build_timeline(0)
        for item in timeline:
            self.assertIn('label', item)
            self.assertIn('label_en', item)

    def test_qr_id_demo_prefix(self):
        result = _start_scenario(b'{}')
        self.assertTrue(result['qr_id'].startswith('DEMO-'))

    def test_scenario_traveler_matches_demo(self):
        result = _start_scenario(b'{}')
        self.assertEqual(result['traveler']['name'], DEMO_TRAVELER['name'])


if __name__ == '__main__':
    unittest.main()
