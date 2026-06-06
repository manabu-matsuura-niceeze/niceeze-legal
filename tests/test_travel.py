"""手ぶら旅行システム テスト (Ver 1.0)"""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

from src.sbds.travel_qr import TravelQR, TravelQRManager, QR_CODE_LENGTH, VALID_STATUSES
from src.sbds.hub_webhook import HubWebhookClient, WebhookEvent, WebhookDeliveryResult
from src.sbds.ai_support import AISupportCenter, SupportRequest, SupportResponse
from src.sbds.travel_pdf import TravelPDFGenerator, TravelPDFDocument


# ---------------------------------------------------------------------------
# TestTravelQR
# ---------------------------------------------------------------------------
class TestTravelQR(unittest.TestCase):

    def setUp(self):
        self.mgr = TravelQRManager()

    def _issue(self, dep='TYO', arr='OSA', count=2):
        return self.mgr.issue('booking-hash-001', dep, arr, count)

    def test_issue_returns_travel_qr(self):
        qr = self._issue()
        self.assertIsInstance(qr, TravelQR)

    def test_is_valid_active_within_expiry(self):
        qr = self._issue()
        self.assertTrue(qr.is_valid)

    def test_is_valid_false_when_expired(self):
        qr = self._issue()
        # Manually set expires_at to the past
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        qr.expires_at = past
        self.assertFalse(qr.is_valid)

    def test_is_valid_false_when_cancelled(self):
        qr = self._issue()
        qr.status = 'cancelled'
        self.assertFalse(qr.is_valid)

    def test_scan_sets_status_used(self):
        qr = self._issue()
        scanned = self.mgr.scan(qr.token)
        self.assertEqual(scanned.status, 'used')

    def test_scan_sets_used_at(self):
        qr = self._issue()
        scanned = self.mgr.scan(qr.token)
        self.assertNotEqual(scanned.used_at, '')

    def test_scan_invalid_token_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.mgr.scan('invalid-token-xyz')

    def test_scan_expired_raises_value_error(self):
        qr = self._issue()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        qr.expires_at = past
        with self.assertRaises(ValueError):
            self.mgr.scan(qr.token)

    def test_expire_old_updates_count(self):
        qr = self._issue()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        qr.expires_at = past
        count = self.mgr.expire_old()
        self.assertEqual(count, 1)
        self.assertEqual(qr.status, 'expired')

    def test_expire_old_no_active_qr_returns_zero(self):
        count = self.mgr.expire_old()
        self.assertEqual(count, 0)

    def test_cancel_sets_status_cancelled(self):
        qr = self._issue()
        cancelled = self.mgr.cancel(qr.qr_id)
        self.assertEqual(cancelled.status, 'cancelled')

    def test_cancel_unknown_qr_id_raises(self):
        with self.assertRaises(ValueError):
            self.mgr.cancel('nonexistent0000')

    def test_get_by_hub_filters_departure(self):
        self._issue(dep='TYO', arr='OSA')
        self._issue(dep='FUK', arr='OSA')
        result = self.mgr.get_by_hub('TYO')
        self.assertEqual(len(result), 1)

    def test_get_by_hub_includes_arrival(self):
        self._issue(dep='TYO', arr='OSA')
        result = self.mgr.get_by_hub('OSA')
        self.assertEqual(len(result), 1)

    def test_qr_id_length_16(self):
        qr = self._issue()
        self.assertEqual(len(qr.qr_id), 16)

    def test_token_is_string_and_nonempty(self):
        qr = self._issue()
        self.assertIsInstance(qr.token, str)
        self.assertTrue(len(qr.token) > 0)

    def test_summary_keys(self):
        self._issue()
        s = self.mgr.summary()
        for key in ('total', 'active', 'expired', 'used', 'cancelled'):
            self.assertIn(key, s)

    def test_summary_counts(self):
        self._issue()
        self._issue()
        s = self.mgr.summary()
        self.assertEqual(s['total'], 2)
        self.assertEqual(s['active'], 2)

    def test_to_dict_has_required_keys(self):
        qr = self._issue()
        d = qr.to_dict()
        for key in ('qr_id', 'token', 'traveler_ref', 'departure_hub', 'arrival_hub',
                    'baggage_count', 'status', 'issued_at', 'expires_at', 'used_at'):
            self.assertIn(key, d)


