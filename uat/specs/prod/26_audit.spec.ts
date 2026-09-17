import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { chromium } from '@playwright/test';
import { test, expect, read, loginAsAdmin, login, PROD_URL, PROD_DB } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * The controls that make a score defensible, checked on the live instance.
 *
 * Every confirmed figure has a confirmer and a first audit event; withdrawing
 * one demands a reason and leaves a trail that nobody can rewrite; a member of
 * the department is not offered the confirm button at all. The one figure this
 * spec withdraws is put back afterwards, so the department's scores are the
 * same before and after.
 */

const ACCOUNTS = resolve(__dirname, '..', '..', 'data', 'kddv_accounts.json');
const REASON = 'Kiểm thử chốt kiểm soát: huỷ xác nhận có lý do rồi xác nhận lại ngay, số liệu không đổi.';

async function xmlid(name: string): Promise<number> {
  const [module, ref] = name.split('.');
  const [row] = await read('ir.model.data', 'search_read', [[['module', '=', module], ['name', '=', ref]]], { fields: ['res_id'] });
  if (!row) throw new Error(`No record ${name}`);
  return row.res_id;
}

test('every confirmed figure carries its confirmer and its history', async () => {
  const confirmed = await read('aic.hrm.kpi.period.result', 'search_read', [[['state', '=', 'confirmed']]],
    { fields: ['kpi_target_id', 'confirmed_by', 'confirmed_on'] });
  expect(confirmed.length).toBeGreaterThan(0);
  for (const result of confirmed) {
    expect(result.confirmed_by, `${result.kpi_target_id[1]}: confirmer`).toBeTruthy();
    expect(result.confirmed_on, `${result.kpi_target_id[1]}: confirmed at`).toBeTruthy();
    const events = await read('aic.hrm.kpi.result.audit', 'search_count', [[['result_id', '=', result.id]]]);
    expect(events, `${result.kpi_target_id[1]}: audit events`).toBeGreaterThan(0);
  }
});

