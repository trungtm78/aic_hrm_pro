import { resolve } from 'node:path';
import { existsSync } from 'node:fs';
import { test, expect, read, loginAsAdmin, dataset } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * Monthly KPI assignments, uploaded through Performance > Plan > Import
 * Spreadsheet - the screen a planner uses for a 400-line assignment sheet.
 *
 * The workbooks come from tools/build_kddv_import.py (one per month). Each
 * month is previewed, imported, and then checked person by person, line by
 * line, against the extracted plan: target, direction, verbatim wording, key
 * result, group weight and weight in group. A month already fully in place is
 * not imported again.
 */

const data = dataset();
const MONTHS = [7, 8, 9];
const IMPORT_DIR = resolve(__dirname, '..', '..', 'data', 'import');

function kpiCode(position: string, line: string) {
  return `KDDV.${position}.${line}`;
}

async function monthCycle(month: number) {
  const code = `KDDV-2026-${String(month).padStart(2, '0')}`;
  const [cycle] = await read('aic.hrm.cycle', 'search_read', [[['code', '=', code]]], { fields: ['display_name'] });
  expect(cycle, `run 04_cycles first (${code})`).toBeTruthy();
  return cycle;
}

async function monthComplete(cycleId: number, month: number): Promise<boolean> {
  const expected = data.scorecards.filter((card: any) => card.month === month).length;
  const cards = await read('aic.hrm.kpi.assignment', 'search_read', [[['cycle_id', '=', cycleId]]], { fields: ['weight_ok'] });
  return cards.length === expected && cards.every((card: any) => card.weight_ok);
}

