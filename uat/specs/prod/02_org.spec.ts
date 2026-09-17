import { test, expect, read, ALL, actionFor, loginAsAdmin, dataset } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * The customer's organisation, entered the way an HR officer would enter it.
 *
 * Source: the staff workbook (employees and departments) and section V of the
 * KPI workbook (which position each person holds). The six departments are
 * all created so the tree is complete; only Sales & Services is staffed in
 * detail, plus the five other department heads so every department has its
 * manager.
 *
 * Each record is looked up before it is created, so a second run finds
 * everything in place and changes nothing.
 */

const data = dataset();

async function findOne(model: string, domain: any[]): Promise<number | null> {
  const ids = await read(model, 'search', [domain], { ...ALL, limit: 2 });
  if (ids.length > 1) throw new Error(`${model} ${JSON.stringify(domain)} matches more than one record`);
  return ids[0] ?? null;
}

test('organisation: company, departments, positions and people', async ({ page }) => {
  const ui = new OdooUi(page);
  await loginAsAdmin(page);

  await test.step('company name', async () => {
    const company = (await read('res.company', 'search_read', [[]], { fields: ['name'], order: 'id', limit: 1 }))[0];
    if (company.name !== data.company) {
      await ui.openRecord(await actionFor('res.company'), company.id);
      await ui.fill('name', data.company);
      await ui.save('company');
    }
    expect((await read('res.company', 'read', [[company.id]], { fields: ['name'] }))[0].name).toBe(data.company);
  });

  const departmentId: Record<string, number> = {};
  await test.step('departments', async () => {
    const action = await actionFor('hr.department');
    for (const department of data.departments) {
      let id = await findOne('hr.department', [['name', '=', department.name]]);
      if (!id) {
        await ui.newRecord(action);
        await ui.fill('name', department.name);
        id = await ui.save(`department ${department.name}`);
      }
      departmentId[department.code] = id;
    }
  });
  const sales = data.departments.find((d: any) => d.code === data.department_code);

  const jobId: Record<string, number> = {};
  await test.step('positions of Sales & Services', async () => {
    const action = await actionFor('hr.job');
    for (const position of data.positions) {
      let id = await findOne('hr.job', [['name', '=', position.title], ['department_id', '=', departmentId[data.department_code]]]);
      if (!id) {
        await ui.newRecord(action);
        await ui.fill('name', position.title);
        await ui.pickMany2one('department_id', sales.name);
        id = await ui.save(`position ${position.code}`);
      }
      jobId[position.code] = id;
    }
  });

  const employeeAction = await actionFor('hr.employee');

  async function ensureEmployee(person: {
    name: string; code?: string; email?: string; department: string; job?: string; title?: string;
    manager?: string | null; note?: string | null;
  }): Promise<number> {
    const existing = person.code
      ? await findOne('hr.employee', [['barcode', '=', person.code]])
      : await findOne('hr.employee', [['name', '=', person.name]]);
    if (existing) return existing;
    await ui.newRecord(employeeAction);
    await ui.fill('name', person.name);
    if (person.email) await ui.fill('work_email', person.email);
    await ui.pickMany2one('department_id', person.department);
    if (person.job) await ui.pickMany2one('job_id', person.job);
    // Picking a position copies its name into the job title; the staff
    // list's own title is set afterwards so it is the one that stays.
    if (person.title) await ui.fill('job_title', person.title);
    if (person.manager) await ui.pickMany2one('parent_id', person.manager);
    if (person.note) await ui.fill('additional_note', person.note);
    if (person.code) {
      await ui.tab(/Cài đặt|Settings/);
      await ui.fill('barcode', person.code);
    }
    return ui.save(`employee ${person.name}`);
  }

  async function setDepartmentManager(code: string, managerName: string) {
    const department = (await read('hr.department', 'read', [[departmentId[code]]], { fields: ['manager_id', 'name'] }))[0];
    if (department.manager_id && department.manager_id[1] === managerName) return;
    await ui.openRecord(await actionFor('hr.department'), departmentId[code]);
    await ui.pickMany2one('manager_id', managerName);
    await ui.save(`manager of ${department.name}`);
  }

  const positionTitle = Object.fromEntries(data.positions.map((p: any) => [p.code, p.title]));
  const head = data.employees.find((e: any) => !e.manager);

  const salesPerson = (employee: any) => ({
    name: employee.name,
    code: employee.code,
    email: employee.email,
    department: sales.name,
    job: positionTitle[employee.position],
    title: employee.job_title,
    manager: employee.manager,
    note: employee.note,
  });

  await test.step('head of Sales & Services', async () => {
    await ensureEmployee(salesPerson(head));
    await setDepartmentManager(data.department_code, head.name);
  });

  await test.step('Sales & Services staff', async () => {
    for (const employee of data.employees) {
      if (employee === head) continue;
      await ensureEmployee(salesPerson(employee));
    }
  });

  await test.step('heads of the other departments', async () => {
    for (const department of data.departments) {
      if (department.code === data.department_code || !department.manager) continue;
      await ensureEmployee({ name: department.manager, department: department.name });
      await setDepartmentManager(department.code, department.manager);
    }
  });

  await test.step('read back against the staff workbook', async () => {
    for (const employee of data.employees) {
      const [row] = await read('hr.employee', 'search_read', [[['barcode', '=', employee.code]]], {
        fields: ['name', 'work_email', 'department_id', 'job_id', 'job_title', 'parent_id', 'barcode'],
      });
      expect(row, employee.code).toBeTruthy();
      expect(row.name).toBe(employee.name);
      expect(row.work_email).toBe(employee.email);
      expect(row.department_id[0]).toBe(departmentId[data.department_code]);
      expect(row.job_id[0]).toBe(jobId[employee.position]);
      expect(row.job_title).toBe(employee.job_title);
      expect(row.parent_id ? row.parent_id[1] : null).toBe(employee.manager);
    }
    for (const department of data.departments) {
      const [row] = await read('hr.department', 'read', [[departmentId[department.code]]], { fields: ['manager_id'] });
      expect(row.manager_id ? row.manager_id[1] : null, department.code).toBe(department.manager);
    }
  });
});
