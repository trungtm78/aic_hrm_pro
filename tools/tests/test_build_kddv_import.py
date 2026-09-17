# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Monthly import workbooks built from the extracted plan."""
import importlib.util
import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _REPO / 'tools' / ('%s.py' % name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = _load('build_kddv_import')
extract = _load('extract_kddv')

DATASET = {
    'year': 2026,
    'positions': [{'code': 'CV', 'title': 'Chuyên viên'}],
    'scorecards': [
        {'month': month, 'employee': person, 'position': 'CV', 'groups': [
            {'code': 'B.I', 'name': 'KPI DOANH THU', 'weight': 80.0, 'lines': [
                {'code': 'B1.1', 'name': 'Revenue', 'unit': 'tỷ VNĐ', 'month_weight_in_group': 100.0,
                 'target': {'direction': 'higher', 'target': 21.92, 'note': '≥ 21,92 tỷ'},
                 'kr_codes': ['O1.KR1', 'O3.KR2'], 'basis': 'ĐỀ XUẤT', 'okr_link': 'O1-KR1 + O3-KR2',
                 'measurement': 'Contract system'}]},
            {'code': 'B.II', 'name': 'KPI QUẢN TRỊ', 'weight': 20.0, 'lines': [
                {'code': 'B2.1', 'name': 'Incidents', 'unit': 'vụ', 'month_weight_in_group': 100.0,
                 'target': {'direction': 'lower', 'target': 0.0, 'note': '0'},
                 'kr_codes': [], 'basis': None, 'okr_link': None, 'measurement': 'Log'}]},
        ]}
        for month in (7, 9) for person in (['An'] if month == 7 else ['An', 'Bình'])
    ],
}


class MonthRowsCase(unittest.TestCase):

    def test_one_assignment_row_per_position_naming_everyone(self):
        _kpis, july = build.month_rows(DATASET, 7)
        _kpis, september = build.month_rows(DATASET, 9)
        self.assertEqual(july[0][1], 'An')
        self.assertEqual(september[0][1], 'An, Bình')
        self.assertEqual(september[0][5], 'KDDV.CV.B1.1,KDDV.CV.B2.1')

    def test_kpi_row_carries_both_weight_levels_and_the_first_key_result(self):
        kpis, _assign = build.month_rows(DATASET, 7)
        revenue, incidents = kpis
        self.assertEqual(revenue[0], 'KDDV.CV.B1.1')
        self.assertEqual(revenue[1], 'B.I — KPI DOANH THU')
        self.assertEqual(revenue[4], 'Càng cao càng tốt')
        self.assertEqual(revenue[7], 80.0)
        self.assertEqual(revenue[12:16], [80.0, 100.0, 'O1.KR1', '≥ 21,92 tỷ'])
        self.assertIn('O1-KR1 + O3-KR2', revenue[11])
        self.assertEqual(incidents[4], 'Càng thấp càng tốt')
        self.assertEqual((incidents[8], incidents[14]), (0.0, ''))

    def test_no_row_for_a_month_nobody_is_assigned(self):
        self.assertEqual(build.month_rows(DATASET, 8), ([], []))


_SOURCE = extract.DEFAULT_SOURCE


@unittest.skipUnless((_SOURCE / extract.KPI_FILE).exists(), 'customer files are not in the repository')
class RealPlanCase(unittest.TestCase):

    def test_every_month_weighs_100_per_person(self):
        data = extract.build(_SOURCE)
        for month, people in ((7, 19), (8, 19), (9, 20)):
            kpis, assign = build.month_rows(data, month)
            self.assertEqual(sum(len(row[1].split(', ')) for row in assign), people)
            weight = {row[0]: row[7] for row in kpis}
            for row in assign:
                total = sum(weight[code] for code in row[5].split(','))
                self.assertAlmostEqual(total, 100.0, places=2, msg='T%s %s' % (month, row[2]))


if __name__ == '__main__':
    unittest.main()
