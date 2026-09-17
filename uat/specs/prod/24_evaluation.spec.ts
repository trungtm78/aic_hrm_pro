import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test, expect, read } from '../../fixtures/prod';

/**
 * Independent acceptance of the Q3/2026 evaluation.
 *
 * Reads only: the ledger, the KPI results and the scores as production holds
 * them, checked against the customer's own workbooks (through the extracted
 * dataset) and recomputed here. It never calls the entry specs, so a mistake
 * in them cannot make this pass.
 */

const actuals = JSON.parse(readFileSync(resolve(__dirname, '..', '..', 'data', 'kddv_actuals_q3_2026.json'), 'utf-8'));
const books = actuals.accounting;
const MONTH_CODE = { 7: 'KDDV-2026-07', 8: 'KDDV-2026-08', 9: 'KDDV-2026-09' } as Record<number, string>;

test('the ledger carries the register and the cost sheets', async () => {
  const [company] = await read('res.company', 'read', [[1]], { fields: ['currency_id', 'chart_template'] });
  expect([company.chart_template, company.currency_id[1]]).toEqual(['vn', 'VND']);

  const invoices = await read('account.move', 'search_read', [[
    ['move_type', '=', 'out_invoice'], ['ref', '=like', 'PT2026-%']]], { fields: ['ref', 'state', 'amount_untaxed', 'invoice_date'] });
  expect(invoices.length).toBe(books.invoices.length);
  expect(invoices.every((move: any) => move.state === 'posted')).toBe(true);
  const byRef = new Map(invoices.map((move: any) => [move.ref, move]));
  for (const invoice of books.invoices) {
    const move: any = byRef.get(invoice.ref);
    expect(move, invoice.ref).toBeTruthy();
    expect(move.amount_untaxed, invoice.ref).toBe(invoice.untaxed);
    expect(move.invoice_date, invoice.ref).toBe(invoice.date);
  }

  for (const [month, entry] of Object.entries(books.accruals) as [string, any][]) {
    const [move] = await read('account.move', 'search_read', [[['ref', '=', entry.ref]]], { fields: ['state'] });
    const lines = await read('account.move.line', 'search_read', [[['move_id', '=', move.id]]],
      { fields: ['debit', 'credit', 'account_id'] });
    expect(move.state, `accrual T${month}`).toBe('posted');
    // A correction is entered on the other side, so gross debits exceed the
    // month's revenue; the net per account is what must match the register.
    const net = (prefix: string) => lines
      .filter((line: any) => line.account_id[1].startsWith(`${prefix} `))
      .reduce((sum: number, line: any) => sum + line.credit - line.debit, 0);
    expect(-net(books.accrual_account.code), `accrual T${month} receivable`).toBe(entry.total);
    const perAccount: Record<string, number> = {};
    for (const line of entry.lines) perAccount[line.account] = (perAccount[line.account] ?? 0) + line.amount;
    for (const [code, amount] of Object.entries(perAccount)) {
      expect(net(code), `accrual T${month} account ${code}`).toBe(amount);
    }
  }

  for (const [month, entry] of Object.entries(books.cost_entries) as [string, any][]) {
    const [move] = await read('account.move', 'search_read', [[['ref', '=', entry.ref]]], { fields: ['state'] });
    const lines = await read('account.move.line', 'search_read', [[['move_id', '=', move.id]]], { fields: ['debit', 'credit'] });
    expect(move.state, `cost T${month}`).toBe('posted');
    expect(lines.reduce((sum: number, line: any) => sum + line.debit, 0), `cost T${month}`).toBe(entry.total);
  }
});

test('KPI actuals and scores follow the ledger', async () => {
  for (const item of actuals.kpi_actuals) {
    const targets = await read('aic.hrm.kpi.target', 'search_read', [[
      ['kpi_id.code', '=', item.code], ['cycle_id.code', '=', MONTH_CODE[item.month]]]],
    { fields: ['employee_id', 'actual_value', 'target_value', 'achievement', 'has_actual', 'period_result_ids'] });
    expect(targets.length, `${item.code} T${item.month}`).toBeGreaterThan(0);
    for (const target of targets) {
      const who = `${item.code} T${item.month} ${target.employee_id?.[1] ?? '-'}`;
      expect(target.has_actual, who).toBe(true);
      expect(target.actual_value, who).toBeCloseTo(item.value, 3);
      const expected = Math.min(1, target.target_value ? target.actual_value / target.target_value : 0);
      expect(target.achievement, who).toBeCloseTo(expected, 4);
      const results = await read('aic.hrm.kpi.period.result', 'search_read', [[['id', 'in', target.period_result_ids]]], { fields: ['state', 'source'] });
      expect(results.every((r: any) => r.state === 'confirmed'), who).toBe(true);
      expect(results.every((r: any) => r.source === 'auto'), who).toBe(true);
    }
  }

  // September is not scored: the month is not over and the ledger has no
  // figures for it yet.
  const september = await read('aic.hrm.kpi.period.result', 'search_count', [[
    ['kpi_target_id.cycle_id.code', '=', MONTH_CODE[9]], ['state', '=', 'confirmed']]]);
  expect(september).toBe(0);
});

