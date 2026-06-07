# tests/test_consent_flow.py
# TASK-PP4: 同意フロー共通処理テスト (35件以上)
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch
from http.server import HTTPServer

from src.common.consent_manager import ConsentManager
from src.common.consent_flow import (
    ConsentFlowProcessor,
    RegistrationRequest,
    RegistrationResult,
    REQUIRED_CONSENTS,
    OPTIONAL_CONSENTS,
    GDPR_REQUIRED_CONSENTS,
    VALID_GUARDIAN_METHODS,
)


def make_req(**kwargs) -> RegistrationRequest:
    defaults = dict(
        user_id='user-001',
        service='sbds',
        country_code='JP',
        consents={'privacy_policy': True},
        age_confirmed=True,
        is_minor=False,
        guardian_consent_method='',
        guardian_name='',
    )
    defaults.update(kwargs)
    return RegistrationRequest(**defaults)


class TestGetRequiredConsents(unittest.TestCase):

    def setUp(self):
        self.proc = ConsentFlowProcessor()

    # 1
    def test_sbds_jp_required(self):
        req = self.proc.get_required_consents('sbds', 'JP')
        self.assertIn('privacy_policy', req)
        self.assertNotIn('gdpr_rights_acknowledged', req)

    # 2
    def test_sbds_de_includes_gdpr(self):
        req = self.proc.get_required_consents('sbds', 'DE')
        self.assertIn('privacy_policy', req)
        self.assertIn('gdpr_rights_acknowledged', req)

    # 3
    def test_smartlife_jp_required(self):
        req = self.proc.get_required_consents('smartlife', 'JP')
        self.assertIn('privacy_policy', req)
        self.assertNotIn('gdpr_rights_acknowledged', req)

    # 4
    def test_travel_fr_includes_gdpr(self):
        req = self.proc.get_required_consents('travel', 'FR')
        self.assertIn('gdpr_rights_acknowledged', req)

    # 5
    def test_unknown_service_returns_empty_plus_gdpr_if_eu(self):
        req = self.proc.get_required_consents('unknown', 'JP')
        self.assertEqual(req, [])

    # 6
    def test_eea_no_includes_gdpr(self):
        req = self.proc.get_required_consents('sbds', 'NO')
        self.assertIn('gdpr_rights_acknowledged', req)


class TestValidateMinor(unittest.TestCase):

    def setUp(self):
        self.proc = ConsentFlowProcessor()

    # 7
    def test_not_minor_no_errors(self):
        req = make_req(is_minor=False)
        errors = self.proc.validate_minor(req)
        self.assertEqual(errors, [])

    # 8
    def test_minor_no_method_errors(self):
        req = make_req(is_minor=True, guardian_consent_method='', guardian_name='田中一郎')
        errors = self.proc.validate_minor(req)
        self.assertTrue(any('guardian_consent_method' in e for e in errors))

    # 9
    def test_minor_no_name_errors(self):
        req = make_req(is_minor=True, guardian_consent_method='accompanied', guardian_name='')
        errors = self.proc.validate_minor(req)
        self.assertTrue(any('guardian_name' in e for e in errors))

    # 10
    def test_minor_accompanied_with_name_ok(self):
        req = make_req(is_minor=True, guardian_consent_method='accompanied', guardian_name='田中一郎')
        errors = self.proc.validate_minor(req)
        self.assertEqual(errors, [])

    # 11
    def test_minor_written_with_name_ok(self):
        req = make_req(is_minor=True, guardian_consent_method='written', guardian_name='鈴木花子')
        errors = self.proc.validate_minor(req)
        self.assertEqual(errors, [])

    # 12
    def test_minor_invalid_method_errors(self):
        req = make_req(is_minor=True, guardian_consent_method='email', guardian_name='田中一郎')
        errors = self.proc.validate_minor(req)
        self.assertTrue(len(errors) >= 1)


