import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Page } from '@playwright/test';
import { test, expect, read, loginAsAdmin } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * The department's KPIs read their actuals from accounting.
 *
 * Metric sources sum posted journal items: revenue by stream from the 5113x
 * accounts (credit balance, so multiplied by -1e-9 to get billions), cost from
 * the debit lines of the cost journal, gross profit from both. Each revenue
 * KPI target of July, August and September gets its source; July and August
 * are pulled now and confirmed by a manager, September is left to the nightly
 * pull until the month has ended. Department cost and gross profit are
 * tracking-only targets. The quarter's revenue key result gets a check-in of
 * the quarter-to-date revenue read from the confirmed KPI results.
 */

const actuals = JSON.parse(readFileSync(resolve(__dirname, '..', '..', 'data', 'kddv_actuals_q3_2026.json'), 'utf-8'));
const MONTHS = ['KDDV-2026-07', 'KDDV-2026-08'];
const ALL_MONTHS = [...MONTHS, 'KDDV-2026-09'];
const REVENUE = '-0,000000001';
const posted = "('parent_state', '=', 'posted')";
const account = (prefix: string) => `('account_id.code', '=like', '${prefix}%')`;

const SOURCES = [
  { name: 'KDDV — DT Telco/ISP (TK 51131)', field: 'balance', multiplier: REVENUE, domain: `[${posted}, ${account('51131')}]` },
  { name: 'KDDV — DT VTVshop MG (TK 51132)', field: 'balance', multiplier: REVENUE, domain: `[${posted}, ${account('51132')}]` },
  { name: 'KDDV — DT DV TNND (TK 51133)', field: 'balance', multiplier: REVENUE, domain: `[${posted}, ${account('51133')}]` },
  { name: 'KDDV — DT FAST & Chuyên trang (TK 51134)', field: 'balance', multiplier: REVENUE, domain: `[${posted}, ${account('51134')}]` },
  { name: 'KDDV — DT TNND + FAST + DV số (TK 51133-51135)', field: 'balance', multiplier: REVENUE,
    domain: `['&', ${posted}, '|', '|', ${account('51133')}, ${account('51134')}, ${account('51135')}]` },
  { name: 'KDDV — Tổng doanh thu phòng (TK 5113)', field: 'balance', multiplier: REVENUE, domain: `[${posted}, ${account('5113')}]` },
  { name: 'KDDV — Chi phí (sổ CPTH, phát sinh Nợ)', field: 'debit', multiplier: '0,000000001',
    domain: `[${posted}, ('journal_id.code', '=', 'CPTH'), ('debit', '>', 0)]` },
  { name: 'KDDV — Lợi nhuận gộp (DT 5113 − CP sổ CPTH)', field: 'balance', multiplier: REVENUE,
    domain: `['&', ${posted}, '|', ${account('5113')}, '&', ('journal_id.code', '=', 'CPTH'), ('debit', '>', 0)]` },
];

const KPI_SOURCE: Record<string, string> = {
  'KDDV.TP-KD.B1.1': SOURCES[5].name,
  'KDDV.TP-KD.B1.2': SOURCES[0].name,
  'KDDV.TP-KD.B1.3': SOURCES[1].name,
  'KDDV.TP-KD.B1.4': SOURCES[4].name,
  'KDDV.PPT-KD.B1.1': SOURCES[2].name,
  'KDDV.PPT-KD.B1.2': SOURCES[3].name,
  'KDDV.CV-KD1.B1.1': SOURCES[0].name,
  'KDDV.CV-KD1.B1.2': SOURCES[1].name,
  'KDDV.CV-KD2.B1.1': SOURCES[2].name,
  'KDDV.CV-KD2.B1.3': SOURCES[3].name,
  'KDDV.CV-KD2.B2.3': SOURCES[3].name,
};

const TRACKING = [
  { key: 'cost', source: SOURCES[6].name, ...actuals.tracking.find((t: any) => t.key === 'cost') },
  { key: 'gross_profit', source: SOURCES[7].name, ...actuals.tracking.find((t: any) => t.key === 'gross_profit') },
];

async function xmlid(name: string): Promise<number> {
  const [module, ref] = name.split('.');
  const [row] = await read('ir.model.data', 'search_read', [[['module', '=', module], ['name', '=', ref]]], { fields: ['res_id'] });
  if (!row) throw new Error(`No record ${name}`);
  return row.res_id;
}

