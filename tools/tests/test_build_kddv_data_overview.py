# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Rendering of the "what data is in the system" page.

The page reads production over RPC; here only the rendering is exercised, with
a hand-made dataset, so the tests need no network.

Run:  python -m unittest discover -s tools/tests -t .
"""
import importlib.util
import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    'build_kddv_data_overview', _REPO / 'tools' / 'build_kddv_data_overview.py')
overview = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(overview)


def dataset():
    objective = {'id': 1, 'code': 'O1', 'name': 'Doanh thu', 'weight': 50.0, 'score': 0.7,
                 'score_covered': 1.0, 'data_coverage': 70.0, 'employee_id': [1, 'TP'], 'state': 'in_progress'}
    krs = [
        {'id': 11, 'code': 'O1.KR1', 'name': 'Doanh thu quý', 'weight': 35.0, 'metric_type': 'number',
         'target': 150.56, 'current': 209.77, 'unit': 'tỷ VNĐ', 'score': 1.0, 'has_actual': True,
         'deadline': '2026-09-30', 'objective_id': [1, 'Doanh thu'], 'milestone_ids': [], 'note': ''},
        {'id': 12, 'code': 'O1.KR2', 'name': 'Ra mắt B2C', 'weight': 10.0, 'metric_type': 'milestone',
         'target': 0.0, 'current': 0.0, 'unit': False, 'score': 0.0, 'has_actual': False,
         'deadline': '2026-09-07', 'objective_id': [1, 'Doanh thu'], 'milestone_ids': [1, 2], 'note': ''},
    ]
    card = {'employee_id': [5, 'Trần Ngọc Tú'], 'job_note': 'TP-KD', 'score': 0.8, 'score_covered': 1.0,
            'data_coverage': 80.0, 'total_weight': 100.0, 'line_ids': [1, 2, 3], 'state': 'draft'}
    empty = {'employee_id': [6, 'Quay phim'], 'job_note': 'QP', 'score': 0.0, 'score_covered': 0.0,
             'data_coverage': 0.0, 'total_weight': 100.0, 'line_ids': [4], 'state': 'draft'}
    return {
        'company': {'name': 'Trung tâm', 'currency_id': [1, 'VND'], 'chart_template': 'vn'},
        'departments': [{'name': 'Kinh doanh và Dịch vụ', 'manager_id': [1, 'TP']}],
        'staff': [{'name': 'Trần Ngọc Tú', 'job_title': 'Trưởng phòng', 'barcode': 'KDDV01',
                   'work_email': 'tu@example.com', 'parent_id': False}],
        'users': 22, 'milestones': 18, 'groups': 116, 'lines': 412, 'lines_measured': 36,
        'targets': 418, 'kpis': 90, 'confirmed': 38,
        'labels': {'cycle_type': {'year': 'Năm', 'month': 'Tháng'}, 'state': {'open': 'Đang mở'}},
        'cycles': [{'code': 'KDDV-2026', 'name': 'Năm 2026', 'cycle_type': 'year', 'date_start': '2026-01-01',
                    'date_end': '2026-12-31', 'state': 'open', 'parent_id': False}],
        'objectives': [objective], 'krs': krs,
        'cards': {7: [card, empty], 8: [card], 9: []},
        'sources': [{'name': 'KDDV — DT', 'field_name': 'balance', 'multiplier': -1e-9, 'domain': "[('x','=',1)]"}],
        'tracking': [{'kpi_id': [1, 'Chi phí'], 'cycle_id': [2, 'Tháng 7/2026'], 'unit': 'tỷ VNĐ',
                      'actual_value': 18.446, 'has_actual': True},
                     {'kpi_id': [1, 'Chi phí'], 'cycle_id': [3, 'Tháng 8/2026'], 'unit': 'tỷ VNĐ',
                      'actual_value': 0.0, 'has_actual': False}],
        'invoices': [{'invoice_date': '2026-07-31', 'amount_untaxed': 1000.0, 'amount_tax': 80.0},
                     {'invoice_date': '2026-07-15', 'amount_untaxed': 500.0, 'amount_tax': 40.0},
                     {'invoice_date': '2026-08-31', 'amount_untaxed': 200.0, 'amount_tax': 16.0}],
        'entries': [{'ref': 'CPTH2026-T07', 'date': '2026-07-31', 'journal_id': [1, 'Chi phí tổng hợp'],
                     'amount_total': 18445937012.0}],
        'revenue_targets': [{'kpi_id': [1, 'Tổng doanh thu Phòng'], 'cycle_id': [2, 'Tháng 7/2026'],
                             'employee_id': [5, 'Trần Ngọc Tú'], 'target_value': 49.15,
                             'actual_value': 108.24, 'achievement': 1.0, 'unit': 'tỷ VNĐ'}],
        'unmeasured': [{'kpi_target_id': [9, 'MAU VTVgo · Trần Ngọc Tú'], 'assignment_id': [3, 'Trần Ngọc Tú · KDDV-2026-07']},
                       {'kpi_target_id': [9, 'MAU VTVgo · Phạm Tuấn Bình'], 'assignment_id': [4, 'Phạm Tuấn Bình · KDDV-2026-07']}],
    }


class HelperCase(unittest.TestCase):

    def test_escapes_text_from_the_database(self):
        rendered = overview.table(['A & B'], [['<script>x</script>']])
        self.assertIn('A &amp; B', rendered)
        self.assertNotIn('<script>', rendered)

    def test_invoices_are_grouped_by_month_in_order(self):
        months = overview.invoice_months(dataset())
        self.assertEqual(list(months), ['2026-07', '2026-08'])
        self.assertEqual(months['2026-07'], {'count': 2, 'untaxed': 1500.0, 'tax': 120.0})


class ChecklistCase(unittest.TestCase):

    def setUp(self):
        self.rows = overview.checklist(dataset())

    def test_every_row_carries_a_status_badge(self):
        self.assertTrue(all('badge' in row[-1] for row in self.rows))

    def test_the_months_that_are_scored_are_named(self):
        row = [row for row in self.rows if row[0] == 'Số thực tế đã xác nhận'][0]
        self.assertIn('38', row[1])
        self.assertIn('7, 8', row[1])

    def test_kpis_without_figures_are_marked_as_waiting(self):
        row = [row for row in self.rows if row[0] == 'KPI ngoài doanh thu'][0]
        self.assertIn('Chờ số liệu', row[-1])


class PageCase(unittest.TestCase):

    def setUp(self):
        self.page = overview.render(dataset(), '18/09/2026 01:00')

    def test_key_result_rows_show_target_actual_and_data_state(self):
        rows = overview.okr_rows(dataset())
        self.assertEqual(len(rows), 3)  # one objective and its two key results
        self.assertIn('209,77', ''.join(rows[1]))
        self.assertIn('chưa có số liệu', ''.join(rows[2]))
        self.assertIn('mốc công việc', ''.join(rows[2]))

    def test_scorecards_of_every_month_are_listed(self):
        rows = overview.scorecard_rows(dataset())
        self.assertEqual([row[0] for row in rows], ['T7/2026', 'T7/2026', 'T8/2026'])
        self.assertEqual(rows[1][6], '—', 'a scorecard without figures shows no covered score')

    def test_missing_rows_group_people_per_kpi(self):
        rows = overview.missing_rows(dataset())
        self.assertEqual(rows, [['MAU VTVgo', 2, 'Phạm Tuấn Bình, Trần Ngọc Tú']])

    def test_page_is_self_contained_vietnamese_html(self):
        self.assertTrue(self.page.startswith('<!DOCTYPE html>'))
        self.assertIn('<html lang="vi">', self.page)
        self.assertIn('width=device-width', self.page)
        self.assertNotIn('<script', self.page)
        self.assertNotIn('http://', self.page.replace('https://okr.aipower.vn', ''))
        self.assertIn('18/09/2026 01:00', self.page)

    def test_page_answers_the_completeness_question_first(self):
        self.assertLess(self.page.index('Hệ thống đã có đủ dữ liệu chưa?'),
                        self.page.index('Tổ chức và người dùng'))