# ---------------------------------------------------------------------------
# TestHubWebhook
# ---------------------------------------------------------------------------
class TestHubWebhook(unittest.TestCase):

    def setUp(self):
        # Ensure mock mode (no env var set)
        os.environ.pop('HUB_WEBHOOK_URLS', None)
        self.client = HubWebhookClient()
        self.mgr = TravelQRManager()

    def _issue_qr(self):
        return self.mgr.issue('ref-001', 'TYO', 'OSA', 1)

    def test_mock_mode_when_no_env(self):
        self.assertTrue(self.client._mock_mode)

    def test_dispatch_returns_delivery_result(self):
        qr = self._issue_qr()
        result = self.client.notify_dispatch(qr, {})
        self.assertIsInstance(result, WebhookDeliveryResult)

    def test_mock_dispatch_success_true(self):
        qr = self._issue_qr()
        result = self.client.notify_dispatch(qr, {})
        self.assertTrue(result.success)

    def test_notify_dispatch_event_type(self):
        qr = self._issue_qr()
        result = self.client.notify_dispatch(qr, {'weight_kg': 5})
        self.assertTrue(result.success)
        # event is stored in history
        history = self.client.get_history()
        self.assertTrue(any(e.event_type == 'baggage_dispatched' for e in history))

    def test_notify_arrival_event_type(self):
        qr = self._issue_qr()
        result = self.client.notify_arrival(qr)
        self.assertTrue(result.success)
        history = self.client.get_history()
        self.assertTrue(any(e.event_type == 'baggage_arrived' for e in history))

    def test_invalid_event_type_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.client._make_event(
                event_type='invalid_type',
                qr_id='abc',
                source_hub='TYO',
                target_hub='OSA',
                payload={},
            )

    def test_get_history_returns_list(self):
        self.assertIsInstance(self.client.get_history(), list)

    def test_summary_keys(self):
        s = self.client.summary()
        for key in ('total_events', 'delivered', 'failed', 'delivery_rate_pct', 'mock_mode'):
            self.assertIn(key, s)

    def test_summary_delivery_rate_after_dispatch(self):
        qr = self._issue_qr()
        self.client.notify_dispatch(qr, {})
        s = self.client.summary()
        self.assertEqual(s['total_events'], 1)
        self.assertEqual(s['delivered'], 1)
        self.assertEqual(s['delivery_rate_pct'], 100.0)

    def test_webhook_event_to_dict(self):
        qr = self._issue_qr()
        self.client.notify_dispatch(qr, {})
        history = self.client.get_history()
        d = history[0].to_dict()
        for key in ('event_id', 'event_type', 'qr_id', 'source_hub', 'target_hub',
                    'payload', 'sent_at', 'delivered', 'delivered_at', 'error'):
            self.assertIn(key, d)


