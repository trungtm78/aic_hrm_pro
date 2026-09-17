# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Rendering of the Sales & Services handbook.

The handbook reads production over RPC and embeds screenshots; here only the
rendering is exercised, with a hand-made dataset and a temporary picture, so
the tests need neither network nor the customer's files.

Run:  python -m unittest discover -s tools/tests -t .
"""
import importlib.util
import pathlib
import tempfile
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    'build_kddv_handbook', _REPO / 'tools' / 'build_kddv_handbook.py')
handbook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(handbook)

# Smallest valid PNG, so a figure can be embedded without a real screenshot.
PNG = bytes.fromhex('89504e470d0a1a0a0000000d494844520000000100000001080600000'
                    '01f15c4890000000a49444154789c6300010000050001'
                    '0d0a2db40000000049454e44ae426082')


def target(id_, kpi, cycle, **kw):
    row = {'id': id_, 'kpi_id': [id_, kpi], 'cycle_id': [70 + int(cycle[-2:]), f'Tháng {int(cycle[-2:])}/2026'],
           'employee_id': [5, 'Trần Ngọc Tú'], 'target_value': 21.92, 'actual_value': 38.03,
           'achievement': 1.0, 'unit': 'tỷ VNĐ', 'target_note': '≥ 21,92 tỷ', 'direction': 'higher',
           'has_actual': True, 'is_tracking': False, 'kr_id': False, 'metric_source_id': [1, 'KDDV — DT']}
    row.update(kw)
    return row


def dataset():
    targets = {
        1: target(1, 'DT Tiếp phát sóng kênh Telco/ISP', 'KDDV-2026-07'),
        2: target(2, 'Churn rate VTVgo Plus', 'KDDV-2026-07', target_value=8.0, actual_value=0.0,
                  achievement=0.0, unit='%', direction='lower', has_actual=False, target_note='≤ 8%'),
        3: target(3, 'DT FAST Channel', 'KDDV-2026-07', target_value=0.9, actual_value=0.0, achievement=0.0),
        4: target(4, 'Sản lượng nội dung', 'KDDV-2026-07', target_value=90.0, actual_value=0.0,
                  achievement=0.0, unit='%', has_actual=False),
    }
    kpi_codes = {1: 'KDDV.TP-KD.B1.2', 2: 'KDDV.CV-KD2.B2.1', 3: 'KDDV.CV-KD2.B2.3', 4: 'KDDV.BTV.B1.1',
                 5: 'KDDV.TP-KD.B1.1'}
    cards = {
        7: [
            {'id': 100, 'employee_id': [5, 'Trần Ngọc Tú'], 'job_note': 'Trưởng phòng', 'score': 0.8,
             'score_covered': 1.0, 'data_coverage': 80.0, 'total_weight': 100.0, 'line_ids': [1, 2],
             'group_ids': [1, 2], 'state': 'draft'},
            {'id': 200, 'employee_id': [6, 'Vũ Quang'], 'job_note': 'Chuyên viên KD', 'score': 0.32,
             'score_covered': 0.604, 'data_coverage': 53.0, 'total_weight': 100.0, 'line_ids': [3, 4],
             'group_ids': [3], 'state': 'draft'},
            {'id': 300, 'employee_id': [7, 'Nguyễn Ánh Kim'], 'job_note': 'Biên tập viên', 'score': 0.0,
             'score_covered': 0.0, 'data_coverage': 0.0, 'total_weight': 100.0, 'line_ids': [5],
             'group_ids': [4], 'state': 'draft'},
        ],
        8: [], 9: [],
    }
    lines = {
        100: [{'kpi_target_id': [1, 'x'], 'group_id': [6, 'B.I — KPI DOANH THU'], 'weight_in_group': 20.0,
               'weight': 16.0, 'score': 1.0, 'has_actual': True},
              {'kpi_target_id': [2, 'x'], 'group_id': [7, 'B.II — KPI QUẢN TRỊ'], 'weight_in_group': 30.0,
               'weight': 6.0, 'score': 0.0, 'has_actual': False}],
        200: [{'kpi_target_id': [3, 'x'], 'group_id': [6, 'B.I — KPI DOANH THU'], 'weight_in_group': 25.0,
               'weight': 20.0, 'score': 0.0, 'has_actual': True},
              {'kpi_target_id': [2, 'x'], 'group_id': [7, 'B.II — KPI QUẢN TRỊ'], 'weight_in_group': 30.0,
               'weight': 6.0, 'score': 0.0, 'has_actual': False}],
        300: [{'kpi_target_id': [4, 'x'], 'group_id': [6, 'B.I — KPI DOANH THU'], 'weight_in_group': 45.0,
               'weight': 22.5, 'score': 0.0, 'has_actual': False}],
    }
    return {
        'company': {'name': 'Trung tâm', 'currency_id': [1, 'VND']},
        'staff': [{'name': 'Trần Ngọc Tú', 'job_title': 'Trưởng phòng', 'barcode': 'KDDV01',
                   'work_email': 'tu@example.com', 'parent_id': False}],
        'departments': [{'name': 'Kinh doanh và Dịch vụ'}], 'users': 22,
        'labels': {'cycle_type': {'month': 'Tháng'}, 'state': {'open': 'Đang mở'}},
        'cycles': [{'code': 'KDDV-2026-07', 'name': 'Tháng 7/2026', 'cycle_type': 'month',
                    'date_start': '2026-07-01', 'date_end': '2026-07-31', 'state': 'open',
                    'parent_id': [2, 'Quý III/2026']}],
        'objectives': [{'id': 1, 'code': 'O1', 'name': 'Doanh thu', 'weight': 50.0, 'score': 0.7,
                        'score_covered': 1.0, 'data_coverage': 70.0, 'employee_id': [5, 'TP']}],
        'krs': [{'id': 11, 'code': 'O1.KR1', 'name': 'Doanh thu quý', 'weight': 35.0, 'metric_type': 'number',
                 'target': 150.56, 'current': 209.77, 'unit': 'tỷ VNĐ', 'score': 1.0, 'has_actual': True,
                 'deadline': '2026-09-30', 'objective_id': [1, 'Doanh thu'], 'milestone_ids': [], 'note': ''},
                {'id': 12, 'code': 'O1.KR2', 'name': 'Ra mắt B2C', 'weight': 10.0, 'metric_type': 'milestone',
                 'target': 0.0, 'current': 0.0, 'unit': False, 'score': 0.0, 'has_actual': False,
                 'deadline': '2026-09-07', 'objective_id': [1, 'Doanh thu'], 'milestone_ids': [1], 'note': ''}],
        'milestones': [{'name': 'LIVE 7/9', 'kr_id': [12, 'Ra mắt B2C'], 'is_done': False}],
        'targets': targets, 'kpi_codes': kpi_codes, 'cards': cards, 'lines': lines,
        'groups': [{'assignment_id': [100, 'a'], 'group_id': [6, 'B.I — KPI DOANH THU'], 'weight': 80.0},
                   {'assignment_id': [100, 'a'], 'group_id': [7, 'B.II — KPI QUẢN TRỊ'], 'weight': 20.0},
                   {'assignment_id': [200, 'b'], 'group_id': [6, 'B.I — KPI DOANH THU'], 'weight': 80.0},
                   {'assignment_id': [300, 'c'], 'group_id': [6, 'B.I — KPI DOANH THU'], 'weight': 50.0}],
        'sources': [{'name': 'KDDV — DT Telco/ISP (TK 51131)', 'field_name': 'balance', 'multiplier': -1e-9},
                    {'name': 'KDDV — Chi phí', 'field_name': 'debit', 'multiplier': 1e-9}],
        'tracking': [{'kpi_id': [9, 'Chi phí hoạt động'], 'cycle_id': [77, 'Tháng 7/2026'], 'unit': 'tỷ VNĐ',
                      'actual_value': 18.446, 'has_actual': True},
                     {'kpi_id': [9, 'Chi phí hoạt động'], 'cycle_id': [78, 'Tháng 8/2026'], 'unit': 'tỷ VNĐ',
                      'actual_value': 0.0, 'has_actual': False}],
        'invoices': [{'ref': 'PT2026-T07-II-01', 'name': 'INV/2026/00001', 'partner_id': [1, 'FPT'],
                      'invoice_date': '2026-07-31', 'amount_untaxed': 1000.0, 'amount_tax': 80.0}],
        'entries': [{'ref': 'CPTH2026-T07', 'name': 'CPTH/2026/07/0001', 'date': '2026-07-31',
                     'journal_id': [1, 'Chi phí tổng hợp'], 'amount_total': 18445937012.0}],
        'confirmed': 38,
        'stream_lines': [{'credit': 38030000000.0, 'debit': 0.0}],
    }


class FigureCase(unittest.TestCase):

    def test_missing_picture_is_flagged_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            rendered = handbook.figure(pathlib.Path(folder), '01-scorecard-list', 1)
        self.assertIn('Thiếu ảnh minh hoạ', rendered)
        self.assertNotIn('<img', rendered)

    def test_picture_is_embedded_in_the_page(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder)
            (path / '01-scorecard-list.png').write_bytes(PNG)
            rendered = handbook.figure(path, '01-scorecard-list', 3)
        self.assertIn('data:image/png;base64,', rendered)
        self.assertIn('Hình 3.', rendered)


class ScorecardCase(unittest.TestCase):

    def setUp(self):
        self.data = dataset()

    def test_a_line_shows_how_its_weight_is_made(self):
        rows = handbook.line_rows(self.data, self.data['cards'][7][0])
        self.assertIn('20% × 80% = 16,00%', rows[0][3])

    def test_a_line_without_figures_says_so_instead_of_showing_zero(self):
        rows = handbook.line_rows(self.data, self.data['cards'][7][0])
        self.assertIn('chưa có số liệu', rows[1][4])
        self.assertIn('>—<', rows[1][5])

    def test_full_coverage_is_explained_as_measured_part_complete(self):
        note = handbook.example_explanation(self.data, self.data['cards'][7][0])
        self.assertIn('đạt trọn vẹn', note)
        self.assertIn('20% trọng số còn lại', note)

    def test_partial_score_names_the_weakest_measured_line(self):
        note = handbook.example_explanation(self.data, self.data['cards'][7][1])
        self.assertIn('DT FAST Channel', note)
        self.assertIn('47% trọng số chưa có số liệu', note)

    def test_no_figures_at_all_is_not_a_bad_result(self):
        note = handbook.example_explanation(self.data, self.data['cards'][7][2])
        self.assertIn('không phải là kết quả kém', note)


class PageCase(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        images = pathlib.Path(self.folder.name)
        for name in handbook.FIGURES:
            (images / f'{name}.png').write_bytes(PNG)
        self.page = handbook.render(dataset(), images, '18/09/2026 01:30')

    def tearDown(self):
        self.folder.cleanup()

    def test_self_contained_vietnamese_page(self):
        self.assertTrue(self.page.startswith('<!DOCTYPE html>'))
        self.assertIn('<html lang="vi">', self.page)
        self.assertIn('width=device-width', self.page)
        self.assertNotIn('<script', self.page)
        self.assertEqual(self.page.count('data:image/png;base64,'), len(handbook.FIGURES))

    def test_every_section_has_a_heading_the_contents_can_reach(self):
        for key, title in handbook.SECTIONS:
            self.assertIn(f'href="#{key}"', self.page)
            self.assertIn(f'id="{key}"', self.page)
            self.assertIn(title, self.page)

    def test_the_trail_carries_the_figure_from_file_to_score(self):
        for expected in ['38,03 tỷ', 'PT2026-T07-II-01', '51131', 'KDDV.TP-KD.B1.2', '209,77']:
            self.assertIn(expected, self.page, expected)

    def test_no_technical_names_leak_into_the_page(self):
        for forbidden in ['aic.hrm', 'account.move', 'miền lọc', 'search_read']:
            self.assertNotIn(forbidden, self.page, forbidden)

    def test_monthly_duties_and_scoring_are_both_explained(self):
        self.assertIn('Lấy số thực tế từ nguồn', self.page)
        self.assertIn('Xác nhận', self.page)
        self.assertIn('Yêu cầu điều chỉnh chỉ tiêu', self.page)
        self.assertIn('Độ phủ dữ liệu', self.page)
