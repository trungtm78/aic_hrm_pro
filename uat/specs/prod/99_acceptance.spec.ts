import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { chromium, devices } from '@playwright/test';
import { test, expect, read, ALL, login, dataset, PROD_URL } from '../../fixtures/prod';
import { horizontalOverflow } from '../../pages/odoo';

/**
 * Acceptance of the production dataset, independent of the specs that built it.
 *
 * Expectations come from the customer's documents (through the extracted
 * dataset) and from the account sheet handed to the customer - never from the
 * data-entry specs. Nothing here writes; the only actions are logins.
 */

const data = dataset();
const TRIAL_CUTOFF = '2026-09-17 09:13:07';
const SHEET = resolve(__dirname, '..', '..', '..', 'Docs', 'OKR', 'Tai_khoan_KDDV_okr.aipower.vn.xlsx');

function accountSheet(): Array<{ code: string; name: string; login: string; password: string; role: string }> {
  const script = [
    'import json, sys, openpyxl',
    'sheet = openpyxl.load_workbook(sys.argv[1], data_only=True).active',
    'rows = [r for r in sheet.iter_rows(min_row=5, values_only=True) if r[1]]',
    'print(json.dumps([dict(code=r[1], name=r[2], login=r[5], password=r[6], role=r[7]) for r in rows], ensure_ascii=False))',
  ].join('\n');
  return JSON.parse(execFileSync('py', ['-3.12', '-c', script, SHEET], { encoding: 'utf-8' }));
}

async function visibleRecordCount(page: any, model: string): Promise<number> {
  const [action] = await read('ir.actions.act_window', 'search_read',
    [[['res_model', '=', model], ['view_mode', 'ilike', 'list']]], { fields: ['id'], limit: 1, order: 'id' });
  await page.goto(`/odoo/action-${action.id}`);
  await page.locator('.o_list_view, .o_view_nocontent').first().waitFor({ timeout: 60_000 });
  const facets = page.locator('.o_searchview_facet .o_facet_remove');
  while (await facets.count()) {
    await facets.first().click();
    await page.waitForTimeout(700);
  }
  await page.waitForTimeout(1500);
  const limit = page.locator('.o_pager_limit');
  if (await limit.isVisible().catch(() => false)) return Number((await limit.innerText()).trim());
  return page.locator('.o_list_view .o_data_row').count();
}

test.describe.configure({ mode: 'serial' });

test('no trial data is left, module data is intact', async () => {
  for (const model of ['aic.hrm.cycle', 'aic.hrm.objective', 'aic.hrm.key.result', 'aic.hrm.kpi.target',
    'aic.hrm.kpi.assignment', 'aic.hrm.checkin', 'aic.hrm.review', 'aic.hrm.review.form', 'aic.hrm.team',
    'hr.department', 'hr.job']) {
    const kept = (await read('ir.model.data', 'search_read', [[['model', '=', model]]], { fields: ['res_id'] }))
      .map((row: any) => row.res_id);
    const trial = await read(model, 'search_count', [[['create_date', '<', TRIAL_CUTOFF], ['id', 'not in', kept]]], ALL);
    expect(trial, `${model} trial records`).toBe(0);
  }
  const trialPeople = await read('hr.employee', 'search_count', [[['create_date', '<', TRIAL_CUTOFF], ['user_id.login', '!=', 'admin']]], ALL);
  expect(trialPeople).toBe(0);
  expect(await read('aic.hrm.kpi', 'search_count', [[['is_template', '=', true]]], ALL)).toBe(114);
  expect(await read('aic.hrm.kr.template', 'search_count', [[]], ALL)).toBe(150);
});

test('organisation matches the staff workbook', async () => {
  const [company] = await read('res.company', 'search_read', [[]], { fields: ['name'], order: 'id', limit: 1 });
  expect(company.name).toBe(data.company);
  for (const department of data.departments) {
    const [row] = await read('hr.department', 'search_read', [[['name', '=', department.name]]], { fields: ['manager_id'] });
    expect(row, department.code).toBeTruthy();
    expect(row.manager_id ? row.manager_id[1] : null, department.code).toBe(department.manager);
  }
  for (const employee of data.employees) {
    const rows = await read('hr.employee', 'search_read', [[['barcode', '=', employee.code]]], {
      fields: ['name', 'work_email', 'department_id', 'job_title', 'job_id', 'parent_id', 'user_id'] });
    expect(rows.length, employee.code).toBe(1);
    const [row] = rows;
    expect([row.name, row.work_email, row.department_id[1], row.job_title, row.parent_id ? row.parent_id[1] : null])
      .toEqual([employee.name, employee.email, 'Kinh doanh và Dịch vụ', employee.job_title, employee.manager]);
    expect(row.job_id[1], employee.code).toBe(employee.position_title);
    expect(row.user_id, `${employee.code} has a login`).toBeTruthy();
  }
});

test('every account on the customer sheet logs in', async () => {
  const sheet = accountSheet();
  expect(sheet.map((row) => row.code).sort()).toEqual(data.employees.map((e: any) => e.code).sort());
  const browser = await chromium.launch();
  try {
    for (const account of sheet) {
      const context = await browser.newContext({ baseURL: PROD_URL, locale: 'vi-VN' });
      const page = await context.newPage();
      await page.route(/\/(longpolling|bus)\/|\/websocket/, (route) => route.abort());
      await login(page, account.login, account.password);
      await expect(page).not.toHaveURL(/\/web\/login/);
      await context.close();
    }
  } finally {
    await browser.close();
  }
});

