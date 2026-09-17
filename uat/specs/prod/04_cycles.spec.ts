import { test, expect, read, ALL, actionFor, loginAsAdmin, dataset } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * The planning calendar: year 2026, its third quarter, and the three months
 * the KPI sheets are assigned for. All are opened, because July and August
 * are already behind us and need their results entered.
 *
 * The year's quarter weights (Q1 20 %, Q2 20 %, Q3 25 %, Q4 35 %) have no
 * field of their own; they are recorded on the year cycle as a note, where
 * everyone who opens it sees them.
 */

const data = dataset();

type CycleSpec = { code: string; name: string; type: string; start: string; end: string; parent?: string };

const CYCLES: CycleSpec[] = [
  { code: 'KDDV-2026', name: 'Năm 2026', type: 'year', start: '2026-01-01', end: '2026-12-31' },
  { code: 'KDDV-2026-Q3', name: 'Quý III/2026', type: 'quarter', start: '2026-07-01', end: '2026-09-30', parent: 'KDDV-2026' },
  { code: 'KDDV-2026-07', name: 'Tháng 7/2026', type: 'month', start: '2026-07-01', end: '2026-07-31', parent: 'KDDV-2026-Q3' },
  { code: 'KDDV-2026-08', name: 'Tháng 8/2026', type: 'month', start: '2026-08-01', end: '2026-08-31', parent: 'KDDV-2026-Q3' },
  { code: 'KDDV-2026-09', name: 'Tháng 9/2026', type: 'month', start: '2026-09-01', end: '2026-09-30', parent: 'KDDV-2026-Q3' },
];

function toUserFormat(iso: string, format: string): string {
  const [year, month, day] = iso.split('-');
  return format.replace('%d', day).replace('%m', month).replace('%Y', year);
}

test('planning cycles 2026 > Q3 > July, August, September', async ({ page }) => {
  const ui = new OdooUi(page);
  await loginAsAdmin(page);
  const [admin] = await read('res.users', 'search_read', [[['login', '=', 'admin']]], { fields: ['lang'] });
  const [lang] = await read('res.lang', 'search_read', [[['code', '=', admin.lang]]], { fields: ['date_format'] });
  const action = await actionFor('aic.hrm.cycle');

  for (const cycle of CYCLES) {
    await test.step(`cycle ${cycle.name}`, async () => {
      let [row] = await read('aic.hrm.cycle', 'search_read', [[['code', '=', cycle.code]]], { ...ALL, fields: ['state'] });
      if (!row) {
        await ui.newRecord(action);
        await ui.fill('name', cycle.name);
        await ui.fill('code', cycle.code);
        await ui.select('cycle_type', `"${cycle.type}"`);
        await ui.fill('date_start', toUserFormat(cycle.start, lang.date_format));
        await ui.fill('date_end', toUserFormat(cycle.end, lang.date_format));
        if (cycle.parent) {
          const [parent] = await read('aic.hrm.cycle', 'search_read', [[['code', '=', cycle.parent]]], { fields: ['display_name'] });
          await ui.pickMany2one('parent_id', parent.display_name);
        }
        await ui.select('check_in_frequency', '"monthly"');
        const id = await ui.save(`cycle ${cycle.code}`);
        row = { id, state: 'draft' };
      }
      if (row.state === 'draft') {
        await ui.openRecord(action, row.id);
        await ui.clickButton('action_open', `open ${cycle.code}`);
      }
    });
  }

  await test.step('quarter weights noted on the year', async () => {
    const [year] = await read('aic.hrm.cycle', 'search_read', [[['code', '=', 'KDDV-2026']]], { fields: ['id'] });
    const weights = Object.entries(data.quarter_weights).map(([quarter, weight]) => `${quarter} = ${weight}%`).join(' | ');
    const body = `Trọng số các quý năm ${data.year}: ${weights}.`;
    const existing = await read('mail.message', 'search_count', [[
      ['model', '=', 'aic.hrm.cycle'], ['res_id', '=', year.id], ['body', 'ilike', `Trọng số các quý năm ${data.year}`]]]);
    if (!existing) {
      await ui.openRecord(action, year.id);
      await page.locator('.o-mail-Chatter-logNote').first().click();
      const composer = page.locator('.o-mail-Composer-input').first();
      await composer.fill(body);
      await ui.rpc('/mail/message/post', 'note quarter weights', () =>
        page.locator('.o-mail-Composer-send').first().click());
    }
  });

  await test.step('read back', async () => {
    for (const cycle of CYCLES) {
      const [row] = await read('aic.hrm.cycle', 'search_read', [[['code', '=', cycle.code]]], {
        fields: ['name', 'cycle_type', 'date_start', 'date_end', 'parent_id', 'state'] });
      expect(row, cycle.code).toBeTruthy();
      expect([row.name, row.cycle_type, row.date_start, row.date_end, row.state])
        .toEqual([cycle.name, cycle.type, cycle.start, cycle.end, 'open']);
      if (cycle.parent) expect(row.parent_id[1]).toContain(CYCLES.find((c) => c.code === cycle.parent)!.name);
    }
  });
});
