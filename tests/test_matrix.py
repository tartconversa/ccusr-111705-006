import sqlite3
import tempfile
import unittest
from pathlib import Path

from test_browser import BrowserBaselineTest
from app.site import DATA
from app.capture import read_matrix_evidence as collect_matrix_evidence
from app.records import (save_matrix_evidence, read_matrix_evidence as load_matrix_evidence,
                         matrix_summary)
from app.review import build_matrix_review


class MatrixEvidenceTest(BrowserBaselineTest):
    def _expected_cells(self):
        return len(DATA['items']) * 2 * 2  # 商户 × 城市 × 票根类别

    def test_matrix_covers_every_city_ticket_cell_without_dedup(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence_dir = Path(directory) / 'artifacts'
            rows = collect_matrix_evidence(self.origin, evidence_dir=evidence_dir)
            self.assertEqual(len(rows), self._expected_cells())
            # 同一商户的不同票根类别必须保留为不同业务键，不得去重。
            keys = {row['detail_fact']['business_key'] for row in rows}
            self.assertEqual(len(keys), self._expected_cells())
            for row in rows:
                self.assertTrue(row['evidence_only'])
                self.assertFalse(row['claim_submitted'])
                self.assertIn(row['requested_ticket'], row['detail_fact']['business_key'])
            # 每格都留下详情与预览的只读快照证据。
            for row in rows:
                self.assertTrue(Path(row['artifacts']['detail']['html']).exists())
                self.assertTrue(Path(row['artifacts']['detail']['screenshot']).exists())
                self.assertTrue(Path(row['artifacts']['preview']['html']).exists())

    def test_stable_portal_confirms_scope_including_quota_pending(self):
        rows = collect_matrix_evidence(self.origin)
        review = build_matrix_review(rows)
        self.assertEqual(review['unknown_cells'], 0)
        self.assertEqual(review['confirmed_cells'], self._expected_cells())
        # 江苏 × 演出票在演练门户中是“名额待核”，仍是已确认的页面结论而非无优惠。
        quota_cells = [c for c in review['cells']
                       if c['requested_city'] == '江苏' and c['requested_ticket'] == '演出票']
        self.assertTrue(quota_cells)
        self.assertTrue(all('名额待核' in c['preview_reading'] or '名额' in c['preview_reading']
                            for c in quota_cells))
        # 网球票各格的商户条款应已见，演出票各格为资格待核。
        terms = {(c['requested_ticket']): c['merchant_terms'] for c in review['cells']}
        self.assertEqual(terms['网球票'], 'terms_seen')
        self.assertEqual(terms['演出票'], 'terms_pending')

    def test_receipt_is_append_only_and_never_merges_categories(self):
        rows = collect_matrix_evidence(self.origin)
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'matrix.sqlite3'
            save_matrix_evidence(database, rows)
            save_matrix_evidence(database, rows)  # 重跑追加，不覆盖
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM matrix_evidence').fetchone()[0],
                                 self._expected_cells() * 2)
                self.assertEqual(
                    db.execute('SELECT count(DISTINCT business_key) FROM matrix_evidence').fetchone()[0],
                    self._expected_cells())
            summary = matrix_summary(database)
            self.assertEqual(summary['state_counts'].get('confirmed'), self._expected_cells() * 2)
            self.assertEqual(summary['unknown_cells'], [])
            loaded = load_matrix_evidence(database)
            self.assertEqual(len(loaded), self._expected_cells() * 2)

    def test_ticket_filter_reset_keeps_confirmed_cells_and_marks_reset_unknown(self):
        rows = collect_matrix_evidence(self.origin, fault='reset')
        review = build_matrix_review(rows)
        # 网球票各格不受影响；演出票各格被重置回首项，必须是 unknown。
        unknown = {c['requested_ticket'] for c in review['cells'] if c['state'] == 'unknown'}
        self.assertEqual(unknown, {'演出票'})
        for cell in review['cells']:
            if cell['state'] == 'unknown':
                self.assertTrue(any('重置' in reason for reason in cell['unknown_reasons']))
                # 页面回读到的是网球票，但该结论绝不能挪用给请求的演出票格。
                self.assertEqual(cell['observed_ticket'], '网球票')
                self.assertEqual(cell['requested_ticket'], '演出票')
                self.assertEqual(cell['cross_category_borrowing'], 'never_used')
            else:
                self.assertEqual(cell['requested_ticket'], '网球票')
        self.assertEqual(review['confirmed_cells'], len(DATA['items']) * 2)

    def test_cross_city_redirect_marks_every_requested_cell_unknown(self):
        rows = collect_matrix_evidence(self.origin, fault='cross-city')
        review = build_matrix_review(rows)
        self.assertEqual(review['confirmed_cells'], 0)
        self.assertEqual(review['unknown_cells'], self._expected_cells())
        for cell in review['cells']:
            self.assertNotEqual(cell['observed_city'], cell['requested_city'])
            self.assertTrue(any('跳转' in reason for reason in cell['unknown_reasons']))

    def test_transient_preview_error_recovers_within_cell_and_records_attempts(self):
        rows = collect_matrix_evidence(self.origin, fault='transient', retries=1)
        review = build_matrix_review(rows)
        self.assertEqual(review['unknown_cells'], 0)
        self.assertTrue(all(c['preview_attempts'] == 2 for c in review['cells']))
        self.assertTrue(all(c['recovered_after_retry'] for c in review['cells']))
        # 已确认范围仍然保留，且业务键与坐标没有漂移。
        for cell in review['cells']:
            self.assertEqual(cell['observed_city'], cell['requested_city'])
            self.assertEqual(cell['observed_ticket'], cell['requested_ticket'])

    def test_transient_preview_without_retry_stays_unknown_not_empty_benefit(self):
        rows = collect_matrix_evidence(self.origin, fault='transient', retries=0)
        review = build_matrix_review(rows)
        self.assertEqual(review['confirmed_cells'], 0)
        self.assertEqual(review['unknown_cells'], self._expected_cells())
        for cell in review['cells']:
            self.assertTrue(any('报错' in reason for reason in cell['unknown_reasons']))
            # 报错文本是短暂故障证据，不是“无优惠”。
            self.assertNotIn('无优惠', cell['preview_reading'])

    def test_non_local_origin_is_rejected(self):
        with self.assertRaises(ValueError):
            collect_matrix_evidence('https://example.com/')

    def test_receipt_rejects_any_claiming_record(self):
        rows = collect_matrix_evidence(self.origin)
        rows[0]['claim_submitted'] = True
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                save_matrix_evidence(Path(directory) / 'bad.sqlite3', rows)


if __name__ == '__main__':
    unittest.main()