# ---------------------------------------------------------------------------
# TestAISupport
# ---------------------------------------------------------------------------
class TestAISupport(unittest.TestCase):

    def setUp(self):
        os.environ.pop('ANTHROPIC_API_KEY', None)
        self.center = AISupportCenter()

    def _make_req(self, lang='ja', cat='general', msg='テスト', qr_id=''):
        return self.center.create_request(lang, cat, msg, qr_id)

    def test_respond_returns_support_response(self):
        req = self._make_req()
        resp = self.center.respond(req)
        self.assertIsInstance(resp, SupportResponse)

    def test_japanese_template_response(self):
        req = self._make_req(lang='ja', cat='general')
        resp = self.center.respond(req)
        self.assertEqual(resp.language, 'ja')
        self.assertIn('担当スタッフ', resp.response_text)

    def test_english_template_response(self):
        req = self._make_req(lang='en', cat='general')
        resp = self.center.respond(req)
        self.assertEqual(resp.language, 'en')
        self.assertIn('staff', resp.response_text)

    def test_unsupported_language_fallback(self):
        req = self._make_req(lang='fr', cat='general')
        resp = self.center.respond(req)
        self.assertEqual(resp.language, 'ja')  # DEFAULT_LANGUAGE

    def test_qr_id_empty_replaced_with_na(self):
        req = self._make_req(lang='ja', cat='baggage_tracking', qr_id='')
        resp = self.center.respond(req)
        self.assertIn('N/A', resp.response_text)

    def test_qr_id_present_in_response(self):
        req = self._make_req(lang='ja', cat='baggage_tracking', qr_id='abc123')
        resp = self.center.respond(req)
        self.assertIn('abc123', resp.response_text)

    def test_health_check_keys(self):
        hc = self.center.health_check()
        self.assertIn('status', hc)
        self.assertIn('supported_languages', hc)

    def test_health_check_status_template(self):
        hc = self.center.health_check()
        self.assertEqual(hc['status'], 'template')

    def test_get_history_returns_list(self):
        self.assertIsInstance(self.center.get_history(), list)

    def test_get_history_grows_after_respond(self):
        req = self._make_req()
        self.center.respond(req)
        self.assertEqual(len(self.center.get_history()), 1)

    def test_unknown_category_falls_back_to_general(self):
        req = self._make_req(cat='nonexistent_category')
        resp = self.center.respond(req)
        self.assertIsInstance(resp.response_text, str)
        self.assertTrue(len(resp.response_text) > 0)

    def test_source_is_template_in_mock_mode(self):
        req = self._make_req()
        resp = self.center.respond(req)
        self.assertEqual(resp.source, 'template')

    def test_response_to_dict(self):
        req = self._make_req()
        resp = self.center.respond(req)
        d = resp.to_dict()
        for key in ('request_id', 'language', 'response_text', 'source', 'responded_at'):
            self.assertIn(key, d)


# ---------------------------------------------------------------------------
# TestTravelPDF
# ---------------------------------------------------------------------------
class TestTravelPDF(unittest.TestCase):

    def setUp(self):
        self.mgr = TravelQRManager()
        self.gen = TravelPDFGenerator()

    def _issue_qr(self):
        return self.mgr.issue('ref-pdf-001', 'TYO', 'OSA', 3)

    def test_generate_html_returns_string(self):
        qr = self._issue_qr()
        doc = TravelPDFDocument(qr=qr)
        result = self.gen.generate_html(doc)
        self.assertIsInstance(result, str)

    def test_html_contains_qr_id(self):
        qr = self._issue_qr()
        doc = TravelPDFDocument(qr=qr)
        result = self.gen.generate_html(doc)
        self.assertIn(qr.qr_id, result)

    def test_html_contains_departure_hub(self):
        qr = self._issue_qr()
        doc = TravelPDFDocument(qr=qr)
        result = self.gen.generate_html(doc)
        self.assertIn('TYO', result)

    def test_html_contains_arrival_hub(self):
        qr = self._issue_qr()
        doc = TravelPDFDocument(qr=qr)
        result = self.gen.generate_html(doc)
        self.assertIn('OSA', result)

    def test_qr_pattern_is_21x21(self):
        qr = self._issue_qr()
        pattern = self.gen._generate_qr_pattern(qr.token)
        self.assertEqual(len(pattern), 21)
        for row in pattern:
            self.assertEqual(len(row), 21)

    def test_qr_pattern_finder_corners(self):
        qr = self._issue_qr()
        pattern = self.gen._generate_qr_pattern(qr.token)
        # Top-left finder
        for r in range(3):
            for c in range(3):
                self.assertTrue(pattern[r][c])

    def test_save_html_creates_file(self):
        qr = self._issue_qr()
        doc = TravelPDFDocument(qr=qr)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'test_qr.html')
            result_path = self.gen.save_html(doc, path)
            self.assertEqual(result_path, path)
            self.assertTrue(os.path.exists(path))
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIn(qr.qr_id, content)

    def test_generate_for_qr_returns_html(self):
        qr = self._issue_qr()
        result = self.gen.generate_for_qr(qr, language='en')
        self.assertIsInstance(result, str)
        self.assertIn('<!DOCTYPE html>', result)

    def test_html_has_footer_text(self):
        qr = self._issue_qr()
        doc = TravelPDFDocument(qr=qr)
        result = self.gen.generate_html(doc)
        self.assertIn('QRコードを到着拠点スタッフ', result)


if __name__ == '__main__':
    unittest.main()
