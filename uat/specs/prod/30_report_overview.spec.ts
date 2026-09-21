import { test, expect, read, loginAsAdmin } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';
import type { Page } from '@playwright/test';

/**
 * The executive overview, checked against the records behind it.
 *
 * The screen read only the rows whose cycle is exactly the one selected.
 * The customer sets objectives per quarter and assigns KPIs per month, so
 * picking the quarter showed one measurement out of thirty-nine: a single
 * month bar, "100% achieved", "nothing is behind plan". Every one of those
 * figures was arithmetically correct about the one row it could see, which
 * is what made it dangerous - a director had no way to tell.
 *
 * So the test does not read the screen against itself. It recounts the
 * measurements from the records, through the cycle tree, and holds the
 * screen to that.
 */

async function xmlid(name: string): Promise<number> {
  const [module, ref] = name.split('.');
  const [row] = await read('ir.model.data', 'search_read',
    [[['module', '=', module], ['name', '=', ref]]], { fields: ['res_id'] });
  if (!row) throw new Error(`No record ${name}`);
  return row.res_id;
}

async function openOverview(page: Page) {
  const ui = new OdooUi(page);
  await loginAsAdmin(page);
  // A client action never renders `.o_view_controller`.
  await ui.gotoWithRetry(`/odoo/action-${await xmlid('aic_okr_kpi.action_aic_hrm_report_overview')}`);
  await page.locator('.o_aic_health_strip, .o_aic_empty').first().waitFor({ timeout: 90_000 });
  await expect(page.locator('.o_dialog, .modal-dialog'), 'no error dialog').toHaveCount(0);
}

/** The periods a cycle speaks for, counted from the records, not from the UI. */
async function periodsOf(cycleId: number) {
  const inside: number[] = (await read('aic.hrm.cycle', 'search_read',
    [[['id', 'child_of', cycleId]]], { fields: ['id'] })).map((c: any) => c.id);
  const rows = await read('aic.hrm.progress.report', 'search_read',
    [[['cycle_id', 'in', inside]]], { fields: ['cycle_id', 'date'] });
  return {
    rows: rows.length,
    cycles: new Set(rows.map((r: any) => r.cycle_id[0])),
    months: new Set(rows.map((r: any) => String(r.date).slice(0, 7))),
  };
}

/** Open the quarter, which is where the customer's figures actually are. */
async function selectQuarter(page: Page) {
  const select = page.locator('.o_aic_cycle_select').first();
  const options = await select.locator('option').evaluateAll(
    (nodes) => nodes.map((node) => ({ id: Number((node as HTMLOptionElement).value), name: node.textContent!.trim() })));
  const quarter = options.find((option) => /Quý|Q[1-4]/i.test(option.name));
  expect(quarter, 'the customer runs quarters, so one must be selectable').toBeTruthy();
  const loaded = page.waitForResponse((r) => r.url().includes('/web/dataset/call_kw') && r.ok(),
    { timeout: 90_000 });
  await select.selectOption(String(quarter!.id));
  await loaded;
  await page.waitForTimeout(2_000);
  return quarter!;
}

test('a quarter counts the measurements of the months inside it', async ({ page }) => {
  test.setTimeout(15 * 60_000);
  await openOverview(page);

  const quarter = await selectQuarter(page);
  const expected = await periodsOf(quarter.id);
  console.log(`${quarter.name}: ${expected.rows} rows across ${expected.cycles.size} cycles, ${expected.months.size} calendar months`);
  await page.screenshot({ path: test.info().outputPath('overview-quarter.png'), fullPage: true });

  const measurements = Number(await page.locator('.o_aic_health_strip .o_aic_stat_value').nth(3).innerText());
  expect(measurements, `${quarter.name} must count every measurement inside it`)
    .toBe(expected.rows);

  // One bar per calendar month that holds a measurement. A quarter showing
  // a single bar was the visible half of the same fault.
  await expect(page.locator('.o_aic_month_chart .o_aic_month_col'),
    'one bar per month measured').toHaveCount(expected.months.size);

  // And the screen says which periods it read, so "39" can be checked.
  await expect(page.locator('.o_aic_scope_note'), 'the scope is stated').not.toBeEmpty();
});