test('withdrawing a confirmation needs a reason and leaves a trail', async ({ page }) => {
  test.setTimeout(20 * 60_000);
  const ui = new OdooUi(page);
  await loginAsAdmin(page);
  const resultAction = await xmlid('aic_okr_kpi.action_aic_hrm_period_result');
  const auditAction = await xmlid('aic_okr_kpi.action_aic_hrm_result_audit');

  // The least consequential figure to touch: a department tracking indicator,
  // which carries no score for any person.
  const [result] = await read('aic.hrm.kpi.period.result', 'search_read', [[
    ['state', '=', 'confirmed'], ['kpi_target_id.kpi_id.code', '=', 'KDDV.PHONG.CP']]],
  { fields: ['kpi_target_id', 'actual', 'date_from'] });
  expect(result, 'the cost tracking figure must exist').toBeTruthy();
  const before = await read('aic.hrm.kpi.result.audit', 'search_count', [[['result_id', '=', result.id]]]);

  await test.step('withdraw it through the wizard', async () => {
    await ui.openAction(resultAction);
    const search = page.locator('.o_searchview_input').first();
    await search.fill('KDDV.PHONG.CP');
    await search.press('Enter');
    await page.locator('.o_searchview_facet').first().waitFor();
    const row = page.locator('.o_list_view .o_data_row').filter({ hasText: /Đã xác nhận|Confirmed/ }).first();
    await row.locator('.o_list_record_selector input').check();
    await page.locator('.o_control_panel button[name="action_open_reset_wizard"], .o_list_view button[name="action_open_reset_wizard"]')
      .first().click();
    const dialog = page.locator('.modal-dialog').last();
    await dialog.waitFor();
    // The reason is mandatory: the wizard refuses an empty one.
    await dialog.locator('.modal-footer button[name="action_reset"]').first().click();
    await expect(page.locator('.o_notification, .o_dialog_error, .modal-dialog').last()).toBeVisible();
    await ui.fill('reason', REASON, dialog);
    await ui.rpc('action_reset', 'withdraw confirmation', () =>
      dialog.locator('.modal-footer button[name="action_reset"]').first().click());
  });

  const [withdrawn] = await read('aic.hrm.kpi.period.result', 'read', [[result.id]],
    { fields: ['state', 'confirmed_by', 'actual'] });
  expect(withdrawn.state).toBe('draft');
  expect(withdrawn.confirmed_by).toBeFalsy();
  expect(withdrawn.actual).toBeCloseTo(result.actual, 6);

  const [reset] = await read('aic.hrm.kpi.result.audit', 'search_read', [[
    ['result_id', '=', result.id], ['action', '=', 'reset']]],
  { fields: ['reason', 'user_id', 'old_state', 'new_state', 'event_date', 'evidence_checksum'] });
  expect(reset.reason).toContain('Kiểm thử chốt kiểm soát');
  expect([reset.old_state, reset.new_state]).toEqual(['confirmed', 'draft']);
  expect(reset.evidence_checksum).toHaveLength(64);

  await test.step('the KPI keeps the note on its chatter', async () => {
    const messages = await read('mail.message', 'search_read', [[
      ['model', '=', 'aic.hrm.kpi.target'], ['res_id', '=', result.kpi_target_id[0]]]], { fields: ['body'] });
    expect(messages.map((m: any) => m.body).join(' ')).toContain('Kiểm thử chốt kiểm soát');
  });

  await test.step('put it back, so nothing is left changed', async () => {
    await ui.openAction(resultAction);
    const search = page.locator('.o_searchview_input').first();
    await search.fill('KDDV.PHONG.CP');
    await search.press('Enter');
    await page.locator('.o_searchview_facet').first().waitFor();
    const row = page.locator('.o_list_view .o_data_row').filter({ hasText: /Nháp|Draft/ }).first();
    await row.locator('.o_list_record_selector input').check();
    await ui.rpc('action_confirm', 'confirm again', () =>
      page.locator('.o_control_panel button[name="action_confirm"], .o_list_view button[name="action_confirm"]')
        .first().click());
  });

  const [restored] = await read('aic.hrm.kpi.period.result', 'read', [[result.id]],
    { fields: ['state', 'confirmed_by', 'actual'] });
  expect(restored.state).toBe('confirmed');
  expect(restored.confirmed_by).toBeTruthy();
  expect(restored.actual).toBeCloseTo(result.actual, 6);
  const after = await read('aic.hrm.kpi.result.audit', 'search_count', [[['result_id', '=', result.id]]]);
  expect(after, 'withdrawal and re-confirmation are both recorded').toBe(before + 2);

  await test.step('the history screen shows the trail', async () => {
    await ui.openAction(auditAction);
    await expect(page.locator('.o_list_view .o_data_row').first()).toBeVisible();
    // Read-only by construction: no create button on the screen.
    await expect(page.locator('.o_list_button_add')).toHaveCount(0);
  });
});

test('a member is not offered the confirm button', async () => {
  test.skip(!existsSync(ACCOUNTS), 'the department accounts file is not present');
  const accounts = JSON.parse(readFileSync(ACCOUNTS, 'utf-8'));
  const entry = (Array.isArray(accounts) ? accounts : Object.values(accounts))
    .find((row: any) => (row.name || '').includes('Vũ Quang'));
  test.skip(!entry, 'no account for the member used in this check');

  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({ baseURL: PROD_URL, locale: 'vi-VN', viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await page.route(/\/(longpolling|bus)\/|\/websocket/, (route) => route.abort());
    await login(page, entry.login, entry.password);
    expect(await page.evaluate(() => (window as any).odoo?.info?.db)).toBe(PROD_DB);
    const ui = new OdooUi(page);
    await ui.openAction(await xmlid('aic_okr_kpi.action_aic_hrm_period_result'));
    await page.locator('.o_list_view').first().waitFor();
    await page.locator('.o_list_view thead .o_list_record_selector input').first().check();
    await expect(page.locator('button[name="action_confirm"]')).toHaveCount(0);
    await expect(page.locator('button[name="action_open_reset_wizard"]')).toHaveCount(0);
    await context.close();
  } finally {
    await browser.close();
  }
});
