import { test, expect, read, loginAsAdmin } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * Remove the draft figures the old nightly pull filed on the wrong month.
 *
 * Before the pull was fixed it fetched "the current month" for every target of
 * an open cycle, so September figures landed on July and August targets. They
 * were never confirmed and never scored, but they sit in the operator's list
 * and nobody can tell what month they belong to. Only drafts dated outside
 * their own cycle are deleted, one by one through the form, and the deletion
 * is recorded in the audit trail like any other change.
 */

async function strayResults() {
  const drafts = await read('aic.hrm.kpi.period.result', 'search_read', [[['state', '=', 'draft']]],
    { fields: ['kpi_target_id', 'date_from', 'date_to'] });
  const targets = await read('aic.hrm.kpi.target', 'search_read',
    [[['id', 'in', drafts.map((row: any) => row.kpi_target_id[0])]]], { fields: ['cycle_id'] });
  const cycles = await read('aic.hrm.cycle', 'search_read',
    [[['id', 'in', targets.map((row: any) => row.cycle_id[0])]]], { fields: ['date_start', 'date_end', 'name'] });
  const window = new Map(cycles.map((cycle: any) => [cycle.id, cycle]));
  const cycleOf = new Map(targets.map((target: any) => [target.id, window.get(target.cycle_id[0])]));
  return drafts.filter((draft: any) => {
    const cycle: any = cycleOf.get(draft.kpi_target_id[0]);
    return cycle && (draft.date_from < cycle.date_start || draft.date_to > cycle.date_end);
  });
}

test('draft figures dated outside their cycle are removed', async ({ page }) => {
  test.setTimeout(60 * 60_000);
  const ui = new OdooUi(page);
  await loginAsAdmin(page);
  const action = await read('ir.model.data', 'search_read',
    [[['module', '=', 'aic_okr_kpi'], ['name', '=', 'action_aic_hrm_period_result']]], { fields: ['res_id'] });
  const resultAction = action[0].res_id;

  const stray = await strayResults();
  for (const result of stray) {
    await test.step(`${result.kpi_target_id[1]} ${result.date_from}`, async () => {
      await ui.openRecord(resultAction, result.id);
      await ui.deleteOpenRecord(`stray draft ${result.id}`);
    });
  }

  await test.step('read back', async () => {
    expect(await strayResults()).toEqual([]);
    // Nothing that was part of a score has been touched.
    const confirmed = await read('aic.hrm.kpi.period.result', 'search_count', [[['state', '=', 'confirmed']]]);
    expect(confirmed).toBe(38);
    if (stray.length) {
      const deletions = await read('aic.hrm.kpi.result.audit', 'search_count', [[['action', '=', 'delete']]]);
      expect(deletions, 'each deletion is in the audit trail').toBeGreaterThanOrEqual(stray.length);
    }
  });
});