test('every cycle in the selector reports what its tree holds', async ({ page }) => {
  test.setTimeout(20 * 60_000);
  await openOverview(page);
  const select = page.locator('.o_aic_cycle_select').first();
  const options = await select.locator('option').evaluateAll(
    (nodes) => nodes.map((node) => ({ id: Number((node as HTMLOptionElement).value), name: node.textContent!.trim() })));
  expect(options.length).toBeGreaterThan(1);

  for (const option of options) {
    const loaded = page.waitForResponse((r) => r.url().includes('/web/dataset/call_kw') && r.ok(),
      { timeout: 90_000 });
    await select.selectOption(String(option.id));
    await loaded;
    await page.waitForTimeout(1_500);
    await expect(page.locator('.o_dialog, .modal-dialog'), `no error dialog on ${option.name}`).toHaveCount(0);

    const expected = await periodsOf(option.id);
    if (!expected.rows) {
      await expect(page.locator('.o_aic_empty'), `${option.name}: says nothing was measured`).toBeVisible();
      console.log(`${option.name}: nothing measured`);
      continue;
    }
    const measurements = Number(await page.locator('.o_aic_health_strip .o_aic_stat_value').nth(3).innerText());
    expect(measurements, `${option.name}: measurements`).toBe(expected.rows);
    console.log(`${option.name}: ${expected.rows} measurements, ${expected.months.size} months`);
  }
});

test('the headline figures are the average over the measurements it read', async ({ page }) => {
  test.setTimeout(15 * 60_000);
  await openOverview(page);
  const selected = Number(await page.locator('.o_aic_cycle_select').first().inputValue());
  const inside: number[] = (await read('aic.hrm.cycle', 'search_read',
    [[['id', 'child_of', selected]]], { fields: ['id'] })).map((c: any) => c.id);
  const rows = await read('aic.hrm.progress.report', 'search_read',
    [[['cycle_id', 'in', inside]]], { fields: ['achieved', 'expected', 'gap'] });
  if (!rows.length) {
    test.skip();
    return;
  }
  const mean = (key: string) => rows.reduce((sum: number, r: any) => sum + r[key], 0) / rows.length;
  const values = await page.locator('.o_aic_health_strip .o_aic_stat_value').allInnerTexts();
  const percent = (text: string) => Number(text.replace(/[^\d,.-]/g, '').replace(',', '.'));
  console.log(`headline: ${values.join(' | ')} over ${rows.length} rows`);
  expect(percent(values[0]), 'achieved to date').toBe(Math.round(mean('achieved') * 100));
  expect(percent(values[1]), 'expected by now').toBe(Math.round(mean('expected') * 100));
});

test('two people behind on the same KPI are two readable rows', async ({ page }) => {
  test.setTimeout(15 * 60_000);
  await openOverview(page);
  await selectQuarter(page);
  const rows = await page.locator('.o_aic_risk_item').evaluateAll(
    (items) => items.map((item) => item.textContent!.replace(/\s+/g, ' ').trim()));
  if (!rows.length) {
    test.skip();
    return;
  }
  console.log(`laggards:\n${rows.join('\n')}`);
  // The customer gives one revenue line to several people on purpose, so
  // the same KPI legitimately appears more than once. What is not allowed
  // is two rows a reader cannot tell apart: the rail named the KPI, the
  // department and the date, and three people shared all three.
  const seen = new Set<string>();
  for (const row of rows) {
    expect(seen.has(row), `two identical rows: ${row}`).toBe(false);
    seen.add(row);
  }
});

test('the screen carries no untranslated English', async ({ page }) => {
  test.setTimeout(15 * 60_000);
  await openOverview(page);
  await selectQuarter(page);
  const text = await page.locator('.o_aic_hrm').innerText();
  // The department fallback was a bare JavaScript string, so a Vietnamese
  // screen read "Not assigned to a department" under a Vietnamese heading.
  for (const phrase of ['Not assigned', 'Measurements of', 'Gathered from']) {
    expect(text, `untranslated: ${phrase}`).not.toContain(phrase);
  }
});
