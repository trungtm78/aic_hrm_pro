import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { test, expect, read, ALL, actionFor, loginAsAdmin } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * Remove the trial data (the earlier DLSP dataset) from production.
 *
 * What stays is what a module installed: every record owned by an XML id
 * (KPI and objective templates, perspectives, frameworks, import terms...).
 * Everything else in the performance tables was entered by hand for the
 * trial, and goes.
 *
 * Deletion is done in the browser, dependants first, so each step meets the
 * same guards a person would. A record the UI refuses to delete fails the
 * run with Odoo's own message - it is never removed behind the UI's back.
 */

type Step = { model: string; mode: 'all' | 'records'; domain?: any[] };

/**
 * Only records that existed when the pre-cleanup backup was taken are trial
 * data. Everything created after it is the customer's own and must survive
 * any later run of this spec - the acceptance pass re-runs the whole profile.
 */
const TRIAL_CUTOFF = '2026-09-17 09:13:07';
const TRIAL = ['create_date', '<', TRIAL_CUTOFF];

const MODULE_OWNED = async (model: string): Promise<number[]> => {
  const rows = await read('ir.model.data', 'search_read', [[['model', '=', model]]], { fields: ['res_id'] });
  return rows.map((row: any) => row.res_id);
};

async function toDelete(step: Step): Promise<number[]> {
  const kept = await MODULE_OWNED(step.model);
  const domain = [...(step.domain ?? []), TRIAL, ['id', 'not in', kept]];
  return read(step.model, 'search', [domain], ALL);
}

const PERFORMANCE_STEPS: Step[] = [
  { model: 'aic.hrm.checkin', mode: 'all' },
  { model: 'aic.hrm.kpi.period.result', mode: 'all' },
  { model: 'aic.hrm.kpi.assignment', mode: 'all' },
  { model: 'aic.hrm.target.revision', mode: 'all' },
  { model: 'aic.hrm.kpi.target', mode: 'all' },
  { model: 'aic.hrm.key.result', mode: 'all' },
  { model: 'aic.hrm.objective', mode: 'all' },
  { model: 'aic.hrm.kpi', mode: 'records' },
  { model: 'aic.hrm.alert.rule', mode: 'all' },
  { model: 'aic.hrm.review.meeting', mode: 'all' },
  { model: 'aic.hrm.calibration.session', mode: 'all' },
  { model: 'aic.hrm.idp', mode: 'all' },
  { model: 'aic.hrm.review', mode: 'all' },
  { model: 'aic.hrm.review.cycle', mode: 'all' },
  { model: 'aic.hrm.review.template', mode: 'records' },
  { model: 'aic.hrm.metric.source', mode: 'records' },
  { model: 'aic.hrm.team', mode: 'records' },
];

// Last. Review forms (questionnaires) sit outside every template, and a
// cycle can only go once nothing is filed under it any more.
const FINAL_STEPS: Step[] = [
  { model: 'aic.hrm.review.form', mode: 'records' },
  { model: 'aic.hrm.cycle', mode: 'records' },
];

// Children without a screen of their own; they must be gone once their parents are.
const CASCADED = ['aic.hrm.kpi.assignment.line', 'aic.hrm.feedback.request', 'aic.hrm.feedback.response',
  'aic.hrm.calibration.line', 'aic.hrm.idp.action', 'aic.hrm.meeting.action', 'aic.hrm.review.stage',
  'aic.hrm.review.section', 'aic.hrm.review.question', 'aic.hrm.kr.milestone'];

async function deleteStep(ui: OdooUi, step: Step, log: string[]) {
  const ids = await toDelete(step);
  if (!ids.length) {
    log.push(`${step.model}: nothing to delete`);
    return;
  }
  const action = await actionFor(step.model);
  if (step.mode === 'all') {
    // A whole-list delete is only safe while nothing but trial data exists.
    const everything = await read(step.model, 'search_count', [[]], ALL);
    if (everything === ids.length) {
      await ui.openAction(action);
      await ui.deleteAllInList(step.model);
    }
  }
  // Whatever a list could not reach (archived rows, partial sets) goes one form at a time.
  for (const id of await toDelete(step)) {
    await ui.openRecord(action, id);
    await ui.deleteOpenRecord(`${step.model} #${id}`);
  }
  const left = await toDelete(step);
  expect(left, `${step.model} still has trial records`).toEqual([]);
  log.push(`${step.model}: deleted ${ids.length}`);
}