async function setDomain(page: Page, domain: string) {
  // Developer mode shows the domain's code editor next to the tree editor.
  const widget = page.locator('.o_field_widget[name="domain"]').first();
  const editor = widget.locator('textarea').first();
  if (!(await editor.isVisible().catch(() => false))) {
    await widget.getByText(/Trình soạn thảo mã|Code editor/).first().click();
  }
  await editor.fill(domain);
  await editor.blur();
}

test('KPI actuals pulled from the ledger', async ({ page }) => {
  test.setTimeout(2 * 60 * 60_000);
  const ui = new OdooUi(page);
  await loginAsAdmin(page);

  await test.step('journal items may feed metric sources', async () => {
    const lineModel = await read('ir.model', 'search_read', [[['model', '=', 'account.move.line']]], { fields: ['display_name'], context: { lang: 'vi_VN' } });
    if (await read('aic.hrm.metric.allowed.model', 'search_count', [[['model_id', '=', lineModel[0].id]]])) return;
    await ui.openAction(await xmlid('aic_hrm_base.action_aic_hrm_metric_allowed_model'));
    await page.locator('.o_list_button_add:visible').first().click();
    const row = page.locator('.o_selected_row').first();
    await ui.pickMany2one('model_id', 'account.move.line', row, new RegExp(lineModel[0].display_name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    await ui.rpc('web_save', 'allowlist journal items', () => page.locator('.o_list_button_save:visible').first().click());
  });

  const [lineModelRow] = await read('ir.model', 'search_read', [[['model', '=', 'account.move.line']]], { fields: ['display_name'], context: { lang: 'vi_VN' } });
  const lineModelName = new RegExp(`^\\s*${lineModelRow.display_name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*$`);
  const sourceAction = await xmlid('aic_hrm_base.action_aic_hrm_metric_source');
  await ui.gotoWithRetry(`/odoo/action-${sourceAction}?debug=1`);
  for (const source of SOURCES) {
    await test.step(`metric source ${source.name}`, async () => {
      if (await read('aic.hrm.metric.source', 'search_count', [[['name', '=', source.name]]])) return;
      await ui.newRecord(sourceAction);
      await ui.fill('name', source.name);
      await ui.pickMany2one('model_id', 'account.move.line', undefined, lineModelName);
      await ui.fill('field_name', source.field);
      await ui.select('aic.hrm.metric.source', 'aggregate', 'sum');
      await ui.fill('multiplier', source.multiplier);
      await ui.fill('date_field', 'date');
      await setDomain(page, source.domain);
      await ui.save(source.name);
    });
  }

  const sources: Record<string, number> = {};
  for (const row of await read('aic.hrm.metric.source', 'search_read', [[['name', 'like', 'KDDV — ']]], { fields: ['name', 'domain', 'multiplier', 'field_name'] })) {
    sources[row.name] = row.id;
    const spec = SOURCES.find((s) => s.name === row.name)!;
    expect(row.field_name).toBe(spec.field);
    expect(row.domain.replace(/\s/g, '')).toBe(spec.domain.replace(/\s/g, ''));
    expect(Math.abs(row.multiplier) * 1e9).toBeCloseTo(1, 6);
  }

  const cycles: Record<string, number> = {};
  for (const row of await read('aic.hrm.cycle', 'search_read', [[['code', 'in', ALL_MONTHS]]], { fields: ['code'] })) cycles[row.code] = row.id;
  const targetAction = await xmlid('aic_okr_kpi.action_aic_hrm_kpi_target');

  await test.step('tracking indicators for the department', async () => {
    const kpiAction = await xmlid('aic_okr_kpi.action_aic_hrm_kpi');
    // An earlier run quick-created a KPI named after a code from a many2one
    // "Create" entry; remove such strays through their form.
    for (const stray of await read('aic.hrm.kpi', 'search_read', [[['name', 'in', TRACKING.map((t) => t.code)]]], { fields: ['id'] })) {
      await ui.openRecord(kpiAction, stray.id);
      await ui.deleteOpenRecord(`stray KPI ${stray.id}`);
    }
    for (const item of TRACKING) {
      let [kpi] = await read('aic.hrm.kpi', 'search_read', [[['code', '=', item.code]]], { fields: ['id'] });
      if (!kpi) {
        await ui.newRecord(kpiAction);
        await ui.fill('name', item.name);
        await ui.fill('code', item.code);
        await ui.check('is_template', false);
        await ui.select('aic.hrm.kpi', 'direction', item.direction);
        await ui.select('aic.hrm.kpi', 'aggregation', 'last');
        await ui.fill('unit', item.unit);
        kpi = { id: await ui.save(item.code) };
      }
      for (const code of ALL_MONTHS) {
        const exists = await read('aic.hrm.kpi.target', 'search_count', [[['kpi_id', '=', kpi.id], ['cycle_id', '=', cycles[code]], ['employee_id', '=', false]]]);
        if (exists) continue;
        await ui.newRecord(targetAction);
        const [kpiRow] = await read('aic.hrm.kpi', 'read', [[kpi.id]], { fields: ['display_name'] });
        const [cycleRow] = await read('aic.hrm.cycle', 'read', [[cycles[code]]], { fields: ['display_name'] });
        await ui.pickMany2one('kpi_id', kpiRow.display_name);
        await ui.pickMany2one('cycle_id', cycleRow.display_name);
        await ui.check('is_tracking', true);
        await ui.fill('weight', 0);
        await ui.fill('target_value', 0);
        await ui.fill('target_note', 'Chỉ số theo dõi cấp phòng, không chấm điểm; số sổ kế toán, cần xác nhận phạm vi phòng');
        await ui.tab(/Cách thu thập|How to Collect/);
        await ui.pickMany2one('metric_source_id', item.source);
        await ui.save(`${item.code} ${code}`);
      }
    }
  });

  const targets = await read('aic.hrm.kpi.target', 'search_read', [[
    ['cycle_id', 'in', Object.values(cycles)],
    '|', ['kpi_id.code', 'in', Object.keys(KPI_SOURCE)], ['kpi_id.code', 'in', TRACKING.map((t) => t.code)]]],
  { fields: ['kpi_id', 'cycle_id', 'employee_id', 'metric_source_id', 'display_label'] });

  for (const target of targets) {
    const code = target.kpi_id[1].split(' ')[0];
    const [kpi] = await read('aic.hrm.kpi', 'read', [[target.kpi_id[0]]], { fields: ['code'] });
    const sourceName = KPI_SOURCE[kpi.code] ?? TRACKING.find((t) => t.code === kpi.code)!.source;
    await test.step(`source on ${target.display_label} ${target.cycle_id[1]}`, async () => {
      if (target.metric_source_id?.[0] === sources[sourceName]) return;
      await ui.openRecord(targetAction, target.id);
      await ui.tab(/Cách thu thập|How to Collect/);
      await ui.pickMany2one('metric_source_id', sourceName);
      await ui.save(`source ${code}`);
    });
  }

  // Cost exists only up to July: pulling August would record a cost of 0 and
  // a "profit" equal to revenue. Those months stay empty until the ledger has
  // them.
  const monthOf = (t: any) => ALL_MONTHS.find((c) => cycles[c] === t.cycle_id[0])!;
  const trackingCodes = new Set(TRACKING.map((t) => t.code));
  const pulled = targets.filter((t: any) => {
    if (!MONTHS.includes(monthOf(t))) return false;
    if (!trackingCodes.has(t.kpi_id[1].split(' ')[0]) && !TRACKING.some((item) => t.display_label.startsWith(item.code))) return true;
    const item = TRACKING.find((i) => t.display_label.startsWith(i.code))!;
    const month = Number(monthOf(t).slice(-2));
    return actuals.tracking.find((x: any) => x.key === item.key && x.month === month).value !== null;
  });
  for (const target of pulled) {
    await test.step(`pull ${target.display_label} ${target.cycle_id[1]}`, async () => {
      const results = await read('aic.hrm.kpi.period.result', 'search_read', [[['kpi_target_id', '=', target.id]]], { fields: ['state'] });
      if (results.some((r: any) => r.state === 'confirmed')) return;
      await ui.openRecord(targetAction, target.id);
      await ui.clickButton('action_pull_metric_actuals', `pull ${target.display_label}`);
    });
  }

  await test.step('manager confirms July and August', async () => {
    const drafts = await read('aic.hrm.kpi.period.result', 'search_read', [[
      ['kpi_target_id', 'in', pulled.map((t: any) => t.id)], ['state', '=', 'draft']]], { fields: ['id'] });
    if (!drafts.length) return;
    await ui.openAction(await xmlid('aic_okr_kpi.action_aic_hrm_period_result'));
    const search = page.locator('.o_searchview_input').first();
    await search.fill('KDDV.');
    await search.press('Enter');
    await page.locator('.o_searchview_facet').first().waitFor();
    const draftFilter = page.locator('.o_searchview_dropdown_toggler, .o_searchview_dropdown_toggle').first();
    await draftFilter.click();
    await page.locator('.o-dropdown-item, .dropdown-item').filter({ hasText: /^\s*(Nháp|Draft)\s*$/ }).first().click();
    await page.keyboard.press('Escape');
    await expect(page.locator('.o_list_view .o_data_row')).toHaveCount(drafts.length, { timeout: 60_000 });
    await page.locator('.o_list_view thead .o_list_record_selector input').first().check();
    await ui.rpc('action_confirm', 'confirm KDDV results', () =>
      page.locator('.o_control_panel button[name="action_confirm"], .o_list_view button[name="action_confirm"]').first().click());
    expect(await read('aic.hrm.kpi.period.result', 'search_count', [[
      ['kpi_target_id', 'in', pulled.map((t: any) => t.id)], ['state', '=', 'draft']]])).toBe(0);
  });

  await test.step('quarter revenue check-in on O1.KR1', async () => {
    const [kr] = await read('aic.hrm.key.result', 'search_read', [[['code', '=', 'O1.KR1'], ['objective_id.department_id.name', 'ilike', 'Kinh doanh']]], { fields: ['display_name', 'last_checkin_date', 'current'] });
    const monthly = await read('aic.hrm.kpi.target', 'search_read', [[
      ['kpi_id.code', '=', 'KDDV.TP-KD.B1.1'], ['cycle_id', 'in', MONTHS.map((c) => cycles[c])]]], { fields: ['actual_value', 'cycle_id', 'has_actual'] });
    expect(monthly.every((t: any) => t.has_actual)).toBe(true);
    const total = Math.round(monthly.reduce((sum: number, t: any) => sum + t.actual_value, 0) * 100) / 100;
    if (kr.last_checkin_date === '2026-08-31' && Math.abs(kr.current - total) < 0.005) return;
    await ui.newRecord(await xmlid('aic_okr_kpi.action_aic_hrm_checkin'));
    await ui.pickMany2one('kr_id', kr.display_name.slice(0, 40), undefined, new RegExp(`^\\s*${kr.display_name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`));
    const dateButton = ui.field('date').locator('button').first();
    if (await dateButton.isVisible().catch(() => false)) await dateButton.click();
    await ui.fill('date', '31/08/2026');
    await page.keyboard.press('Escape');
    await ui.fill('value_current', total);
    await ui.fill('note', `Doanh thu Quý III/2026 lũy kế đến hết T8, đọc từ kế toán (hoá đơn đã vào sổ + bút toán dự thu, chưa VAT): `
      + monthly.map((t: any) => `${t.cycle_id[1]} ${String(t.actual_value.toFixed(2)).replace('.', ',')} tỷ`).join(' + ')
      + '. T7 có hoá đơn gộp quý (VNPT, VTVshop MG) và T8 có doanh thu chưa xuất HĐ cần kế toán xác nhận.');
    await ui.save('O1.KR1 check-in');
    const [after] = await read('aic.hrm.key.result', 'read', [[kr.id]], { fields: ['current'] });
    expect(after.current).toBeCloseTo(total, 2);
  });

  await test.step('pulled actuals equal the register', async () => {
    for (const item of actuals.kpi_actuals) {
      const cycle = cycles[`KDDV-2026-0${item.month}`];
      const rows = await read('aic.hrm.kpi.target', 'search_read', [[['kpi_id.code', '=', item.code], ['cycle_id', '=', cycle]]], { fields: ['actual_value', 'has_actual', 'employee_id'] });
      expect(rows.length, `${item.code} T${item.month}`).toBeGreaterThan(0);
      for (const row of rows) {
        expect(row.has_actual, `${item.code} T${item.month} ${row.employee_id[1]}`).toBe(true);
        expect(row.actual_value, `${item.code} T${item.month} ${row.employee_id[1]}`).toBeCloseTo(item.value, 3);
      }
    }
    for (const item of TRACKING) {
      for (const month of [7, 8]) {
        const expected = actuals.tracking.find((t: any) => t.key === item.key && t.month === month).value;
        const [row] = await read('aic.hrm.kpi.target', 'search_read', [[['kpi_id.code', '=', item.code], ['cycle_id', '=', cycles[`KDDV-2026-0${month}`]]]], { fields: ['actual_value', 'rag'] });
        expect(row.rag).toBe('none');
        if (expected !== null) expect(row.actual_value, `${item.code} T${month}`).toBeCloseTo(expected, 3);
      }
    }
  });
});
