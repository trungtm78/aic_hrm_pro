import { randomInt } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { chromium } from '@playwright/test';
import { test, expect, read, ALL, actionFor, login, loginAsAdmin, dataset, PROD_URL } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * A login for every Sales & Services employee.
 *
 * Users are created from the employee form's "Create User" button, so each
 * account is linked to its employee the way HR would link it. The server has
 * no outgoing mail, so the invitation Odoo queues on creation cannot reach
 * anyone; those queued messages carry sign-up tokens and are deleted.
 *
 * Passwords are random per person and are recorded in uat/data (git-ignored)
 * the moment they are set, so an interrupted run never leaves an account
 * whose password nobody knows. Every account is then proven by logging in
 * with it.
 */

const data = dataset();
const ACCOUNTS_FILE = resolve(__dirname, '..', '..', 'data', 'kddv_accounts.json');

type Account = { code: string; name: string; login: string; password: string; role: string; verified?: boolean };

function loadAccounts(): Record<string, Account> {
  return existsSync(ACCOUNTS_FILE) ? JSON.parse(readFileSync(ACCOUNTS_FILE, 'utf-8')) : {};
}

function saveAccounts(accounts: Record<string, Account>) {
  writeFileSync(ACCOUNTS_FILE, JSON.stringify(accounts, null, 2), 'utf-8');
}

// No look-alike characters (0/O, 1/l/I): these passwords are read off a sheet and typed by hand.
const ALPHABETS = ['ABCDEFGHJKLMNPQRSTUVWXYZ', 'abcdefghijkmnpqrstuvwxyz', '23456789', '@#$%&*?'];

export function randomPassword(length = 12): string {
  const pool = ALPHABETS.join('');
  const chars = ALPHABETS.map((alphabet) => alphabet[randomInt(alphabet.length)]);
  while (chars.length < length) chars.push(pool[randomInt(pool.length)]);
  for (let i = chars.length - 1; i > 0; i -= 1) {
    const j = randomInt(i + 1);
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }
  return chars.join('');
}

const ROLE_LABEL: Record<string, RegExp> = {
  manager: /^\s*Hiệu suất: Quản lý\s*$/,
  user: /^\s*Hiệu suất: Người dùng\s*$/,
};
const ROLE_GROUP: Record<string, string> = {
  manager: 'aic_hrm_base.group_hrm_manager',
  user: 'aic_hrm_base.group_hrm_user',
};

async function groupId(xmlid: string): Promise<number> {
  const [module, name] = xmlid.split('.');
  const [row] = await read('ir.model.data', 'search_read', [[['module', '=', module], ['name', '=', name]]], { fields: ['res_id'] });
  return row.res_id;
}

