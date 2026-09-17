# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The reading of the VTV Sales & Services planning files.

Parser cases run everywhere. The dataset cases need the customer's files, which
are never committed, and skip without them.

Run:  python -m unittest discover -s tools/tests -t .
"""
import importlib.util
import pathlib
import re
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('extract_kddv', _REPO / 'tools' / 'extract_kddv.py')
extract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extract)


class ParseNumberCase(unittest.TestCase):

    def test_vietnamese_decimal_comma(self):
        self.assertEqual(extract.parse_number('49,15'), 49.15)
        self.assertEqual(extract.parse_number('0,20'), 0.2)

    def test_dot_groups_thousands(self):
        self.assertEqual(extract.parse_number('2.600'), 2600.0)
        self.assertEqual(extract.parse_number('15.000'), 15000.0)

    def test_plain_integer(self):
        self.assertEqual(extract.parse_number('93'), 93.0)


class ParseMonthTargetCase(unittest.TestCase):

    def check(self, text, direction, target):
        parsed = extract.parse_month_target(text)
        self.assertEqual((parsed['direction'], parsed['target']), (direction, target), text)
        self.assertEqual(parsed['note'], text)

    def test_at_least_keeps_the_explanation(self):
        self.check('≥ 21,92 tỷ (gốc 20,92 + 1,00 bổ sung)', 'higher', 21.92)

    def test_at_most_is_lower_is_better(self):
        self.check('≤ 8%', 'lower', 8.0)
        self.check('≤ 15.000đ', 'lower', 15000.0)

    def test_zero_incidents_is_zero_tolerance(self):
        self.check('0', 'lower', 0.0)
        self.check('0 (audit T7)', 'lower', 0.0)

    def test_growth_and_ratio(self):
        self.check('+7% vs Q2', 'higher', 7.0)
        self.check('≥ 3:1', 'higher', 3.0)
        self.check('≥ 2.600 đ', 'higher', 2600.0)

    def test_full_attainment(self):
        self.check('100% (4–5 tuần T7)', 'higher', 100.0)

    def test_wording_is_a_milestone(self):
        self.check('Dự thảo 3 quy trình (Telco/VTVshop/DVsố)', 'boolean', 1.0)
        self.check('Thu hồi lũy kế ≥ 2–3 đối tác', 'boolean', 1.0)

    def test_dash_means_not_assigned_that_month(self):
        for text in ('—', '-', '', None):
            self.assertIsNone(extract.parse_month_target(text))


class KrReferenceCase(unittest.TestCase):

    def test_several_references_in_order_without_repeats(self):
        self.assertEqual(extract.parse_kr_refs('O1-KR1 (MG) + O1-KR2 (B2C 10%)'), ['O1.KR1', 'O1.KR2'])
        self.assertEqual(extract.parse_kr_refs('O3-KR1 + O1-KR2 + O3-KR1'), ['O3.KR1', 'O1.KR2'])

    def test_no_reference(self):
        self.assertEqual(extract.parse_kr_refs('Hỗ trợ toàn bộ OKR Q3'), [])


class MonthLinesCase(unittest.TestCase):

    def test_missing_line_rescales_the_rest_to_100(self):
        group = {'lines': [
            {'code': 'a', 'weight_in_group': 45.0, 'months': {'7': {'target': 90}, '9': {'target': 90}}},
            {'code': 'b', 'weight_in_group': 35.0, 'months': {'7': {'target': 5}, '9': {'target': 5}}},
            {'code': 'c', 'weight_in_group': 20.0, 'months': {'7': None, '9': {'target': 20}}},
        ]}
        july = extract.month_lines(group, 7)
        self.assertEqual([line['code'] for line in july], ['a', 'b'])
        self.assertAlmostEqual(sum(line['month_weight_in_group'] for line in july), 100.0, places=2)
        self.assertEqual([line['month_weight_in_group'] for line in extract.month_lines(group, 9)],
                         [45.0, 35.0, 20.0])


_SOURCE = extract.DEFAULT_SOURCE


@unittest.skipUnless((_SOURCE / extract.KPI_FILE).exists(), 'customer files are not in the repository')
class DatasetCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data = extract.build(_SOURCE)

    def test_organisation(self):
        self.assertEqual(len(self.data['departments']), 6)
        self.assertEqual(len(self.data['employees']), 21)
        self.assertEqual(len({e['email'] for e in self.data['employees']}), 21)
        self.assertEqual(len(self.data['positions']), 13)

    def test_every_employee_has_a_position_and_a_manager_chain(self):
        for employee in self.data['employees']:
            self.assertTrue(employee['position'], employee['name'])
        head = [e for e in self.data['employees'] if e['manager'] is None]
        self.assertEqual([e['name'] for e in head], ['Trần Ngọc Tú'])

    def test_special_cases(self):
        by_name = {e['name']: e for e in self.data['employees']}
        self.assertEqual(by_name['Nguyễn Đình Hải']['kpi_months'], [])
        self.assertEqual(by_name['Đinh Duy Phương']['kpi_months'], [9])
        self.assertEqual({e['name'] for e in self.data['employees'] if e['performance_role'] == 'manager'},
                         {'Trần Ngọc Tú', 'Lưu Quý Hiểu', 'Phạm Tuấn Bình'})

    def test_scorecard_count(self):
        per_month = {m: sum(1 for s in self.data['scorecards'] if s['month'] == m) for m in (7, 8, 9)}
        self.assertEqual(per_month, {7: 19, 8: 19, 9: 20})

    def test_every_scorecard_weighs_100_at_both_levels(self):
        for card in self.data['scorecards']:
            label = '%s T%s' % (card['employee'], card['month'])
            self.assertAlmostEqual(sum(g['weight'] for g in card['groups']), 100.0, places=2, msg=label)
            for group in card['groups']:
                self.assertTrue(group['lines'], label)
                self.assertAlmostEqual(sum(l['month_weight_in_group'] for l in group['lines']), 100.0,
                                       places=1, msg='%s %s' % (label, group['code']))

    def test_monthly_revenue_matches_the_signed_plan(self):
        sheet = self.data['kpi_sheets']['TP-KD']
        total = sheet[0]['lines'][0]['months']
        self.assertEqual([total[m]['target'] for m in ('7', '8', '9')], [49.15, 50.27, 51.14])
        self.assertAlmostEqual(sum(total[m]['target'] for m in ('7', '8', '9')), 150.56, places=2)

    def test_objective_and_kr_weights(self):
        objectives = self.data['objectives']
        self.assertEqual(sum(o['weight'] for o in objectives), 100.0)
        self.assertEqual(sum(len(o['key_results']) for o in objectives), 10)
        for objective in objectives:
            self.assertAlmostEqual(sum(kr['weight'] for kr in objective['key_results']), objective['weight'])

    def test_kr_references_point_at_real_key_results(self):
        known = {kr['code'] for o in self.data['objectives'] for kr in o['key_results']}
        for position, groups in self.data['kpi_sheets'].items():
            for group in groups:
                for line in group['lines']:
                    for code in line['kr_codes']:
                        self.assertIn(code, known, '%s %s' % (position, line['code']))

    def test_okr_wording_is_taken_from_the_signed_decision(self):
        try:
            import pypdf
        except ImportError:
            self.skipTest('pypdf not installed')
        text = ' '.join(page.extract_text() for page in pypdf.PdfReader(_SOURCE / extract.OKR_FILE).pages)
        flat = re.sub(r'\s+', '', text)
        for objective in self.data['objectives']:
            for kr in objective['key_results']:
                self.assertIn(re.sub(r'\s+', '', kr['name']), flat, kr['code'])
                self.assertIn(re.sub(r'\s+', '', kr['criterion']), flat, kr['code'])


if __name__ == '__main__':
    unittest.main()
