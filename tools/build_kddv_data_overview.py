# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Describe, for the customer, the OKR/KPI data the live system holds.

The evaluation workbook answers "what is the result"; this page answers the
question before it: "is everything in there, and where do I look?" It counts
what production holds, lists the objectives, key results, scorecards and the
accounting documents the actuals come from, says which figures are still
missing, and names the menu each item sits under so the reader can verify
every line themselves.

Everything is read over JSON-RPC (queries only) from the live instance, so
the page cannot drift from what the system actually holds. It names real
people and real revenue and is written to Docs/OKR, which is git-ignored.

Run:  set OKR_ADMIN_PASSWORD=... && python tools/build_kddv_data_overview.py
"""
import argparse
import datetime
import html
import importlib.util
import os
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    'build_kddv_evaluation', _REPO / 'tools' / 'build_kddv_evaluation.py')
_evaluation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_evaluation)
Client, vn = _evaluation.Client, _evaluation.vn

DEFAULT_OUT = _REPO / 'Docs' / 'OKR' / 'Mo_ta_du_lieu_OKR_KDDV.html'
DEPARTMENT = 'Kinh doanh và Dịch vụ'
MONTHS = {7: 'KDDV-2026-07', 8: 'KDDV-2026-08', 9: 'KDDV-2026-09'}
VI = {'lang': 'vi_VN'}

STATUS_FULL = ('Đủ', 'ok')
STATUS_WAIT = ('Chờ số liệu', 'wait')
STATUS_PART = ('Một phần', 'part')


def esc(value):
    return html.escape('' if value is None else str(value))


def badge(status):
    label, kind = status
    return f'<span class="badge {kind}">{esc(label)}</span>'


def table(headers, rows, classes=''):
    head = ''.join(f'<th>{esc(h)}</th>' for h in headers)
    body = []
    for row in rows:
        cells = ''.join(cell if isinstance(cell, Raw) else f'<td>{esc(cell)}</td>' for cell in row)
        body.append(f'<tr>{cells}</tr>')
    return (f'<div class="scroll"><table class="{classes}"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


class Raw(str):
    """A cell already rendered as HTML."""


def cell(value, kind=''):
    return Raw(f'<td class="{kind}">{esc(value)}</td>')


def collect(client):
    """Everything the page prints, read from the live instance."""
    data = {}
    [data['company']] = client.call('res.company', 'read', [[1]],
                                    {'fields': ['name', 'currency_id', 'chart_template'], 'context': VI})
    data['departments'] = client.search_read('hr.department', [], ['name', 'manager_id'], context=VI)
    data['staff'] = client.search_read(
        'hr.employee', [('department_id.name', '=', DEPARTMENT)],
        ['name', 'job_title', 'barcode', 'work_email', 'parent_id'], order='name', context=VI)
    data['users'] = client.call('res.users', 'search_count', [[('share', '=', False)]])
    data['cycles'] = client.search_read(
        'aic.hrm.cycle', [], ['code', 'name', 'cycle_type', 'date_start', 'date_end', 'state', 'parent_id'],
        order='date_start, cycle_type', context=VI)
    data['objectives'] = client.search_read(
        'aic.hrm.objective', [('level', '=', 'department')],
        ['code', 'name', 'weight', 'score', 'score_covered', 'data_coverage', 'employee_id', 'state'],
        order='code', context=VI)
    data['krs'] = client.search_read(
        'aic.hrm.key.result', [], ['code', 'name', 'weight', 'metric_type', 'target', 'current', 'unit',
                                   'score', 'has_actual', 'deadline', 'objective_id', 'milestone_ids', 'note'],
        order='code', context=VI)
    data['milestones'] = client.call('aic.hrm.kr.milestone', 'search_count', [[]])
    # Selection labels in Vietnamese, so the page never shows technical keys.
    described = client.call('aic.hrm.cycle', 'fields_get', [['cycle_type', 'state']],
                           {'attributes': ['selection'], 'context': VI})
    data['labels'] = {field: dict(value['selection']) for field, value in described.items()}
    data['cards'] = {}
    for month, code in MONTHS.items():
        data['cards'][month] = client.search_read(
            'aic.hrm.kpi.assignment', [('cycle_id.code', '=', code)],
            ['employee_id', 'job_note', 'score', 'score_covered', 'data_coverage', 'total_weight',
             'line_ids', 'state'], order='employee_id', context=VI)
    data['groups'] = client.call('aic.hrm.kpi.assignment.group', 'search_count', [[]])
    data['lines'] = client.call('aic.hrm.kpi.assignment.line', 'search_count', [[]])
    data['lines_measured'] = client.call('aic.hrm.kpi.assignment.line', 'search_count', [[('has_actual', '=', True)]])
    data['targets'] = client.call('aic.hrm.kpi.target', 'search_count', [[]])
    data['kpis'] = client.call('aic.hrm.kpi', 'search_count', [[('is_template', '=', False)]])
    data['confirmed'] = client.call('aic.hrm.kpi.period.result', 'search_count', [[('state', '=', 'confirmed')]])
    data['sources'] = client.search_read(
        'aic.hrm.metric.source', [('name', 'like', 'KDDV')], ['name', 'field_name', 'multiplier', 'domain'],
        order='name', context=VI)
    data['tracking'] = client.search_read(
        'aic.hrm.kpi.target', [('is_tracking', '=', True)],
        ['kpi_id', 'cycle_id', 'unit', 'actual_value', 'has_actual'], context=VI)
    data['invoices'] = client.search_read(
        'account.move', [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')],
        ['invoice_date', 'amount_untaxed', 'amount_tax'], context=VI)
    data['entries'] = client.search_read(
        'account.move', [('move_type', '=', 'entry'), ('state', '=', 'posted')],
        ['ref', 'date', 'journal_id', 'amount_total'], order='ref', context=VI)
    data['revenue_targets'] = client.search_read(
        'aic.hrm.kpi.target', [('has_actual', '=', True), ('is_tracking', '=', False)],
        ['kpi_id', 'cycle_id', 'employee_id', 'target_value', 'actual_value', 'achievement', 'unit'],
        context=VI)
    data['unmeasured'] = client.search_read(
        'aic.hrm.kpi.assignment.line',
        [('assignment_id.cycle_id.code', 'in', [MONTHS[7], MONTHS[8]]), ('has_actual', '=', False)],
        ['kpi_target_id', 'assignment_id'], context=VI)
    return data


def invoice_months(data):
    months = {}
    for move in data['invoices']:
        key = move['invoice_date'][:7]
        entry = months.setdefault(key, {'count': 0, 'untaxed': 0.0, 'tax': 0.0})
        entry['count'] += 1
        entry['untaxed'] += move['amount_untaxed']
        entry['tax'] += move['amount_tax']
    return dict(sorted(months.items()))


def checklist(data):
    """The answer to "is the data complete?", item by item."""
    scored_months = [month for month, cards in data['cards'].items()
                     if any(card['data_coverage'] for card in cards)]
    rows = [
        ('Công ty, phòng ban', f"1 công ty · {len(data['departments'])} phòng ban", 'File TT Nhân viên',
         'Nhân viên › Cấu hình › Phòng ban', STATUS_FULL),
        ('Nhân sự phòng KDDV', f"{len(data['staff'])} người (mã, email, chức danh, quản lý)", 'File TT Nhân viên',
         'Nhân viên › Nhân viên', STATUS_FULL),
        ('Tài khoản đăng nhập', f"{data['users']} tài khoản nội bộ", 'Tạo theo danh sách nhân sự',
         'Cài đặt › Người dùng', STATUS_FULL),
        ('Chu kỳ kế hoạch', f"{len(data['cycles'])} chu kỳ (năm · quý · 3 tháng)", 'Quyết định giao OKR Q3',
         'Hiệu suất › Kế hoạch › Chu kỳ', STATUS_FULL),
        ('Mục tiêu OKR quý III', f"{len(data['objectives'])} mục tiêu", 'Phụ lục 5 của Quyết định',
         'Hiệu suất › Kế hoạch › Mục tiêu', STATUS_FULL),
        ('Kết quả then chốt (KR)', f"{len(data['krs'])} KR · {data['milestones']} mốc công việc", 'Phụ lục 5',
         'Hiệu suất › Kế hoạch › Kết quả then chốt', STATUS_FULL),
        ('Phiếu giao KPI tháng', f"{sum(len(c) for c in data['cards'].values())} phiếu "
                                 f"· {data['groups']} nhóm · {data['lines']} dòng KPI",
         'File Giao KPI T7–T9', 'Hiệu suất › Kế hoạch › Bảng điểm cá nhân', STATUS_FULL),
        ('Chỉ tiêu KPI', f"{data['targets']} chỉ tiêu · {data['kpis']} KPI riêng của phòng", 'File Giao KPI T7–T9',
         'Hiệu suất › Kế hoạch › Chỉ tiêu KPI', STATUS_FULL),
        ('Doanh thu thực tế', f"{len(data['invoices'])} hoá đơn đã vào sổ (T1–T8) "
                              f"+ 1 bút toán dự thu T8", 'File Phiếu thu 2026',
         'Kế toán › Khách hàng › Hoá đơn', STATUS_PART),
        ('Chi phí thực tế', f"{len([e for e in data['entries'] if e['ref'].startswith('CPTH')])} bút toán (T1–T7)",
         'File chi phí 2026', 'Kế toán › Kế toán › Bút toán', STATUS_PART),
        ('Nguồn lấy số tự động', f"{len(data['sources'])} nguồn đọc sổ kế toán", 'Cấu hình trong hệ thống',
         'Hiệu suất › Cấu hình › Nguồn số liệu', STATUS_FULL),
        ('Số thực tế đã xác nhận', f"{data['confirmed']} kết quả kỳ (tháng "
                                   f"{', '.join(str(m) for m in scored_months)})", 'Lấy từ sổ kế toán',
         'Hiệu suất › Thực hiện › Kết quả theo kỳ', STATUS_PART),
        ('Chỉ số theo dõi của phòng', 'Chi phí · Lợi nhuận gộp (không chấm điểm)', 'File chi phí 2026',
         'Hiệu suất › Kế hoạch › Chỉ tiêu KPI', STATUS_PART),
        ('KPI ngoài doanh thu', f"{len(data['unmeasured'])} dòng chưa có số thực tế "
                               '(MAU, merchant, SOP, CAC, công nợ…)', 'Khách hàng cung cấp',
         'Hiệu suất › Thực hiện › Import số liệu thực tế', STATUS_WAIT),
    ]
    return [(name, amount, source, where, badge(status)) for name, amount, source, where, status in rows]


def okr_rows(data):
    rows = []
    by_objective = {}
    for kr in data['krs']:
        by_objective.setdefault(kr['objective_id'][0], []).append(kr)
    for objective in data['objectives']:
        rows.append([
            Raw(f'<td class="strong">{esc(objective["code"])}</td>'),
            Raw(f'<td class="strong">{esc(objective["name"])}</td>'),
            cell(vn(objective['weight'], 0) + '%'), cell(''), cell(''),
            cell(vn(100 * objective['score'], 1) + '%'),
            cell(vn(objective['data_coverage'], 1) + '%'),
        ])
        for kr in by_objective.get(objective['id'], []):
            target = ('mốc công việc' if kr['metric_type'] == 'milestone'
                      else f"{vn(kr['target'])} {kr['unit'] or ''}".strip())
            actual = ('—' if not kr['has_actual']
                      else ('đã ghi nhận' if kr['metric_type'] == 'milestone'
                            else f"{vn(kr['current'])} {kr['unit'] or ''}".strip()))
            rows.append([
                cell(kr['code']), cell(kr['name']), cell(vn(kr['weight'], 0) + '%'),
                cell(target), cell(actual),
                cell(vn(100 * kr['score'], 1) + '%'),
                Raw('<td>' + ('có số liệu' if kr['has_actual'] else
                              '<span class="muted">chưa có số liệu</span>') + '</td>'),
            ])
    return rows


def scorecard_rows(data):
    rows = []
    for month in sorted(data['cards']):
        for card in data['cards'][month]:
            rows.append([
                f'T{month}/2026', card['employee_id'][1], card['job_note'] or '',
                len(card['line_ids']),
                vn(card['total_weight'], 0) + '%',
                vn(100 * card['score'], 1) + '%',
                vn(100 * card['score_covered'], 1) + '%' if card['data_coverage'] else '—',
                vn(card['data_coverage'], 1) + '%',
            ])
    return rows


def actual_rows(data):
    rows = []
    for target in sorted(data['revenue_targets'], key=lambda t: (t['cycle_id'][1], t['kpi_id'][1])):
        rows.append([
            target['cycle_id'][1], target['kpi_id'][1],
            target['employee_id'][1] if target['employee_id'] else 'cấp phòng',
            f"{vn(target['target_value'])} {target['unit'] or ''}".strip(),
            f"{vn(target['actual_value'])} {target['unit'] or ''}".strip(),
            vn(100 * target['achievement'], 1) + '%',
        ])
    return rows


def missing_rows(data):
    grouped = {}
    for line in data['unmeasured']:
        label = line['kpi_target_id'][1].split(' · ')[0]
        grouped.setdefault(label, set()).add(line['assignment_id'][1].split(' · ')[0])
    return [[label, len(people), ', '.join(sorted(people))]
            for label, people in sorted(grouped.items(), key=lambda item: -len(item[1]))]


STYLE = """
:root { --ink:#16202b; --muted:#6b7a8d; --line:#dfe6ee; --bg:#f6f8fb; --card:#fff;
        --ok:#1f7a4d; --okbg:#e6f5ec; --wait:#8a5a00; --waitbg:#fdf2dd; --part:#1c4f8a; --partbg:#e7f0fb; }
* { box-sizing:border-box; }
body { margin:0; padding:24px 16px 64px; background:var(--bg); color:var(--ink);
       font:16px/1.65 "Segoe UI", system-ui, -apple-system, Arial, sans-serif; }
main { max-width:1100px; margin:0 auto; }
h1 { font-size:1.6rem; margin:0 0 4px; }
h2 { font-size:1.2rem; margin:32px 0 8px; padding-top:8px; border-top:2px solid var(--line); }
h3 { font-size:1rem; margin:20px 0 6px; }
p, li { margin:6px 0; }
.lead { color:var(--muted); }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; margin:12px 0; }
.grid { display:grid; gap:12px; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); }
.kpi { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 14px; }
.kpi b { display:block; font-size:1.5rem; line-height:1.2; }
.kpi span { color:var(--muted); font-size:.9rem; }
.scroll { overflow-x:auto; -webkit-overflow-scrolling:touch; }
table { width:100%; border-collapse:collapse; background:var(--card); font-size:.94rem; }
th, td { padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
th { background:#eef3f8; font-weight:600; white-space:nowrap; }
tbody tr:hover { background:#fafcff; }
.strong td, td.strong { font-weight:600; background:#f4f8fd; }
.muted, .lead small { color:var(--muted); }
.badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.85rem; white-space:nowrap; }
.badge.ok { background:var(--okbg); color:var(--ok); }
.badge.wait { background:var(--waitbg); color:var(--wait); }
.badge.part { background:var(--partbg); color:var(--part); }
code { background:#eef3f8; padding:1px 5px; border-radius:5px; font-size:.9em; }
footer { color:var(--muted); font-size:.9rem; margin-top:32px; }
@media (max-width:600px) { body { padding:16px 12px 48px; } h1 { font-size:1.3rem; } table { font-size:.88rem; } }
"""


def render(data, generated):
    months = invoice_months(data)
    quarter_actual = sum(target['actual_value'] for target in data['revenue_targets']
                         if target['kpi_id'][1].startswith('Tổng doanh thu'))
    parts = [f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dữ liệu OKR/KPI đã có trong hệ thống — Phòng Kinh doanh và Dịch vụ</title>
<style>{STYLE}</style></head><body><main>
<h1>Dữ liệu OKR/KPI đã có trong hệ thống</h1>
<p class="lead">{esc(data['company']['name'])} · Phòng {esc(DEPARTMENT)} · Quý III/2026<br>
<small>Địa chỉ hệ thống: <code>https://okr.aipower.vn</code> · Tiền tệ {esc(data['company']['currency_id'][1])}
· Số liệu đọc trực tiếp từ hệ thống lúc {esc(generated)}</small></p>

<div class="card"><p><b>Đọc trang này để làm gì.</b> Trang này liệt kê đúng những gì hệ thống đang có:
kế hoạch (OKR, KPI) và số thực hiện (doanh thu, chi phí). Mỗi mục đều ghi <i>số lượng</i>,
<i>lấy từ tài liệu nào</i> và <i>xem ở menu nào</i>, để anh/chị tự mở hệ thống kiểm chứng.
Mục nào chưa có số thực hiện đều được ghi rõ là đang chờ dữ liệu, hệ thống không tự điền số.</p></div>

<div class="grid">
  <div class="kpi"><b>{len(data['objectives'])} / {len(data['krs'])}</b><span>Mục tiêu / Kết quả then chốt</span></div>
  <div class="kpi"><b>{sum(len(c) for c in data['cards'].values())}</b><span>Phiếu giao KPI tháng</span></div>
  <div class="kpi"><b>{data['lines']}</b><span>Dòng KPI được giao</span></div>
  <div class="kpi"><b>{len(data['invoices'])}</b><span>Hoá đơn đã vào sổ</span></div>
  <div class="kpi"><b>{data['confirmed']}</b><span>Số thực tế đã xác nhận</span></div>
  <div class="kpi"><b>{vn(quarter_actual)} tỷ</b><span>Doanh thu quý III đã ghi nhận</span></div>
</div>

<h2>1. Hệ thống đã có đủ dữ liệu chưa?</h2>
<p>Bảng sau là câu trả lời theo từng nhóm dữ liệu.
<span class="badge ok">Đủ</span> = đã nhập trọn vẹn theo tài liệu;
<span class="badge part">Một phần</span> = đúng với dữ liệu khách hàng đã cung cấp, còn thiếu kỳ chưa có số;
<span class="badge wait">Chờ số liệu</span> = hệ thống đã sẵn chỗ nhập, đang chờ số từ đơn vị.</p>
{table(['Nhóm dữ liệu', 'Đang có', 'Nguồn', 'Xem tại menu', 'Trạng thái'], checklist(data))}

<h2>2. Tổ chức và người dùng</h2>
<p>{len(data['departments'])} phòng ban; nhân sự chi tiết nhập cho Phòng {esc(DEPARTMENT)}
({len(data['staff'])} người), mỗi người có một tài khoản đăng nhập riêng.</p>
{table(['Mã NV', 'Họ và tên', 'Chức danh', 'Email đăng nhập', 'Quản lý trực tiếp'],
       [[s['barcode'] or '', s['name'], s['job_title'] or '', s['work_email'] or '',
         s['parent_id'][1] if s['parent_id'] else ''] for s in data['staff']])}

<h2>3. Chu kỳ kế hoạch</h2>
{table(['Mã', 'Tên', 'Loại', 'Từ ngày', 'Đến ngày', 'Chu kỳ cha', 'Trạng thái'],
       [[c['code'], c['name'], data['labels']['cycle_type'].get(c['cycle_type'], c['cycle_type']),
         c['date_start'], c['date_end'], c['parent_id'][1] if c['parent_id'] else '—',
         data['labels']['state'].get(c['state'], c['state'])] for c in data['cycles']])}

<h2>4. OKR quý III/2026 của phòng</h2>
<p>Nguyên văn theo Phụ lục 5 của Quyết định giao nhiệm vụ trọng tâm. Cột “Điểm” do hệ thống tính
từ số thực hiện đã ghi nhận; cột “Độ phủ dữ liệu” cho biết bao nhiêu phần trăm trọng số đã có số thực tế.</p>
{table(['Mã', 'Nội dung', 'Trọng số', 'Chỉ tiêu', 'Thực hiện', 'Điểm', 'Độ phủ dữ liệu'], okr_rows(data))}

<h2>5. Phiếu giao KPI theo tháng</h2>
<p>Mỗi người mỗi tháng có một phiếu, chia hai nhóm (KPI Doanh thu và KPI Quản trị) đúng như phiếu giao;
trọng số từng dòng = trọng số nhóm × trọng số trong nhóm, tổng luôn bằng 100%.</p>
{table(['Kỳ', 'Họ và tên', 'Vị trí', 'Số dòng KPI', 'Tổng trọng số', 'Điểm', 'Điểm trên phần có số liệu', 'Độ phủ dữ liệu'],
       scorecard_rows(data))}

<h2>6. Số thực hiện lấy từ kế toán</h2>
<p>Doanh thu được ghi nhận bằng <b>hoá đơn bán hàng</b> (phần đã xuất hoá đơn) và <b>bút toán dự thu</b>
(phần đã thực hiện chưa xuất hoá đơn). Chi phí ghi bằng bút toán theo từng tài khoản của sổ kế toán.
KPI không nhập số tay: hệ thống đọc trực tiếp từ các bút toán đã vào sổ.</p>
<h3>6.1 Hoá đơn bán hàng theo tháng</h3>
{table(['Tháng', 'Số hoá đơn', 'Doanh thu chưa VAT (đồng)', 'Thuế GTGT (đồng)'],
       [[month, entry['count'], vn(entry['untaxed'], 0), vn(entry['tax'], 0)] for month, entry in months.items()])}
<h3>6.2 Bút toán dự thu và chi phí</h3>
{table(['Tham chiếu', 'Ngày', 'Sổ nhật ký', 'Giá trị (đồng)'],
       [[e['ref'], e['date'], e['journal_id'][1], vn(e['amount_total'], 0)] for e in data['entries']])}
<h3>6.3 Nguồn lấy số tự động</h3>
{table(['Tên nguồn', 'Trường đọc', 'Điều kiện (miền lọc)'],
       [[s['name'], s['field_name'], s['domain']] for s in data['sources']])}

<h2>7. Số thực tế đã ghi nhận cho từng KPI</h2>
{table(['Kỳ', 'KPI', 'Người được giao', 'Chỉ tiêu', 'Thực hiện', 'Đạt'], actual_rows(data))}

<h2>8. Chỉ số theo dõi của phòng (không chấm điểm)</h2>
<p>Chi phí và lợi nhuận gộp lấy từ sổ kế toán, chỉ để theo dõi, không có trọng số nên không ảnh hưởng
điểm của cá nhân. Tháng nào chưa có số kế toán thì để trống.</p>
{table(['Kỳ', 'Chỉ số', 'Đơn vị', 'Giá trị'],
       [[t['cycle_id'][1], t['kpi_id'][1], t['unit'] or '',
         vn(t['actual_value']) if t['has_actual'] else 'chưa có số liệu']
        for t in sorted(data['tracking'], key=lambda t: (t['cycle_id'][1], t['kpi_id'][1]))])}

<h2>9. Những gì chưa có số thực hiện</h2>
<p>Đây là các KPI đã được giao đầy đủ trong hệ thống nhưng chưa có số thực tế, vì số liệu nằm ngoài
sổ kế toán. Hệ thống <b>không chấm 0</b> cho các dòng này: điểm được tính trên phần có số liệu và luôn
kèm độ phủ dữ liệu, để việc đánh giá không bị hiểu sai.</p>
{table(['KPI chưa có số thực hiện', 'Số người được giao', 'Người được giao'], missing_rows(data))}

<h2>10. Cách anh/chị tự kiểm tra trong hệ thống</h2>
<div class="card"><ol>
<li>Kế hoạch quý: <b>Hiệu suất › Kế hoạch › Mục tiêu</b> và <b>Kết quả then chốt</b>.</li>
<li>Phiếu giao KPI từng người: <b>Hiệu suất › Kế hoạch › Bảng điểm cá nhân</b> — mở một phiếu để thấy
hai nhóm KPI, trọng số và điểm.</li>
<li>Số thực hiện từng tháng: <b>Hiệu suất › Thực hiện › Kết quả theo kỳ</b> (trạng thái “Đã xác nhận”
mới được tính điểm).</li>
<li>Gốc số liệu doanh thu: <b>Kế toán › Khách hàng › Hoá đơn</b>, tìm theo tham chiếu <code>PT2026-…</code>;
chi phí và dự thu: <b>Kế toán › Kế toán › Bút toán</b>, tham chiếu <code>CPTH2026-…</code>,
<code>DTHU2026-…</code>.</li>
<li>Cách hệ thống tự lấy số: <b>Hiệu suất › Cấu hình › Nguồn số liệu</b>.</li>
<li>Báo cáo tổng hợp: <b>Hiệu suất › Báo cáo › Bảng điểm phòng ban</b> và
<b>Tiến độ so với kế hoạch</b>; bản đánh giá chi tiết trong tệp
<code>Danh_gia_KDDV_Q3_2026_T7-T8.xlsx</code> gửi kèm.</li>
</ol></div>

<h2>11. Việc cần đơn vị cung cấp thêm</h2>
<div class="card"><ol>
<li>Doanh thu tháng 9/2026 và chi phí tháng 8–9/2026 (hiện chưa có trong hai tệp đã gửi).</li>
<li>Xác nhận phần “đã thực hiện chưa xuất hoá đơn” của tháng 8: nhiều đối tác có cả hai phần gần bằng nhau,
cần xác nhận phần chưa xuất hoá đơn thuộc tháng nào.</li>
<li>Xác nhận các hoá đơn gộp nhiều tháng ghi ở tháng 7 (VNPT, VTVshop MG).</li>
<li>Số liệu cho các KPI ngoài doanh thu ở mục 9 (MAU, merchant, SOP, CAC, công nợ…).</li>
<li>Phân bổ tài khoản trung gian <code>3388</code> về lương, nhà cung cấp… theo sổ kế toán thật.</li>
</ol></div>

<footer>Tài liệu do hệ thống sinh tự động từ dữ liệu đang chạy trên <code>okr.aipower.vn</code>.
Mọi con số ở trên đọc trực tiếp từ hệ thống, không nhập lại bằng tay.</footer>
</main></body></html>
"""]
    return ''.join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--url', default='https://okr.aipower.vn')
    parser.add_argument('--db', default='okr_aipower')
    parser.add_argument('--user', default='admin')
    parser.add_argument('--password', default=os.environ.get('OKR_ADMIN_PASSWORD'))
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    if not args.password:
        parser.error('pass --password or set OKR_ADMIN_PASSWORD')
    client = Client(args.url, args.db, args.user, args.password)
    data = collect(client)
    generated = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data, generated), encoding='utf-8', newline='\n')
    print('%s (%d KB)' % (out, out.stat().st_size // 1024))


if __name__ == '__main__':
    main()
