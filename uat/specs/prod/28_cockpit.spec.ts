import { test, expect, read, loginAsAdmin } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';
import type { Page } from '@playwright/test';

/**
 * The leadership desk, checked in the browser it actually runs in.
 *
 * The cockpit is an OWL screen, so nothing on the server alone can prove what
 * it shows. The product's tour cannot run here either - the customer's backend
 * theme replaces the app shell, which is how a wrong ORM call once reached
 * production and left the screen showing an error dialog. This spec opens the
 * real screen on the real data, reads the figures back and recomputes them
 * from the records.
 *
 * Every cycle in the selector is opened, not only the one the desk starts on:
 * the desk once read only the objectives of exactly the selected cycle, so the
 * year and every month were empty while the months held the KPI scorecards.
 */

async function xmlid(name: string): Promise<number> {
  const [module, ref] = name.split('.');
  const [row] = await read('ir.model.data', 'search_read', [[['module', '=', module], ['name', '=', ref]]], { fields: ['res_id'] });
  if (!row) throw new Error(`No record ${name}`);
  return row.res_id;
}

const percent = (text: string) => Number(text.replace(/[^\d,.-]/g, '').replace(',', '.'));

const okrStrip = (page: Page) => page.locator('.o_aic_health_strip:not(.o_aic_kpi_strip)');
const kpiStrip = (page: Page) => page.locator('.o_aic_kpi_strip');

async function openDesk(page: Page) {
  const ui = new OdooUi(page);
  await loginAsAdmin(page);
  // Not `openAction`: the cockpit is a client action, so it never renders the
  // `.o_view_controller` that helper waits for.
  await ui.gotoWithRetry(`/odoo/action-${await xmlid('aic_okr_kpi.action_aic_hrm_cockpit')}`);
  await okrStrip(page).waitFor({ timeout: 90_000 });
  await expect(page.locator('.o_dialog, .modal-dialog'), 'no error dialog over the desk').toHaveCount(0);
}

/**
 * An independent reading of which records speak for a cycle - written from
 * the rule, not from the server code: own records, else the cycles inside,
 * else the nearest cycle above.
 */
async function resolve(model: string, cycleId: number, gatherInside: boolean) {
  const inside: number[] = (await read('aic.hrm.cycle', 'search_read',
    [[['id', 'child_of', cycleId]]], { fields: ['id'] })).map((c: any) => c.id);
  const own = await read(model, 'search_count', [[['cycle_id', '=', cycleId]]]);
  const below = await read(model, 'search_count', [[['cycle_id', 'in', inside]]]);
  if (own && !gatherInside) return { source: 'own', count: own };
  if (below) return { source: below === own ? 'own' : 'children', count: below };
  let [cycle] = await read('aic.hrm.cycle', 'read', [[cycleId]], { fields: ['parent_id'] });
  while (cycle.parent_id) {
    const parentId = cycle.parent_id[0];
    const count = await read(model, 'search_count', [[['cycle_id', '=', parentId]]]);
    if (count) return { source: 'parent', count };
    [cycle] = await read('aic.hrm.cycle', 'read', [[parentId]], { fields: ['parent_id'] });
  }
  return { source: 'none', count: 0 };
}

test('the cockpit opens on a cycle with objectives and states what it measured', async ({ page }) => {
  test.setTimeout(15 * 60_000);
  await openDesk(page);
  const strip = okrStrip(page);

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

test('every cycle in the selector shows what its tree holds', async ({ page }) => {
  test.setTimeout(20 * 60_000);
  await openDesk(page);
  const select = page.locator('.o_aic_cycle_select').first();
  const options = await select.locator('option').evaluateAll(
    (nodes) => nodes.map((node) => ({ id: (node as HTMLOptionElement).value, name: node.textContent!.trim() })));
  expect(options.length).toBeGreaterThan(1);

  for (const option of options) {
    const loaded = page.waitForResponse((r) => r.url().includes('/cockpit_data') && r.ok());
    await select.selectOption(option.id);
    await loaded;
    await expect(page.locator('.o_dialog, .modal-dialog'), `no error dialog on ${option.name}`).toHaveCount(0);

    const okr = await resolve('aic.hrm.objective', Number(option.id), false);
    const kpi = await resolve('aic.hrm.kpi.assignment', Number(option.id), true);

    // The objective count on the strip is what the tree holds.
    await expect(okrStrip(page).locator('.o_aic_stat_value').nth(4),
      `${option.name}: objectives (${okr.source})`).toHaveText(String(okr.count));
    // The desk says where its figures came from.
    await expect(page.locator('.o_aic_scope_note'), `${option.name}: scope stated`).not.toBeEmpty();

    if (kpi.count) {
      const withFigures = await kpiStrip(page).locator('.o_aic_stat_value').nth(2).innerText();
      expect(Number(withFigures.split('/')[1]), `${option.name}: scorecards (${kpi.source})`).toBe(kpi.count);
    } else {
      await expect(kpiStrip(page), `${option.name}: no KPI strip without scorecards`).toHaveCount(0);
    }
    const note = await page.locator('.o_aic_scope_note').innerText();
    console.log(`${option.name}: OKR ${okr.source} ${okr.count} | KPI ${kpi.source} ${kpi.count} | ${note}`);
    await page.screenshot({ path: test.info().outputPath(`cycle-${option.id}.png`), fullPage: true });
  }
});

test('the alignment tree opens on a cycle that has objectives', async ({ page }) => {
  test.setTimeout(15 * 60_000);
  const ui = new OdooUi(page);
  await loginAsAdmin(page);
  await ui.gotoWithRetry(`/odoo/action-${await xmlid('aic_okr_kpi.action_aic_hrm_alignment_tree')}`);
  await page.locator('.o_aic_hrm').first().waitFor({ timeout: 90_000 });
  await expect(page.locator('.o_dialog, .modal-dialog'), 'no error dialog').toHaveCount(0);

  // It used to open on the newest cycle - the month that has just started,
  // which carries scorecards but no objectives - and greeted the reader with
  // "chu kỳ chưa có mục tiêu" on a system holding four of them.
  const selected = Number(await page.locator('.o_aic_hrm select').first().inputValue());
  const objectives = await read('aic.hrm.objective', 'search_count', [[['cycle_id', '=', selected]]]);
  const anywhere = await read('aic.hrm.objective', 'search_count', [[]]);
  const [cycle] = await read('aic.hrm.cycle', 'read', [[selected]], { fields: ['name'] });
  if (anywhere) {
    expect(objectives, `the tree must not open on ${cycle.name}, which has no objectives`)
      .toBeGreaterThan(0);
    await expect(page.locator('.o_aic_hrm'), 'the tree shows its objectives')
      .not.toContainText('Chu kỳ chưa có mục tiêu');
  }
  await page.screenshot({ path: test.info().outputPath('alignment-tree.png'), fullPage: true });
});