test('OKR matches Appendix 5 of the signed decision', async () => {
  const [quarter] = await read('aic.hrm.cycle', 'search_read', [[['code', '=', 'KDDV-2026-Q3']]], { fields: ['state'] });
  expect(quarter.state).toBe('open');
  const objectives = await read('aic.hrm.objective', 'search_read', [[['cycle_id', '=', quarter.id]]], {
    fields: ['code', 'name', 'weight', 'state', 'level'] });
  expect(objectives.length).toBe(4);
  expect(objectives.reduce((sum: number, o: any) => sum + o.weight, 0)).toBe(100);
  for (const spec of data.objectives) {
    const objective = objectives.find((o: any) => o.code === spec.code);
    expect([objective.name, objective.weight, objective.level, objective.state])
      .toEqual([spec.name, spec.weight, 'department', 'in_progress']);
    const krs = await read('aic.hrm.key.result', 'search_read', [[['objective_id', '=', objective.id]]], {
      fields: ['code', 'name', 'weight', 'note'] });
    expect(krs.map((kr: any) => kr.code).sort()).toEqual(spec.key_results.map((kr: any) => kr.code).sort());
    for (const kr of spec.key_results) {
      const row = krs.find((r: any) => r.code === kr.code);
      expect([row.name, row.weight]).toEqual([kr.name, kr.weight]);
      expect(row.note).toContain(kr.criterion);
    }
  }
});

test('scorecards: every person, every month, both weight levels', async () => {
  const expected: Record<number, number> = { 7: 19, 8: 19, 9: 20 };
  for (const [month, count] of Object.entries(expected)) {
    const code = `KDDV-2026-${String(month).padStart(2, '0')}`;
    const cards = await read('aic.hrm.kpi.assignment', 'search_read', [[['cycle_id.code', '=', code]]], {
      fields: ['employee_id', 'weight_ok', 'total_weight', 'line_ids', 'group_ids'] });
    expect(cards.length, code).toBe(count);
    for (const card of cards) {
      const plan = data.scorecards.find((c: any) => c.month === Number(month) && c.employee === card.employee_id[1]);
      expect(plan, `${card.employee_id[1]} ${code} is in the plan`).toBeTruthy();
      expect(card.weight_ok, `${card.employee_id[1]} ${code}`).toBe(true);
      expect(card.total_weight).toBeCloseTo(100, 2);
      expect(card.group_ids.length).toBe(plan.groups.length);
      expect(card.line_ids.length).toBe(plan.groups.reduce((n: number, g: any) => n + g.lines.length, 0));
    }
  }
  const driver = data.employees.find((e: any) => e.position === 'LX').name;
  expect(await read('aic.hrm.kpi.assignment', 'search_count', [[['employee_id.name', '=', driver]]])).toBe(0);
  const lateJoiner = data.employees.find((e: any) => e.kpi_months.length === 1).name;
  const lateCards = await read('aic.hrm.kpi.assignment', 'search_read', [[['employee_id.name', '=', lateJoiner]]], { fields: ['cycle_id'] });
  expect(lateCards.map((c: any) => c.cycle_id[1])).toEqual(['Tháng 9/2026']);
});

test('access: a member sees only their own scorecards, the head sees the department', async () => {
  const sheet = accountSheet();
  const browser = await chromium.launch();
  try {
    const member = sheet.find((row) => row.name === 'Vũ Quang')!;
    const head = sheet.find((row) => row.name === data.employees.find((e: any) => !e.manager).name)!;
    for (const [account, expected] of [[member, 3], [head, 58]] as const) {
      const context = await browser.newContext({ baseURL: PROD_URL, locale: 'vi-VN', viewport: { width: 1440, height: 900 } });
      const page = await context.newPage();
      await page.route(/\/(longpolling|bus)\/|\/websocket/, (route) => route.abort());
      await login(page, account.login, account.password);
      expect(await visibleRecordCount(page, 'aic.hrm.kpi.assignment'), account.name).toBe(expected);
      await context.close();
    }
  } finally {
    await browser.close();
  }
});

test('the scorecard screen works on a phone', async () => {
  const sheet = accountSheet();
  const member = sheet.find((row) => row.name === 'Vũ Quang')!;
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({ ...devices['iPhone 12'], baseURL: PROD_URL, locale: 'vi-VN',
      viewport: { width: 375, height: 812 } });
    const page = await context.newPage();
    await page.route(/\/(longpolling|bus)\/|\/websocket/, (route) => route.abort());
    await login(page, member.login, member.password);
    const [card] = await read('aic.hrm.kpi.assignment', 'search_read',
      [[['employee_id.name', '=', 'Vũ Quang'], ['cycle_id.code', '=', 'KDDV-2026-09']]], { fields: ['id'] });
    const [action] = await read('ir.actions.act_window', 'search_read',
      [[['res_model', '=', 'aic.hrm.kpi.assignment'], ['view_mode', 'ilike', 'list']]], { fields: ['id'], limit: 1, order: 'id' });
    await page.goto(`/odoo/action-${action.id}/${card.id}`);
    await page.locator('.o_form_view').first().waitFor({ timeout: 60_000 });
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
    await context.close();
  } finally {
    await browser.close();
  }
});