test('every Sales & Services employee can log in', async ({ page }) => {
  const ui = new OdooUi(page);
  const accounts = loadAccounts();
  await loginAsAdmin(page);
  const employeeAction = await actionFor('hr.employee');
  const userAction = await actionFor('res.users');
  const managerGroup = await groupId(ROLE_GROUP.manager);
  const adminGroup = await groupId('aic_hrm_base.group_hrm_admin');

  for (const employee of data.employees) {
    await test.step(`account for ${employee.name}`, async () => {
      const [record] = await read('hr.employee', 'search_read', [[['barcode', '=', employee.code]]], { fields: ['user_id'] });
      expect(record, `employee ${employee.code} must exist (run 02_org first)`).toBeTruthy();
      let userId: number | null = record.user_id ? record.user_id[0] : null;

      if (!userId) {
        await ui.openRecord(employeeAction, record.id);
        await ui.clickButton('action_create_user', `create user for ${employee.name}`);
        const dialog = page.locator('.modal-dialog').last();
        await dialog.locator('.o_field_widget[name="login"] input').waitFor();
        await expect(dialog.locator('.o_field_widget[name="login"] input')).toHaveValue(employee.email);
        await ui.rpc('web_save', `user ${employee.email}`, () =>
          dialog.locator('.modal-footer .btn-primary, .modal-footer .o_form_button_save').first().click());
        userId = (await read('hr.employee', 'read', [[record.id]], { fields: ['user_id'] }))[0].user_id[0];
      }

      const [user] = await read('res.users', 'read', [[userId]], { fields: ['login', 'group_ids', 'lang', 'tz'] });
      expect(user.login).toBe(employee.email);
      const wantsManager = employee.performance_role === 'manager';
      const hasManager = user.group_ids.includes(managerGroup);
      const hasAdmin = user.group_ids.includes(adminGroup);
      const rightsOk = (wantsManager === hasManager) && !hasAdmin &&
        user.group_ids.includes(await groupId(ROLE_GROUP.user));
      if (!rightsOk || user.lang !== 'vi_VN' || user.tz !== 'Asia/Ho_Chi_Minh') {
        await ui.openRecord(userAction, userId);
        if (!rightsOk) {
          const privilege = page.locator('.o_wrap_field').filter({ has: page.locator('label', { hasText: /^\s*AIConnect HRM Pro\s*\??\s*$/ }) })
            .locator('.o_select_menu').first();
          await privilege.click();
          await page.locator('.o_select_menu_item, .o-dropdown--menu .dropdown-item')
            .filter({ hasText: ROLE_LABEL[employee.performance_role] }).first().click();
        }
        if (user.lang !== 'vi_VN' || user.tz !== 'Asia/Ho_Chi_Minh') {
          await ui.tab(/Tùy chọn|Preferences/);
          await ui.select('lang', '"vi_VN"').catch(() => ui.select('lang', 'vi_VN'));
          await ui.select('tz', '"Asia/Ho_Chi_Minh"').catch(() => ui.select('tz', 'Asia/Ho_Chi_Minh'));
        }
        await ui.save(`rights of ${employee.email}`);
      }

      if (!accounts[employee.code]) {
        const password = randomPassword();
        await ui.openRecord(userAction, userId);
        await ui.openCogItem(/Thay đổi Mật khẩu|Change Password/i);
        const dialog = page.locator('.modal-dialog').last();
        const cell = dialog.locator('.o_data_row .o_data_cell[name="new_passwd"]').first();
        await cell.click();
        await dialog.locator('.o_data_row .o_field_widget[name="new_passwd"] input').first().fill(password);
        await ui.rpc('change_password_button', `password of ${employee.email}`, () =>
          dialog.locator('.modal-footer button[name="change_password_button"]').click());
        accounts[employee.code] = {
          code: employee.code, name: employee.name, login: employee.email, password,
          role: wantsManager ? 'Hiệu suất: Quản lý' : 'Hiệu suất: Người dùng',
        };
        saveAccounts(accounts);
      }
    });
  }

  await test.step('queued invitations are deleted (no mail server; they carry sign-up tokens)', async () => {
    const mailAction = await actionFor('mail.mail');
    const queued = await read('mail.mail', 'search', [[['state', 'in', ['exception', 'outgoing']]]], ALL);
    for (const id of queued) {
      await ui.openRecord(mailAction, id);
      await ui.deleteOpenRecord(`queued mail #${id}`);
    }
    expect(await read('mail.mail', 'search_count', [[['state', 'in', ['exception', 'outgoing']]]], ALL)).toBe(0);
  });

  await test.step('every account logs in with its own password', async () => {
    const browser = await chromium.launch();
    try {
      for (const employee of data.employees) {
        const account = accounts[employee.code];
        const context = await browser.newContext({ baseURL: PROD_URL, locale: 'vi-VN' });
        const userPage = await context.newPage();
        await userPage.route(/\/(longpolling|bus)\/|\/websocket/, (route) => route.abort());
        await login(userPage, account.login, account.password);
        await expect(userPage, `${account.login} left the login page`).not.toHaveURL(/\/web\/login/);
        const scorecards = await actionFor('aic.hrm.kpi.assignment');
        await userPage.goto(`/odoo/action-${scorecards}`);
        await expect(userPage.locator('.o_action_manager .o_view_controller').first()).toBeVisible({ timeout: 60_000 });
        await expect(userPage.locator('.o_error_dialog')).toHaveCount(0);
        account.verified = true;
        saveAccounts(accounts);
        await context.close();
      }
    } finally {
      await browser.close();
    }
  });

  const unverified = data.employees.filter((e: any) => !accounts[e.code]?.verified).map((e: any) => e.name);
  expect(unverified, 'accounts not proven by a login').toEqual([]);
});