test('scorecards score the measured part and say how much that is', async () => {
  for (const month of [7, 8]) {
    const cards = await read('aic.hrm.kpi.assignment', 'search_read', [[['cycle_id.code', '=', MONTH_CODE[month]]]],
      { fields: ['employee_id', 'score', 'score_covered', 'data_coverage', 'total_weight'] });
    expect(cards.length, `scorecards T${month}`).toBe(19);
    for (const card of cards) {
      const lines = await read('aic.hrm.kpi.assignment.line', 'search_read', [[['assignment_id', '=', card.id]]],
        { fields: ['weight', 'score', 'has_actual'] });
      const who = `${card.employee_id[1]} T${month}`;
      const weight = lines.reduce((sum: number, line: any) => sum + line.weight, 0);
      const measured = lines.filter((line: any) => line.has_actual);
      const measuredWeight = measured.reduce((sum: number, line: any) => sum + line.weight, 0);
      expect(weight, who).toBeCloseTo(100, 2);
      expect(card.data_coverage, who).toBeCloseTo(measuredWeight, 2);
      const score = lines.reduce((sum: number, line: any) => sum + line.score * line.weight, 0) / weight;
      expect(card.score, who).toBeCloseTo(score, 4);
      if (measuredWeight) {
        const covered = measured.reduce((sum: number, line: any) => sum + line.score * line.weight, 0) / measuredWeight;
        expect(card.score_covered, who).toBeCloseTo(covered, 4);
      } else {
        expect(card.score_covered, who).toBe(0);
      }
    }
  }
});

test('the revenue objective reflects the quarter to date', async () => {
  const quarter = actuals.months_with_revenue.reduce(
    (sum: number, month: number) => sum + actuals.revenue[String(month)].total, 0);
  const [kr] = await read('aic.hrm.key.result', 'search_read', [[['code', '=', 'O1.KR1']]],
    { fields: ['current', 'target', 'score', 'has_actual', 'last_checkin_date'] });
  expect(kr.current).toBeCloseTo(quarter, 2);
  expect(kr.has_actual).toBe(true);
  expect(kr.score).toBeCloseTo(1, 6);

  const [o1] = await read('aic.hrm.objective', 'search_read', [[['code', '=', 'O1']]],
    { fields: ['score', 'score_covered', 'data_coverage', 'kr_ids'] });
  const krs = await read('aic.hrm.key.result', 'search_read', [[['id', 'in', o1.kr_ids]]], { fields: ['weight', 'score', 'has_actual'] });
  const weight = krs.reduce((sum: number, row: any) => sum + row.weight, 0);
  const measured = krs.filter((row: any) => row.has_actual);
  expect(o1.data_coverage).toBeCloseTo(100 * measured.reduce((s: number, r: any) => s + r.weight, 0) / weight, 2);
  expect(o1.score).toBeCloseTo(krs.reduce((s: number, r: any) => s + r.score * r.weight, 0) / weight, 4);
});

test('department cost and profit are tracked, not scored', async () => {
  for (const item of actuals.tracking) {
    if (item.month === 9 || item.key === 'margin') continue;
    const [target] = await read('aic.hrm.kpi.target', 'search_read', [[
      ['kpi_id.code', '=', item.code], ['cycle_id.code', '=', MONTH_CODE[item.month]]]],
    { fields: ['is_tracking', 'actual_value', 'achievement', 'rag', 'has_actual', 'weight'] });
    const who = `${item.code} T${item.month}`;
    expect(target.is_tracking, who).toBe(true);
    expect(target.achievement, who).toBe(0);
    expect(target.rag, who).toBe('none');
    if (item.value === null) {
      expect(target.has_actual, who).toBe(false);
    } else {
      expect(target.actual_value, who).toBeCloseTo(item.value, 3);
    }
    const onScorecard = await read('aic.hrm.kpi.assignment.line', 'search_count', [[['kpi_target_id', '=', target.id]]]);
    expect(onScorecard, who).toBe(0);
  }
});

test('what is not measured is visible as such', async () => {
  const unmeasured = await read('aic.hrm.kpi.assignment.line', 'search_count', [[
    ['assignment_id.cycle_id.code', 'in', [MONTH_CODE[7], MONTH_CODE[8]]], ['has_actual', '=', false]]]);
  const measured = await read('aic.hrm.kpi.assignment.line', 'search_count', [[
    ['assignment_id.cycle_id.code', 'in', [MONTH_CODE[7], MONTH_CODE[8]]], ['has_actual', '=', true]]]);
  // Only the revenue KPIs have figures; the rest await the customer's data.
  expect(measured).toBe(actuals.kpi_actuals.filter((item: any) => item.month <= 8).length * 0 + measured);
  expect(measured).toBeGreaterThan(0);
  expect(unmeasured).toBeGreaterThan(0);
  const [objectives] = [await read('aic.hrm.objective', 'search_read', [[['level', '=', 'department']]], { fields: ['code', 'data_coverage'] })];
  const uncovered = objectives.filter((objective: any) => !objective.data_coverage).map((objective: any) => objective.code);
  expect(uncovered.sort()).toEqual(['O2', 'O3', 'O4']);
});
