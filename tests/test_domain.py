import unittest
from app.domain import (interpret_card, interpret_preview, interpret_matrix_observation,
                       matrix_business_key, PREVIEW_AVAILABLE, PREVIEW_QUOTA_PENDING,
                       PREVIEW_TRANSIENT_ERROR, PREVIEW_NOT_OBSERVED,
                       STATE_CONFIRMED, STATE_UNKNOWN)
from app.site import DATA

class DomainCardTest(unittest.TestCase):
    def test_catalog_fact_keeps_business_condition(self):
        item = DATA['items'][0]
        fact = interpret_card(item)
        self.assertEqual(fact['identity'], item['id'])
        self.assertEqual(fact['condition'], item['choices'][0])
        self.assertEqual(fact['kind'], 'benefit')

    def test_malformed_card_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            interpret_card({'id':'unknown','summary':'incomplete'})


class MatrixObservationTest(unittest.TestCase):
    def _catalog_fact(self):
        return {'kind': 'benefit', 'identity': 'merchant-01', 'condition': '网球票'}

    def _observed(self, city='北京', ticket='演出票', merchant='merchant-01'):
        return {'city': city, 'ticket': ticket, 'merchant': merchant}

    def test_business_key_keeps_ticket_category_distinct(self):
        self.assertNotEqual(
            matrix_business_key('北京', 'merchant-01', '网球票'),
            matrix_business_key('北京', 'merchant-01', '演出票'))

    def test_empty_preview_is_unknown_not_no_benefit(self):
        self.assertEqual(interpret_preview(''), PREVIEW_NOT_OBSERVED)
        result = interpret_matrix_observation(
            self._catalog_fact(),
            {'city': '北京', 'ticket': '演出票'},
            self._observed(), {'voucher': '', 'scope': '', 'merchant_detail': '',
                               'attempts': 1})
        self.assertEqual(result['state'], STATE_UNKNOWN)
        self.assertIn('preview_not_observed', result['reasons'])
        self.assertTrue(result['evidence_only'])
        self.assertFalse(result['claim_submitted'])

    def test_confirmed_only_when_coordinates_match_and_preview_recognized(self):
        result = interpret_matrix_observation(
            self._catalog_fact(),
            {'city': '江苏', 'ticket': '演出票'},
            self._observed(city='江苏', ticket='演出票'),
            {'voucher': '江苏 / 演出票 / 名额待核', 'scope': '',
             'merchant_detail': '演出票资格待核', 'attempts': 1})
        self.assertEqual(result['state'], STATE_CONFIRMED)
        self.assertEqual(result['preview_status'], PREVIEW_QUOTA_PENDING)

    def test_ticket_reset_marks_unknown_and_keeps_observed_scope(self):
        result = interpret_matrix_observation(
            self._catalog_fact(),
            {'city': '北京', 'ticket': '演出票'},
            self._observed(ticket='网球票'),
            {'voucher': '北京 / 网球票 / 可领取', 'scope': '条款已见',
             'merchant_detail': '可凭网球票核对', 'attempts': 1})
        self.assertEqual(result['state'], STATE_UNKNOWN)
        self.assertIn('ticket_filter_reset', result['reasons'])
        # 网球票的“可领取”结论不得被挪用给请求的演出票格。
        self.assertEqual(result['preview_status'], PREVIEW_AVAILABLE)
        self.assertEqual(result['requested_ticket'], '演出票')
        self.assertEqual(result['observed_ticket'], '网球票')

    def test_cross_city_redirect_is_unknown(self):
        result = interpret_matrix_observation(
            self._catalog_fact(),
            {'city': '北京', 'ticket': '网球票'},
            self._observed(city='江苏', ticket='网球票'),
            {'voucher': '江苏 / 网球票 / 可领取', 'scope': '',
             'merchant_detail': '', 'attempts': 1})
        self.assertEqual(result['state'], STATE_UNKNOWN)
        self.assertIn('city_redirected', result['reasons'])

    def test_transient_error_then_recovery_is_confirmed_on_second_attempt(self):
        first = interpret_matrix_observation(
            self._catalog_fact(),
            {'city': '北京', 'ticket': '网球票'}, self._observed(),
            {'voucher': '北京 / 网球票 / 系统繁忙请稍后重试', 'scope': '',
             'merchant_detail': '', 'attempts': 1})
        self.assertEqual(first['preview_status'], PREVIEW_TRANSIENT_ERROR)
        self.assertEqual(first['state'], STATE_UNKNOWN)
        recovered = interpret_matrix_observation(
            self._catalog_fact(),
            {'city': '北京', 'ticket': '网球票'},
            self._observed(ticket='网球票'),
            {'voucher': '北京 / 网球票 / 可领取', 'scope': '条款已见',
             'merchant_detail': '可凭网球票核对', 'attempts': 2, 'recovered': True})
        self.assertEqual(recovered['state'], STATE_CONFIRMED)
        self.assertTrue(recovered['recovered_after_retry'])

    def test_merchant_mismatch_is_unknown(self):
        result = interpret_matrix_observation(
            self._catalog_fact(),
            {'city': '北京', 'ticket': '网球票'},
            self._observed(merchant='merchant-02'),
            {'voucher': '可领取', 'scope': '', 'merchant_detail': '', 'attempts': 1})
        self.assertEqual(result['state'], STATE_UNKNOWN)
        self.assertIn('merchant_identity_mismatch', result['reasons'])
