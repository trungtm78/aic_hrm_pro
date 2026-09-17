# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Write the Sales & Services actuals as files for the product's actuals import.

The files use the flat format of Performance > Import Actuals
(type | code | employee | date_from | date_to | value | note), one file per
cycle the wizard is run in: one per month with revenue or cost figures, and
one for the quarter carrying the revenue key result's check-in.

Revenue lines go to every person holding the scorecard line (the department
target is shared by everyone in the position). Department tracking
indicators have no owner, which the wizard matches to targets without an
employee. Values the source does not have are left out, never written as 0.

Output folder is git-ignored (it names real people and real revenue).

Run:  python tools/build_kddv_actuals_import.py [--actuals ...] [--plan ...] [--out uat/data/import_actuals]
"""
import argparse
import calendar
import json
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_ACTUALS = _REPO / 'uat' / 'data' / 'kddv_actuals_q3_2026.json'
DEFAULT_PLAN = _REPO / 'uat' / 'data' / 'kddv_q3_2026.json'
DEFAULT_OUT = _REPO / 'uat' / 'data' / 'import_actuals'

HEADER = ['type', 'code', 'employee', 'date_from', 'date_to', 'value', 'note']
QUARTER_FILE = 'KDDV_THUC_TE_Q3_2026.xlsx'


def month_file(month, year):
    return 'KDDV_THUC_TE_T%d_%d.xlsx' % (month, year)


def month_bounds(year, month):
    return '%d-%02d-01' % (year, month), '%d-%02d-%02d' % (year, month, calendar.monthrange(year, month)[1])


def holders(plan, month, position):
    return sorted(card['employee'] for card in plan['scorecards']
                  if card['month'] == month and card['position'] == position)


def files(actuals, plan):
    """{file name: [row, ...]} with rows in HEADER order."""
    year = actuals['year']
    out = {}
    for item in actuals['kpi_actuals']:
        date_from, date_to = month_bounds(year, item['month'])
        people = holders(plan, item['month'], item['position'])
        if not people:
            raise ValueError('No %s scorecard in month %s' % (item['position'], item['month']))
        for person in people:
            out.setdefault(month_file(item['month'], year), []).append(
                ['kpi', item['code'], person, date_from, date_to, item['value'], item['note']])
    for item in actuals['tracking']:
        if item['value'] is None:
            continue
        date_from, date_to = month_bounds(year, item['month'])
        out.setdefault(month_file(item['month'], year), []).append(
            ['kpi', item['code'], '', date_from, date_to, item['value'], item['note']])
    for item in actuals['kr_checkins']:
        last = max(actuals['months_with_revenue'])
        date_from, date_to = month_bounds(year, last)
        out.setdefault(QUARTER_FILE, []).append(
            ['kr', item['code'], '', date_to, date_to, item['value'], item['note']])
    return out


def write(rows_by_file, out_dir):
    import openpyxl
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in rows_by_file.items():
        book = openpyxl.Workbook()
        sheet = book.active
        sheet.title = 'actuals'
        sheet.append(HEADER)
        for row in rows:
            sheet.append(row)
        book.save(out_dir / name)
    return sorted(rows_by_file)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--actuals', default=str(DEFAULT_ACTUALS))
    parser.add_argument('--plan', default=str(DEFAULT_PLAN))
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    actuals = json.loads(pathlib.Path(args.actuals).read_text(encoding='utf-8'))
    plan = json.loads(pathlib.Path(args.plan).read_text(encoding='utf-8'))
    rows = files(actuals, plan)
    for name in write(rows, args.out):
        print('%s: %d rows' % (name, len(rows[name])))


if __name__ == '__main__':
    main()
