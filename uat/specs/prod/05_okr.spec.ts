import { test, expect, read, ALL, actionFor, loginAsAdmin, dataset } from '../../fixtures/prod';
import { OdooUi, escapeRegExp } from '../../pages/prod';

/**
 * The department's Q3/2026 OKR as signed in the centre's decision
 * (Appendix 5): four objectives and ten key results with their weights,
 * evaluation criteria and deadlines. Milestone key results carry the
 * milestones their criterion names.
 *
 * The decision is in force, so each objective is taken through Submit,
 * Approve and Start - the state a signed plan is in - after its key results
 * are complete (key results cannot be added to an approved objective).
 */

const data = dataset();
const QUARTER = 'KDDV-2026-Q3';

function head() {
  return data.employees.find((employee: any) => !employee.manager).name as string;
}

test('Q3/2026 OKR of Sales & Services', async ({ page }) => {
  const ui = new OdooUi(page);
  await loginAsAdmin(page);
  const [admin] = await read('res.users', 'search_read', [[['login', '=', 'admin']]], { fields: ['lang'] });
  const [lang] = await read('res.lang', 'search_read', [[['code', '=', admin.lang]]], { fields: ['date_format'] });
  const [quarter] = await read('aic.hrm.cycle', 'search_read', [[['code', '=', QUARTER]]], { fields: ['display_name'] });
  expect(quarter, 'run 04_cycles first').toBeTruthy();
  const sales = data.departments.find((d: any) => d.code === data.department_code).name;
  const [department] = await read('hr.department', 'search_read', [[['name', '=', sales]]], { fields: ['id'] });
  const objectiveAction = await actionFor('aic.hrm.objective');
  const krAction = await actionFor('aic.hrm.key.result');
  const owner = head();
  const userDate = (iso: string) => {
    const [y, m, d] = iso.split('-');
    return lang.date_format.replace('%d', d).replace('%m', m).replace('%Y', y);
  };

  /**
   * Add milestone rows to the open key result form. Each new row is awaited
   * before it is typed into: clicking "add a line" while the previous row is
   * still being committed left the selection on the old row, whose name was
   * then overwritten - two milestones went missing that way.
   */
  async function addMilestones(names: string[]) {
    await ui.tab(/Mốc|Milestones/);
    const list = page.locator('.o_field_widget[name="milestone_ids"]');
    for (const milestone of names) {
      const before = await list.locator('.o_data_row').count();
      await list.locator('.o_field_x2many_list_row_add a').first().click();
      await expect(list.locator('.o_data_row')).toHaveCount(before + 1);
      const row = list.locator('.o_data_row.o_selected_row');
      const name = row.locator('.o_field_widget[name="name"] input');
      await expect(name).toHaveValue('');
      await name.fill(milestone);
      await row.locator('.o_field_widget[name="weight"] input').fill('1');
      await expect(name).toHaveValue(milestone);
    }
  }

  /** Milestones the decision names but the key result lacks are added (not governed by approval). */
  async function completeMilestones(spec: any) {
    const krAction = await actionFor('aic.hrm.key.result');
    const [objective] = await read('aic.hrm.objective', 'search_read',
      [[['cycle_id', '=', quarter.id], ['code', '=', spec.code]]], { fields: ['id'] });
    for (const kr of spec.key_results.filter((k: any) => k.metric_type === 'milestone')) {
      const [row] = await read('aic.hrm.key.result', 'search_read',
        [[['objective_id', '=', objective.id], ['code', '=', kr.code]]], { fields: ['milestone_ids'] });
      const present = (await read('aic.hrm.kr.milestone', 'read', [row.milestone_ids], { fields: ['name'] }))
        .map((m: any) => m.name);
      const missing = kr.milestones.filter((name: string) => !present.includes(name));
      if (!missing.length) continue;
      await ui.openRecord(krAction, row.id);
      await addMilestones(missing);
      await ui.save(`milestones of ${kr.code}`);
    }
  }

  /**
   * An approved objective's numbers are frozen and change only through a
   * target revision - the product's audited path. A key result whose baseline
   * or target differs from the signed decision is corrected that way, with
   * the reason on record, and approved.
   */
  async function reviseToDecision(spec: any) {
    const revisionAction = await actionFor('aic.hrm.target.revision');
    const [objective] = await read('aic.hrm.objective', 'search_read',
      [[['cycle_id', '=', quarter.id], ['code', '=', spec.code]]], { fields: ['id'] });
    for (const kr of spec.key_results.filter((k: any) => k.metric_type === 'number')) {
      const [row] = await read('aic.hrm.key.result', 'search_read',
        [[['objective_id', '=', objective.id], ['code', '=', kr.code]]], { fields: ['baseline', 'target'] });
      for (const field of ['baseline', 'target']) {
        if (row[field] === kr[field]) continue;
        await ui.newRecord(revisionAction);
        await ui.fill('res_model', 'aic.hrm.key.result');
        // "Record" follows the model typed above: a record picker, not an id box.
        await ui.pickMany2one('res_id', kr.name.slice(0, 40), undefined,
          new RegExp(`^\\s*${escapeRegExp(kr.name)}\\s*$`));
        await ui.fill('field_name', field);
        await ui.fill('new_value_float', kr[field]);
        await ui.fill('reason', `Sửa lỗi nhập liệu: ${kr.code} theo Quyết định giao OKR Quý III/2026 (Phụ lục 5) `
          + `có ${field === 'target' ? 'chỉ tiêu' : 'giá trị ban đầu'} ${String(kr[field]).replace('.', ',')} ${kr.unit}; `
          + `giá trị ${String(row[field]).replace('.', ',')} bị nhập sai định dạng số.`);
        const revisionId = await ui.save(`revision ${kr.code}.${field}`);
        await ui.openRecord(revisionAction, revisionId);
        await ui.clickButton('action_approve', `approve revision ${kr.code}.${field}`);
      }
    }
  }

  for (const spec of data.objectives) {
    await test.step(`${spec.code} ${spec.name}`, async () => {
      const domain = [['cycle_id', '=', quarter.id], ['code', '=', spec.code]];
      let [objective] = await read('aic.hrm.objective', 'search_read', [domain], { ...ALL, fields: ['state', 'name'] });
      if (!objective) {
        await ui.newRecord(objectiveAction);
        await ui.fill('name', spec.name);
        await ui.fill('code', spec.code);
        await ui.pickMany2one('cycle_id', quarter.display_name);
        await ui.select('aic.hrm.objective', 'level', 'department');
        await ui.pickMany2one('employee_id', owner);
        await ui.pickMany2one('department_id', sales);
        await ui.fill('weight', spec.weight);
        await ui.tab(/Mô tả|Description/);
        await ui.fill('description', 'Nguồn: Quyết định giao nhiệm vụ trọng tâm (OKR) Quý III/2026 - Phụ lục 5, '
          + 'Phòng Kinh doanh và Dịch vụ.');
        const id = await ui.save(`objective ${spec.code}`);
        objective = { id, state: 'draft', name: spec.name };
      }

      if (objective.state !== 'draft') {
        await reviseToDecision(spec);
        await completeMilestones(spec);
        return;
      }

      for (const kr of spec.key_results) {
        const [existing] = await read('aic.hrm.key.result', 'search_read',
          [[['objective_id', '=', objective.id], ['code', '=', kr.code]]], { fields: ['id'] });
        if (existing) continue;
        await ui.newRecord(krAction);
        await ui.fill('name', kr.name);
        await ui.fill('code', kr.code);
        await ui.pickMany2one('objective_id', spec.name.slice(0, 40), undefined,
          new RegExp(`^\\s*${escapeRegExp(spec.name)}\\s*$`));
        await ui.pickMany2one('employee_id', owner);
        await ui.select('aic.hrm.key.result', 'metric_type', kr.metric_type);
        if (kr.metric_type === 'number') {
          await ui.fill('unit', kr.unit);
          await ui.fill('baseline', kr.baseline);
          await ui.fill('target', kr.target);
        }
        await ui.fill('weight', kr.weight);
        await ui.fill('deadline', userDate(kr.deadline));
        await ui.tab(/Ghi chú|Notes/);
        await ui.fill('note', `Chỉ tiêu đánh giá: ${kr.criterion}`);
        if (kr.metric_type === 'milestone') await addMilestones(kr.milestones);
        await ui.save(`key result ${kr.code}`);
      }

      for (const [button, state] of [['action_submit', 'submitted'], ['action_approve', 'approved'], ['action_start', 'in_progress']]) {
        const [current] = await read('aic.hrm.objective', 'read', [[objective.id]], { fields: ['state'] });
        if (current.state !== 'draft' && button === 'action_submit') continue;
        if (!['draft', 'submitted'].includes(current.state) && button === 'action_approve') continue;
        if (current.state === 'in_progress') continue;
        await ui.openRecord(objectiveAction, objective.id);
        await ui.clickButton(button, `${spec.code} ${button}`);
        const [after] = await read('aic.hrm.objective', 'read', [[objective.id]], { fields: ['state'] });
        expect(after.state, `${spec.code} after ${button}`).toBe(state);
      }
    });
  }

  await test.step('read back against the signed decision', async () => {
    const objectives = await read('aic.hrm.objective', 'search_read', [[['cycle_id', '=', quarter.id]]], {
      fields: ['code', 'name', 'weight', 'state', 'department_id', 'employee_id', 'kr_ids'] });
    expect(objectives.length).toBe(data.objectives.length);
    for (const spec of data.objectives) {
      const objective = objectives.find((o: any) => o.code === spec.code);
      expect(objective, spec.code).toBeTruthy();
      expect([objective.name, objective.weight, objective.state, objective.department_id[0], objective.employee_id[1]])
        .toEqual([spec.name, spec.weight, 'in_progress', department.id, owner]);
      const krs = await read('aic.hrm.key.result', 'search_read', [[['objective_id', '=', objective.id]]], {
        fields: ['code', 'name', 'weight', 'metric_type', 'target', 'baseline', 'deadline', 'note', 'milestone_ids'] });
      expect(krs.length, spec.code).toBe(spec.key_results.length);
      for (const kr of spec.key_results) {
        const row = krs.find((r: any) => r.code === kr.code);
        expect(row, kr.code).toBeTruthy();
        expect([row.name, row.weight, row.metric_type, row.deadline]).toEqual([kr.name, kr.weight, kr.metric_type, kr.deadline]);
        expect(row.note).toContain(kr.criterion);
        if (kr.metric_type === 'number') expect([row.baseline, row.target]).toEqual([kr.baseline, kr.target]);
        else {
          const names = (await read('aic.hrm.kr.milestone', 'read', [row.milestone_ids], { fields: ['name'] }))
            .map((m: any) => m.name).sort();
          expect(names, kr.code).toEqual([...kr.milestones].sort());
        }
      }
    }
  });
});