test('monthly KPI scorecards July-September 2026', async ({ page }) => {
  const ui = new OdooUi(page);
  await loginAsAdmin(page);
  const [wizardAction] = await read('ir.actions.act_window', 'search_read',
    [[['res_model', '=', 'aic.hrm.import.wizard']]], { fields: ['id'], limit: 1 });
  const sales = data.departments.find((d: any) => d.code === data.department_code).name;

  for (const month of MONTHS) {
    await test.step(`import month ${month}`, async () => {
      const cycle = await monthCycle(month);
      if (await monthComplete(cycle.id, month)) return;
      const file = resolve(IMPORT_DIR, `KDDV_KPI_T${month}_${data.year}.xlsx`);
      expect(existsSync(file), `${file} (run tools/build_kddv_import.py)`).toBe(true);

      await page.goto(`/odoo/action-${wizardAction.id}`);
      const dialog = page.locator('.modal-dialog').last();
      const form = dialog.locator('.o_form_view');
      await form.waitFor({ timeout: 60_000 });
      await ui.pickMany2one('cycle_id', cycle.display_name, form);
      await ui.pickMany2one('department_id', sales, form);
      await form.locator('.o_field_widget[name="file"] input[type="file"]').setInputFiles(file);
      await expect(form.locator('.o_field_widget[name="file"]')).toContainText('.xlsx', { timeout: 60_000 });
      await ui.rpc('action_preview', `preview T${month}`, () =>
        dialog.locator('.modal-footer button[name="action_preview"]').click());
      await expect(form.locator('.o_field_widget[name="preview"]')).toContainText('KDDV.');
      await ui.rpc('action_import', `import T${month}`, () =>
        dialog.locator('.modal-footer button[name="action_import"]').click());
      const warnings = form.locator('.o_field_widget[name="warning_log"]');
      const text = (await warnings.count()) ? (await warnings.innerText()).trim() : '';
      expect(text, `import warnings for month ${month}`).toBe('');
    });
  }

  await test.step('scorecards read back line by line against the plan', async () => {
    const employees = await read('hr.employee', 'search_read', [[['barcode', 'like', 'KDDV']]], { fields: ['name'] });
    const employeeId = Object.fromEntries(employees.map((e: any) => [e.name, e.id]));
    const krs = await read('aic.hrm.key.result', 'search_read', [[['objective_id.cycle_id.code', '=', 'KDDV-2026-Q3']]], { fields: ['code'] });
    const krId = Object.fromEntries(krs.map((kr: any) => [kr.code, kr.id]));

    for (const month of MONTHS) {
      const cycle = await monthCycle(month);
      const cards = data.scorecards.filter((card: any) => card.month === month);
      const records = await read('aic.hrm.kpi.assignment', 'search_read', [[['cycle_id', '=', cycle.id]]], {
        fields: ['employee_id', 'weight_ok', 'weight_issue', 'total_weight', 'state'] });
      expect(records.length, `scorecards in month ${month}`).toBe(cards.length);

      for (const card of cards) {
        const label = `${card.employee} T${month}`;
        const record = records.find((r: any) => r.employee_id[0] === employeeId[card.employee]);
        expect(record, label).toBeTruthy();
        expect(record.weight_issue || '', label).toBe('');
        expect(record.state, label).toBe('draft');

        const groups = await read('aic.hrm.kpi.assignment.group', 'search_read',
          [[['assignment_id', '=', record.id]]], { fields: ['group_id', 'weight', 'total_in_group'] });
        expect(groups.map((g: any) => g.weight).sort(), label)
          .toEqual(card.groups.map((g: any) => g.weight).sort());

        const lines = await read('aic.hrm.kpi.assignment.line', 'search_read', [[['assignment_id', '=', record.id]]], {
          fields: ['kpi_target_id', 'weight_in_group', 'weight', 'group_id'] });
        const expectedLines = card.groups.flatMap((g: any) => g.lines.map((line: any) => ({ group: g, line })));
        expect(lines.length, label).toBe(expectedLines.length);
        const targets = await read('aic.hrm.kpi.target', 'read', [lines.map((l: any) => l.kpi_target_id[0])], {
          fields: ['kpi_id', 'target_value', 'direction', 'target_note', 'kr_id', 'employee_id', 'unit'] });
        const kpis = await read('aic.hrm.kpi', 'read', [targets.map((t: any) => t.kpi_id[0])], { fields: ['code'] });
        const codeOf = Object.fromEntries(kpis.map((k: any) => [k.id, k.code]));

        for (const { group, line } of expectedLines) {
          const code = kpiCode(card.position, line.code);
          const target = targets.find((t: any) => codeOf[t.kpi_id[0]] === code);
          const where = `${label} ${code}`;
          expect(target, where).toBeTruthy();
          const assignmentLine = lines.find((l: any) => l.kpi_target_id[0] === target.id);
          expect(target.employee_id[0], where).toBe(employeeId[card.employee]);
          expect([target.target_value, target.direction, target.target_note], where)
            .toEqual([line.target.target, line.target.direction, line.target.note]);
          expect(target.kr_id ? target.kr_id[0] : false, where).toBe(line.kr_codes.length ? krId[line.kr_codes[0]] : false);
          expect(assignmentLine.weight_in_group, where).toBeCloseTo(line.month_weight_in_group, 2);
          expect(assignmentLine.weight, where).toBeCloseTo(group.weight * line.month_weight_in_group / 100, 2);
        }
      }
    }
  });

  await test.step('revenue plan totals', async () => {
    const plan: Record<number, number> = { 7: 49.15, 8: 50.27, 9: 51.14 };
    const head = data.employees.find((e: any) => !e.manager).name;
    for (const month of MONTHS) {
      const cycle = await monthCycle(month);
      const [target] = await read('aic.hrm.kpi.target', 'search_read', [[
        ['cycle_id', '=', cycle.id], ['kpi_id.code', '=', kpiCode('TP-KD', 'B1.1')], ['employee_id.name', '=', head]]],
      { fields: ['target_value'] });
      expect(target.target_value, `department revenue T${month}`).toBe(plan[month]);
    }
  });
});
