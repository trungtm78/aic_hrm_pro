# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Write the Sales & Services Q3/2026 evaluation from what production holds.

Everything printed here is read from the live instance over JSON-RPC (queries
only) and compared with the customer's own workbooks, so the report states
what the system scored, how much of each scorecard is actually measured, and
what could not be scored because no figures exist yet.

The output names real people and real revenue: it is written to Docs/OKR,
which is git-ignored, and is meant to be handed to the customer.

Run:  set OKR_ADMIN_PASSWORD=... && python tools/build_kddv_evaluation.py
"""
import argparse
import json
import os
import pathlib
import urllib.request

_REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_ACTUALS = _REPO / 'uat' / 'data' / 'kddv_actuals_q3_2026.json'
DEFAULT_OUT = _REPO / 'Docs' / 'OKR' / 'Danh_gia_KDDV_Q3_2026_T7-T8.xlsx'
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/130.0 Safari/537.36')
MONTH_CODES = {7: 'KDDV-2026-07', 8: 'KDDV-2026-08', 9: 'KDDV-2026-09'}
QUARTER_PLAN = {'telco': 67.53, 'vtvshop_mg': 62.50, 'tnnd': 17.55, 'fast': 2.73, 'digital': 0.20}
MONTH_PLAN = {
    7: {'telco': 21.92, 'vtvshop_mg': 20.83, 'tnnd': 5.50, 'fast': 0.90, 'digital': 0.0},
    8: {'telco': 22.64, 'vtvshop_mg': 20.83, 'tnnd': 5.90, 'fast': 0.90, 'digital': 0.0},
    9: {'telco': 22.97, 'vtvshop_mg': 20.84, 'tnnd': 6.20, 'fast': 0.93, 'digital': 0.20},
}


class Client:
    """Read-only JSON-RPC client."""

    QUERIES = {'search_read', 'search_count', 'read', 'read_group', 'fields_get', 'search'}

    def __init__(self, url, db, user, password):
        self.url, self.db, self.password = url, db, password
        self.uid = self._rpc('common', 'login', [db, user, password])
        if not self.uid:
            raise SystemExit('Cannot log in to %s at %s' % (db, url))

    def _rpc(self, service, method, args):
        request = urllib.request.Request(
            self.url.rstrip('/') + '/jsonrpc',
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                             'params': {'service': service, 'method': method, 'args': args}}).encode(),
            headers={'Content-Type': 'application/json', 'User-Agent': USER_AGENT})
        body = json.load(urllib.request.urlopen(request, timeout=120))
        if body.get('error'):
            raise SystemExit(body['error']['data']['message'])
        return body['result']

    def call(self, model, method, args, kwargs=None):
        assert method in self.QUERIES, method
        return self._rpc('object', 'execute_kw',
                         [self.db, self.uid, self.password, model, method, args, kwargs or {}])

    def search_read(self, model, domain, fields, **kwargs):
        return self.call(model, 'search_read', [domain], dict(fields=fields, **kwargs))


def vn(value, decimals=2):
    """Vietnamese number, e.g. 1.234,56; empty for a missing figure."""
    if value is None:
        return ''
    text = ('{:,.%df}' % decimals).format(value)
    return text.replace(',', ' ').replace('.', ',').replace(' ', '.')


def revenue_rows(actuals):
    """Plan against actual per stream and month, plus the quarter to date."""
    rows = []
    for key, name in actuals['streams'].items():
        actual = {month: actuals['revenue'][str(month)]['streams'][key] for month in (7, 8, 9)}
        done = sum(actual[m]['total'] for m in (7, 8))
        rows.append([
            name,
            vn(MONTH_PLAN[7][key]), vn(actual[7]['total']),
            vn(MONTH_PLAN[8][key]), vn(actual[8]['total']),
            vn(MONTH_PLAN[9][key]), vn(actual[9]['total']) if actuals['revenue']['9']['has_data'] else '',
            vn(QUARTER_PLAN[key]), vn(done),
            vn(100.0 * done / QUARTER_PLAN[key], 1) if QUARTER_PLAN[key] else '',
        ])
    plan_total = sum(QUARTER_PLAN.values())
    done_total = sum(actuals['revenue'][str(m)]['total'] for m in (7, 8))
    rows.append([
        'TỔNG', vn(sum(MONTH_PLAN[7].values())), vn(actuals['revenue']['7']['total']),
        vn(sum(MONTH_PLAN[8].values())), vn(actuals['revenue']['8']['total']),
        vn(sum(MONTH_PLAN[9].values())), '',
        vn(plan_total), vn(done_total), vn(100.0 * done_total / plan_total, 1),
    ])
    return rows


def scorecard_rows(client):
    """One row per person and month: score, score on measured KPIs, coverage."""
    cycles = {row['code']: row['id'] for row in client.search_read(
        'aic.hrm.cycle', [('code', 'in', list(MONTH_CODES.values()))], ['code'])}
    rows = []
    for month in (7, 8):
        cards = client.search_read(
            'aic.hrm.kpi.assignment', [('cycle_id', '=', cycles[MONTH_CODES[month]])],
            ['employee_id', 'job_note', 'score', 'score_covered', 'data_coverage', 'state'])
        for card in sorted(cards, key=lambda card: card['employee_id'][1]):
            lines = client.search_read(
                'aic.hrm.kpi.assignment.line', [('assignment_id', '=', card['id'])],
                ['kpi_target_id', 'weight', 'has_actual', 'score'])
            measured = [line for line in lines if line['has_actual']]
            rows.append(['T%d/2026' % month, card['employee_id'][1], card['job_note'] or '',
                          vn(100 * card['score'], 1), vn(100 * card['score_covered'], 1),
                          vn(card['data_coverage'], 1), len(measured), len(lines)])
    return rows


def kpi_detail_rows(client, actuals):
    """Every revenue KPI that was scored, with its target and actual."""
    codes = sorted({item['code'] for item in actuals['kpi_actuals']})
    rows = []
    for month in (7, 8):
        for code in codes:
            for target in client.search_read(
                    'aic.hrm.kpi.target',
                    [('kpi_id.code', '=', code), ('cycle_id.code', '=', MONTH_CODES[month])],
                    ['employee_id', 'target_value', 'actual_value', 'achievement', 'unit', 'target_note', 'kr_id']):
                rows.append(['T%d/2026' % month, code,
                             target['employee_id'][1] if target['employee_id'] else '',
                             target['target_note'] or '', vn(target['target_value']),
                             vn(target['actual_value']), vn(100 * target['achievement'], 1),
                             target['kr_id'][1] if target['kr_id'] else ''])
    return rows


def okr_rows(client):
    objectives = client.search_read(
        'aic.hrm.objective', [('level', '=', 'department')],
        ['code', 'name', 'weight', 'score', 'score_covered', 'data_coverage'], order='code')
    rows = []
    for objective in objectives:
        rows.append([objective['code'], objective['name'], vn(objective['weight'], 0),
                     vn(100 * objective['score'], 1), vn(100 * objective['score_covered'], 1),
                     vn(objective['data_coverage'], 1), '', ''])
        for kr in client.search_read('aic.hrm.key.result', [('objective_id', '=', objective['id'])],
                                     ['code', 'name', 'weight', 'target', 'current', 'unit', 'score', 'has_actual'],
                                     order='code'):
            rows.append([kr['code'], kr['name'], vn(kr['weight'], 0), vn(100 * kr['score'], 1), '', '',
                         '%s / %s %s' % (vn(kr['current']), vn(kr['target']), kr['unit'] or ''),
                         'có số liệu' if kr['has_actual'] else 'chưa có số liệu'])
    return rows


def tracking_rows(client, actuals):
    rows = []
    for item in actuals['tracking']:
        if item['month'] == 9:
            continue
        found = client.search_read(
            'aic.hrm.kpi.target', [('kpi_id.code', '=', item['code']),
                                   ('cycle_id.code', '=', MONTH_CODES[item['month']])],
            ['actual_value', 'has_actual'])
        rows.append(['T%d/2026' % item['month'], item['name'], item['unit'],
                     vn(item['value']) if item['value'] is not None else 'chưa có số liệu',
                     vn(found[0]['actual_value']) if found and found[0]['has_actual'] else 'chưa có số liệu'])
    return rows


def missing_rows(client):
    """Scorecard lines with no confirmed actual: what the customer must supply."""
    rows = []
    for month in (7, 8):
        lines = client.search_read(
            'aic.hrm.kpi.assignment.line',
            [('assignment_id.cycle_id.code', '=', MONTH_CODES[month]), ('has_actual', '=', False)],
            ['kpi_target_id', 'weight', 'assignment_id'])
        by_kpi = {}
        for line in lines:
            label = line['kpi_target_id'][1].split(' · ')[0]
            by_kpi.setdefault(label, []).append(line['assignment_id'][1].split(' · ')[0])
        for label, people in sorted(by_kpi.items()):
            rows.append(['T%d/2026' % month, label, len(people), ', '.join(sorted(set(people)))])
    return rows


SHEETS = [
    ('Tổng quan DT', ['Mảng doanh thu', 'KH T7', 'Thực tế T7', 'KH T8', 'Thực tế T8', 'KH T9', 'Thực tế T9',
                      'KH Quý III', 'Thực tế T7+T8', '% so KH quý'], revenue_rows),
    ('Diem theo nguoi', ['Kỳ', 'Họ tên', 'Vị trí', 'Điểm (%)', 'Điểm trên KPI có số liệu (%)',
                         'Độ phủ dữ liệu (%)', 'Số KPI có số liệu', 'Tổng KPI'], None),
    ('Chi tiet KPI DT', ['Kỳ', 'Mã KPI', 'Người', 'Chỉ tiêu giao (nguyên văn)', 'Chỉ tiêu', 'Thực tế',
                         'Đạt (%)', 'Gắn KR'], None),
    ('OKR Quy III', ['Mã', 'Nội dung', 'Trọng số (%)', 'Điểm (%)', 'Điểm trên phần có số liệu (%)',
                     'Độ phủ (%)', 'Thực tế / Chỉ tiêu', 'Trạng thái số liệu'], None),
    ('Chi phi - Loi nhuan', ['Kỳ', 'Chỉ số', 'Đơn vị', 'Theo file', 'Trên hệ thống'], None),
    ('Chua co so lieu', ['Kỳ', 'KPI', 'Số người', 'Người được giao'], None),
    ('Bat thuong can kiem tra', ['Tháng', 'Đối tác', 'Loại', 'Nội dung'], None),
]


def build(client, actuals, out):
    import openpyxl
    from openpyxl.styles import Alignment, Font

    book = openpyxl.Workbook()
    book.remove(book.active)
    data = {
        'Tổng quan DT': revenue_rows(actuals),
        'Diem theo nguoi': scorecard_rows(client),
        'Chi tiet KPI DT': kpi_detail_rows(client, actuals),
        'OKR Quy III': okr_rows(client),
        'Chi phi - Loi nhuan': tracking_rows(client, actuals),
        'Chua co so lieu': missing_rows(client),
        'Bat thuong can kiem tra': [[ 'T%d' % issue['month'], issue['partner'], issue['kind'], issue['text']]
                                    for issue in actuals['irregularities']],
    }
    for title, header, _builder in SHEETS:
        sheet = book.create_sheet(title)
        sheet.append(header)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(wrap_text=True, vertical='center')
        for row in data[title]:
            sheet.append(row)
        for index, _name in enumerate(header, 1):
            letter = openpyxl.utils.get_column_letter(index)
            width = max([len(str(header[index - 1]))] + [len(str(row[index - 1])) for row in data[title]] or [10])
            sheet.column_dimensions[letter].width = min(60, max(12, width + 2))
        sheet.freeze_panes = 'A2'
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    book.save(out)
    return {title: len(rows) for title, rows in data.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--url', default='https://okr.aipower.vn')
    parser.add_argument('--db', default='okr_aipower')
    parser.add_argument('--user', default='admin')
    parser.add_argument('--password', default=os.environ.get('OKR_ADMIN_PASSWORD'))
    parser.add_argument('--actuals', default=str(DEFAULT_ACTUALS))
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    if not args.password:
        parser.error('pass --password or set OKR_ADMIN_PASSWORD')
    actuals = json.loads(pathlib.Path(args.actuals).read_text(encoding='utf-8'))
    client = Client(args.url, args.db, args.user, args.password)
    counts = build(client, actuals, args.out)
    print('%s: %s' % (args.out, counts))


if __name__ == '__main__':
    main()
