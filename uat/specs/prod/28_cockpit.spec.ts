import { test, expect, read, loginAsAdmin } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * The leadership desk, checked in the browser it actually runs in.
 *
 * The cockpit is an OWL screen: its figures are computed in the browser from
 * ORM calls, so nothing on the server can prove it right. The product's tour
 * cannot run here either - the customer's backend theme replaces the app
 * shell, which is exactly how a wrong ORM call once reached production and
 * left the screen showing an error dialog. This spec opens the real screen on
 * the real data and reads the four figures back.
 */

async function xmlid(name: string): Promise<number> {
  const [module, ref] = name.split('.');
  const [row] = await read('ir.model.data', 'search_read', [[['module', '=', module], ['name', '=', ref]]], { fields: ['res_id'] });
  if (!row) throw new Error(`No record ${name}`);
  return row.res_id;
}

const percent = (text: string) => Number(text.replace(/[^\d,.-]/g, '').replace(',', '.'));

test('the cockpit opens on a cycle with objectives and states what it measured', async ({ page }) => {
  test.setTimeout(15 * 60_000);
  const ui = new OdooUi(page);
  await loginAsAdmin(page);
  // Not `openAction`: the cockpit is a client action, so it never renders the
  // `.o_view_controller` that helper waits for.
  await ui.gotoWithRetry(`/odoo/action-${await xmlid('aic_okr_kpi.action_aic_hrm_cockpit')}`);

  const strip = page.locator('.o_aic_health_strip');
  await strip.waitFor({ timeout: 90_000 });
  await expect(page.locator('.o_dialog, .modal-dialog'), 'no error dialog over the desk').toHaveCount(0);

  // Which cycle did it choose, and what should the figures be?
  const selected = await page.locator('.o_aic_cycle_select').first().inputValue();
  const [cycle] = await read('aic.hrm.cycle', 'read', [[Number(selected)]], { fields: ['name', 'code'] });
  const objectives = await read('aic.hrm.objective', 'search_read', [[['cycle_id', '=', Number(selected)]]],
    { fields: ['weight', 'score', 'data_coverage', 'rag'] });
  expect(objectives.length, `the desk must not open on a cycle without objectives (${cycle.name})`).toBeGreaterThan(0);

  const weight = objectives.reduce((sum: number, row: any) => sum + row.weight, 0);
  const expectedScore = Math.round(100 * objectives.reduce(
    (sum: number, row: any) => sum + row.score * row.weight, 0) / weight);
  const expectedCoverage = Math.round(objectives.reduce(
    (sum: number, row: any) => sum + row.data_coverage * row.weight, 0) / weight);
  const krs = await read('aic.hrm.key.result', 'search_read', [[['cycle_id', '=', Number(selected)]]],
    { fields: ['code', 'metric_type', 'has_actual', 'last_checkin_date', 'progress_reported_on'] });
  const expectedReported = Math.round(100 * krs.filter((row: any) => row.has_actual).length / krs.length);

  // "Reported" is a recorded event, never read off the value: a key result
  // left at 0 under a baseline of 10 once counted as reported and went red.
  for (const kr of krs.filter((row: any) => row.has_actual && row.metric_type !== 'milestone')) {
    expect(kr.last_checkin_date || kr.progress_reported_on,
      `${kr.code} counts as reported, so somebody must have reported it`).toBeTruthy();
  }

  const values = await strip.locator('.o_aic_stat_value').allInnerTexts();
  const labels = await strip.locator('.o_aic_stat_label').allInnerTexts();
  console.log(`cockpit ${cycle.name}: ` + labels.map((l, i) => `${l}=${values[i]}`).join(' | '));
  await page.screenshot({ path: test.info().outputPath('cockpit.png'), fullPage: true });
  expect(values.length).toBeGreaterThanOrEqual(4);
  expect(percent(values[0]), 'overall score is weighted by objective weight').toBe(expectedScore);
  expect(percent(values[2]), 'data coverage').toBe(expectedCoverage);
  expect(percent(values[3]), 'key results with progress reported').toBe(expectedReported);
  expect(Number(values[4]), 'objective count').toBe(objectives.length);

  const unmeasured = objectives.filter((row: any) => !row.data_coverage).length;
  if (unmeasured) {
    await expect(strip.locator('.o_aic_stat_note'), 'the desk says how many are unmeasured')
      .toContainText(String(unmeasured));
  }

  // An objective nobody has measured is "not scored", never "off track".
  for (const objective of objectives) {
    if (!objective.data_coverage) expect(objective.rag).toBe('none');
  }
});
