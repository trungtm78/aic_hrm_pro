# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Actuals import files for the Sales & Services department.

Uses small hand-made datasets, so it runs without the customer's files.

Run:  python -m unittest discover -s tools/tests -t .
"""
import importlib.util
import pathlib
import tempfile
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    'build_kddv_actuals_import', _REPO / 'tools' / 'build_kddv_actuals_import.py')
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

PLAN = {'scorecards': [
    {'month': 7, 'position': 'CV-KD1', 'employee': 'B Person'},
    {'month': 7, 'position': 'CV-KD1', 'employee': 'A Person'},
    {'month': 8, 'position': 'CV-KD1', 'employee': 'A Person'},
]}
ACTUALS = {
    'year': 2026, 'months_with_revenue': [7, 8],
    'kpi_actuals': [
        {'month': 7, 'position': 'CV-KD1', 'code': 'KDDV.CV-KD1.B1.1', 'value': 38.03, 'note': 'jul'},
        {'month': 8, 'position': 'CV-KD1', 'code': 'KDDV.CV-KD1.B1.1', 'value': 43.99, 'note': 'aug'},
    ],
    'tracking': [
        {'month': 7, 'code': 'KDDV.PHONG.CP', 'value': 18.446, 'note': 'cost'},
        {'month': 8, 'code': 'KDDV.PHONG.CP', 'value': None, 'note': 'no data'},
    ],
    'kr_checkins': [{'code': 'O1.KR1', 'value': 209.77, 'note': 'q3'}],
}


class BuildCase(unittest.TestCase):

    def setUp(self):
        self.files = build.files(ACTUALS, PLAN)

    def test_one_file_per_month_and_one_for_the_quarter(self):
        self.assertEqual(sorted(self.files), [
            'KDDV_THUC_TE_Q3_2026.xlsx', 'KDDV_THUC_TE_T7_2026.xlsx', 'KDDV_THUC_TE_T8_2026.xlsx'])

    def test_every_holder_of_the_line_gets_the_actual(self):
        july = [row for row in self.files['KDDV_THUC_TE_T7_2026.xlsx'] if row[1] == 'KDDV.CV-KD1.B1.1']
        self.assertEqual([row[2] for row in july], ['A Person', 'B Person'])
        self.assertEqual(july[0], ['kpi', 'KDDV.CV-KD1.B1.1', 'A Person', '2026-07-01', '2026-07-31', 38.03, 'jul'])

    def test_tracking_without_owner_and_missing_values_left_out(self):
        july = self.files['KDDV_THUC_TE_T7_2026.xlsx']
        self.assertIn(['kpi', 'KDDV.PHONG.CP', '', '2026-07-01', '2026-07-31', 18.446, 'cost'], july)
        august_codes = [row[1] for row in self.files['KDDV_THUC_TE_T8_2026.xlsx']]
        self.assertNotIn('KDDV.PHONG.CP', august_codes)

    def test_key_result_checkin_dated_end_of_last_month_with_data(self):
        self.assertEqual(self.files['KDDV_THUC_TE_Q3_2026.xlsx'],
                         [['kr', 'O1.KR1', '', '2026-08-31', '2026-08-31', 209.77, 'q3']])

    def test_position_without_scorecard_is_an_error(self):
        actuals = dict(ACTUALS, kpi_actuals=[dict(ACTUALS['kpi_actuals'][0], position='QP')])
        with self.assertRaises(ValueError):
            build.files(actuals, PLAN)

    def test_written_workbooks_start_with_the_wizard_header(self):
        import openpyxl
        with tempfile.TemporaryDirectory() as folder:
            names = build.write(self.files, folder)
            sheet = openpyxl.load_workbook(pathlib.Path(folder) / names[0]).active
            self.assertEqual([cell.value for cell in sheet[1]], build.HEADER)