class TestProcessRegistrationSBDS(unittest.TestCase):

    def setUp(self):
        self.cm = ConsentManager()
        self.proc = ConsentFlowProcessor(consent_manager=self.cm)

    # 13
    def test_required_consent_missing_fails(self):
        req = make_req(consents={'privacy_policy': False})
        result = self.proc.process_registration(req)
        self.assertFalse(result.success)
        self.assertTrue(any('privacy_policy' in e for e in result.errors))

    # 14
    def test_required_consent_granted_success(self):
        req = make_req(consents={'privacy_policy': True})
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)
        self.assertIn('privacy_policy', result.granted_consents)

    # 15
    def test_optional_skipped_success(self):
        req = make_req(consents={'privacy_policy': True, 'delivery_preference': False, 'line_integration': False})
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)
        self.assertIn('delivery_preference', result.skipped_consents)
        self.assertIn('line_integration', result.skipped_consents)

    # 16
    def test_optional_granted_included(self):
        req = make_req(consents={'privacy_policy': True, 'delivery_preference': True})
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)
        self.assertIn('delivery_preference', result.granted_consents)

    # 17
    def test_consent_manager_grant_called(self):
        req = make_req(consents={'privacy_policy': True})
        result = self.proc.process_registration(req)
        self.assertTrue(self.cm.is_granted('user-001', 'sbds', 'privacy_policy'))

    # 18
    def test_optional_not_granted_cm_not_granted(self):
        req = make_req(consents={'privacy_policy': True, 'delivery_preference': False})
        self.proc.process_registration(req)
        self.assertFalse(self.cm.is_granted('user-001', 'sbds', 'delivery_preference'))

    # 19
    def test_jp_gdpr_not_applicable(self):
        req = make_req(country_code='JP', consents={'privacy_policy': True})
        result = self.proc.process_registration(req)
        self.assertFalse(result.gdpr_applicable)

    # 20
    def test_de_gdpr_applicable_requires_gdpr_consent(self):
        req = make_req(
            country_code='DE',
            consents={'privacy_policy': True}  # missing gdpr_rights_acknowledged
        )
        result = self.proc.process_registration(req)
        self.assertFalse(result.success)
        self.assertTrue(any('gdpr_rights_acknowledged' in e for e in result.errors))

    # 21
    def test_de_gdpr_with_consent_success(self):
        req = make_req(
            country_code='DE',
            consents={'privacy_policy': True, 'gdpr_rights_acknowledged': True}
        )
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)
        self.assertTrue(result.gdpr_applicable)
        self.assertIn('gdpr_rights_acknowledged', result.granted_consents)

    # 22
    def test_errors_empty_on_success(self):
        req = make_req(consents={'privacy_policy': True})
        result = self.proc.process_registration(req)
        self.assertEqual(result.errors, [])

    # 23
    def test_multiple_required_errors(self):
        req = make_req(
            country_code='DE',
            consents={'privacy_policy': False, 'gdpr_rights_acknowledged': False}
        )
        result = self.proc.process_registration(req)
        self.assertFalse(result.success)
        self.assertGreaterEqual(len(result.errors), 2)

    # 24
    def test_minor_missing_guardian_fails(self):
        req = make_req(
            consents={'privacy_policy': True},
            is_minor=True,
            guardian_consent_method='',
            guardian_name=''
        )
        result = self.proc.process_registration(req)
        self.assertFalse(result.success)
        self.assertGreater(len(result.errors), 0)

    # 25
    def test_minor_accompanied_with_name_success(self):
        req = make_req(
            consents={'privacy_policy': True},
            is_minor=True,
            guardian_consent_method='accompanied',
            guardian_name='田中一郎'
        )
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)

    # 26
    def test_result_fields(self):
        req = make_req(consents={'privacy_policy': True})
        result = self.proc.process_registration(req)
        self.assertEqual(result.user_id, 'user-001')
        self.assertEqual(result.service, 'sbds')
        self.assertIsInstance(result.granted_consents, list)
        self.assertIsInstance(result.skipped_consents, list)
        self.assertIsInstance(result.errors, list)


class TestProcessRegistrationSmartLife(unittest.TestCase):

    def setUp(self):
        self.cm = ConsentManager()
        self.proc = ConsentFlowProcessor(consent_manager=self.cm)

    # 27
    def test_smartlife_required_missing_fails(self):
        req = make_req(service='smartlife', consents={'privacy_policy': False})
        result = self.proc.process_registration(req)
        self.assertFalse(result.success)

    # 28
    def test_smartlife_ai_learning_not_granted_skipped(self):
        req = make_req(
            service='smartlife',
            consents={'privacy_policy': True, 'ai_learning': False, 'marketing_communication': False}
        )
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)
        self.assertIn('ai_learning', result.skipped_consents)
        self.assertFalse(self.cm.is_granted('user-001', 'smartlife', 'ai_learning'))

    # 29
    def test_smartlife_ai_learning_granted(self):
        req = make_req(
            service='smartlife',
            consents={'privacy_policy': True, 'ai_learning': True}
        )
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)
        self.assertIn('ai_learning', result.granted_consents)
        self.assertTrue(self.cm.is_granted('user-001', 'smartlife', 'ai_learning'))

    # 30
    def test_smartlife_marketing_skipped(self):
        req = make_req(
            service='smartlife',
            consents={'privacy_policy': True, 'marketing_communication': False}
        )
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)
        self.assertIn('marketing_communication', result.skipped_consents)