test('trial data is removed from production through the UI', async ({ page }) => {
  const ui = new OdooUi(page);
  const log: string[] = [];
  await loginAsAdmin(page);

  const admin = (await read('res.users', 'search_read', [[['login', '=', 'admin']]], { fields: ['employee_ids', 'partner_id'] }))[0];
  const companyPartners = (await read('res.company', 'search_read', [[]], { ...ALL, fields: ['partner_id'] }))
    .map((c: any) => c.partner_id[0]);

  // Snapshot the people side before anything is deleted: once an employee
  // is gone, nothing points at the contact that was created for them.
  const trialEmployees = await read('hr.employee', 'search_read',
    [[TRIAL, ['id', 'not in', admin.employee_ids]]], { ...ALL, fields: ['name', 'work_contact_id', 'user_id'] });
  const trialUsers = await read('res.users', 'search_read',
    [[TRIAL, ['login', 'not in', ['admin', '__system__']], ['share', '=', false]]], { ...ALL, fields: ['login', 'partner_id'] });

  for (const step of PERFORMANCE_STEPS) {
    await test.step(`delete ${step.model}`, () => deleteStep(ui, step, log));
  }
  await test.step('delete trial employees', async () => {
    const action = await actionFor('hr.employee');
    for (const employee of trialEmployees) {
      if (!(await read('hr.employee', 'search', [[['id', '=', employee.id]]], ALL)).length) continue;
      await ui.openRecord(action, employee.id);
      await ui.deleteOpenRecord(`employee ${employee.name}`);
    }
    log.push(`hr.employee: deleted ${trialEmployees.length}`);
  });

  // Users go after their employees: hr_employee.user_id restricts deletion.
  await test.step('delete trial users', async () => {
    const action = await actionFor('res.users');
    for (const user of trialUsers) {
      await ui.openRecord(action, user.id);
      await ui.deleteOpenRecord(`user ${user.login}`);
    }
    log.push(`res.users: deleted ${trialUsers.length} (${trialUsers.map((u: any) => u.login).join(', ')})`);
  });

  await test.step('delete contacts left behind by trial people', async () => {
    const keep = new Set<number>([admin.partner_id[0], ...companyPartners]);
    const candidates = [
      ...trialEmployees.map((e: any) => e.work_contact_id && e.work_contact_id[0]),
      ...trialUsers.map((u: any) => u.partner_id[0]),
    ].filter((id: number) => id && !keep.has(id));
    const action = await actionFor('res.partner');
    let deleted = 0;
    for (const id of [...new Set(candidates)]) {
      if (!(await read('res.partner', 'search', [[['id', '=', id]]], ALL)).length) continue;
      await ui.openRecord(action, id);
      await ui.deleteOpenRecord(`contact #${id}`);
      deleted += 1;
    }
    log.push(`res.partner: deleted ${deleted}`);
  });

  await test.step('delete trial departments', async () => {
    const kept = await MODULE_OWNED('hr.department');
    const departments = await read('hr.department', 'search_read',
      [[TRIAL, ['id', 'not in', kept]]], { ...ALL, fields: ['name'] });
    const action = await actionFor('hr.department');
    for (const department of departments) {
      await ui.openRecord(action, department.id);
      await ui.deleteOpenRecord(`department ${department.name}`);
    }
    log.push(`hr.department: deleted ${departments.length}`);
  });

  for (const step of FINAL_STEPS) {
    await test.step(`delete ${step.model}`, () => deleteStep(ui, step, log));
  }
  for (const model of CASCADED) {
    const left = await read(model, 'search_count', [[TRIAL]], ALL);
    expect(left, `${model} should have gone with its parent`).toBe(0);
  }

  expect(await read('hr.employee', 'search_count', [[TRIAL, ['id', 'not in', admin.employee_ids]]], ALL)).toBe(0);
  expect(await read('res.users', 'search_count', [[TRIAL, ['login', 'not in', ['admin', '__system__']], ['share', '=', false]]], ALL)).toBe(0);

  const out = resolve(__dirname, '..', '..', 'test-results', 'prod');
  mkdirSync(out, { recursive: true });
  writeFileSync(resolve(out, 'purge-log.txt'), log.join('\n') + '\n', 'utf-8');
  console.log(log.join('\n'));
});