class TestProcessRegistrationTravel(unittest.TestCase):

    def setUp(self):
        self.cm = ConsentManager()
        self.proc = ConsentFlowProcessor(consent_manager=self.cm)

    # 31
    def test_travel_location_granted_in_granted_consents(self):
        req = make_req(
            service='travel',
            consents={'privacy_policy': True, 'location_info_travel': True}
        )
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)
        self.assertIn('location_info_travel', result.granted_consents)

    # 32
    def test_travel_location_not_granted_skipped(self):
        req = make_req(
            service='travel',
            consents={'privacy_policy': True, 'location_info_travel': False}
        )
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)
        self.assertIn('location_info_travel', result.skipped_consents)
        self.assertNotIn('location_info_travel', result.granted_consents)

    # 33
    def test_travel_privacy_missing_fails(self):
        req = make_req(
            service='travel',
            consents={'privacy_policy': False, 'location_info_travel': True}
        )
        result = self.proc.process_registration(req)
        self.assertFalse(result.success)
        self.assertTrue(any('privacy_policy' in e for e in result.errors))

    # 34
    def test_travel_eu_gdpr_required(self):
        req = make_req(
            service='travel',
            country_code='FR',
            consents={'privacy_policy': True, 'gdpr_rights_acknowledged': False}
        )
        result = self.proc.process_registration(req)
        self.assertFalse(result.success)

    # 35
    def test_travel_eu_gdpr_success(self):
        req = make_req(
            service='travel',
            country_code='FR',
            consents={'privacy_policy': True, 'gdpr_rights_acknowledged': True, 'location_info_travel': True}
        )
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)
        self.assertTrue(result.gdpr_applicable)

    # 36
    def test_travel_location_tracking_logic(self):
        """location_info_travel 同意 → granted_consents に含まれる (APIレイヤーでlocation_tracking_enabledをTrueにする)"""
        req = make_req(
            service='travel',
            consents={'privacy_policy': True, 'location_info_travel': True}
        )
        result = self.proc.process_registration(req)
        location_tracking_enabled = 'location_info_travel' in result.granted_consents
        self.assertTrue(location_tracking_enabled)

    # 37
    def test_travel_location_not_tracking_when_skipped(self):
        req = make_req(
            service='travel',
            consents={'privacy_policy': True, 'location_info_travel': False}
        )
        result = self.proc.process_registration(req)
        location_tracking_enabled = 'location_info_travel' in result.granted_consents
        self.assertFalse(location_tracking_enabled)


class TestProcessRegistrationMinorEdgeCases(unittest.TestCase):

    def setUp(self):
        self.cm = ConsentManager()
        self.proc = ConsentFlowProcessor(consent_manager=self.cm)

    # 38
    def test_minor_written_with_name_success(self):
        req = make_req(
            consents={'privacy_policy': True},
            is_minor=True,
            guardian_consent_method='written',
            guardian_name='山田花子'
        )
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)

    # 39
    def test_minor_whitespace_name_fails(self):
        req = make_req(
            consents={'privacy_policy': True},
            is_minor=True,
            guardian_consent_method='accompanied',
            guardian_name='   '
        )
        result = self.proc.process_registration(req)
        self.assertFalse(result.success)

    # 40
    def test_not_minor_no_guardian_needed(self):
        req = make_req(
            consents={'privacy_policy': True},
            is_minor=False,
            guardian_consent_method='',
            guardian_name=''
        )
        result = self.proc.process_registration(req)
        self.assertTrue(result.success)


class TestDefaultConsentManager(unittest.TestCase):

    # 41
    def test_default_consent_manager_created(self):
        proc = ConsentFlowProcessor()
        self.assertIsInstance(proc._cm, ConsentManager)

    # 42
    def test_custom_consent_manager_used(self):
        cm = ConsentManager()
        proc = ConsentFlowProcessor(consent_manager=cm)
        self.assertIs(proc._cm, cm)


if __name__ == '__main__':
    unittest.main()
