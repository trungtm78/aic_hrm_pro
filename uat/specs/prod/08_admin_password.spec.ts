import { randomInt } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { chromium } from '@playwright/test';
import { test, expect, read, login, PROD_URL, PROD_DB } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';

/**
 * Retire the administrator password that published documents advertise.
 *
 * The instance now holds real people's data, and the introduction and user
 * guide handed out earlier print its admin login. The password is replaced
 * through the administrator's own profile (Security > Change password, with
 * Odoo's identity check), the way the owner would do it.
 *
 * The new password is written to uat/data/prod_admin.json (git-ignored)
 * before it is set, so an interrupted run never leaves an unknown password.
 * Later runs of the profile read it from there.
 */

const SECRET_FILE = resolve(__dirname, '..', '..', 'data', 'prod_admin.json');
const ALPHABETS = ['ABCDEFGHJKLMNPQRSTUVWXYZ', 'abcdefghijkmnpqrstuvwxyz', '23456789', '@#$%&*?'];

function strongPassword(length = 20): string {
  const pool = ALPHABETS.join('');
  const chars = ALPHABETS.map((alphabet) => alphabet[randomInt(alphabet.length)]);
  while (chars.length < length) chars.push(pool[randomInt(pool.length)]);
  for (let i = chars.length - 1; i > 0; i -= 1) {
    const j = randomInt(i + 1);
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }
  return chars.join('');
}

async function canLogin(password: string): Promise<boolean> {
  const response = await fetch(`${PROD_URL}/jsonrpc`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json',
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36' },
    body: JSON.stringify({ jsonrpc: '2.0', method: 'call', id: 1,
      params: { service: 'common', method: 'login', args: [PROD_DB, 'admin', password] } }),
  });
  return Boolean((await response.json()).result);
}

test('the advertised administrator password no longer works', async () => {
  const published = process.env.PROD_PUBLISHED_ADMIN_PASSWORD;
  expect(published, 'set PROD_PUBLISHED_ADMIN_PASSWORD to the password printed in the documents').toBeTruthy();
  const secret = existsSync(SECRET_FILE) ? JSON.parse(readFileSync(SECRET_FILE, 'utf-8')) : null;

  if (secret && await canLogin(secret.password)) {
    expect(await canLogin(published!), 'published password must be dead').toBe(false);
    return;
  }

  const current = await canLogin(published!) ? published! : null;
  expect(current, 'neither the stored nor the published password logs in').toBeTruthy();
  const next = secret?.password ?? strongPassword();
  writeFileSync(SECRET_FILE, JSON.stringify({ login: 'admin', password: next, url: PROD_URL,
    changed: new Date().toISOString() }, null, 2), 'utf-8');

  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({ baseURL: PROD_URL, locale: 'vi-VN', viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await page.route(/\/(longpolling|bus)\/|\/websocket/, (route) => route.abort());
    await login(page, 'admin', current!);
    const ui = new OdooUi(page);

    // My profile: the preferences form of the logged-in user. The action
    // needs the user's id, which the account menu passes; opened bare it
    // shows a new, nameless user and the password button cannot save it.
    const [profileAction] = await read('ir.model.data', 'search_read',
      [[['module', '=', 'base'], ['name', '=', 'action_res_users_my']]], { fields: ['res_id'] });
    const [admin] = await read('res.users', 'search', [[['login', '=', 'admin']]]);
    await ui.gotoWithRetry(`/odoo/action-${profileAction.res_id}/${admin}`);
    await expect(page.locator('.o_field_widget[name="name"] input').first()).not.toHaveValue('');
    await page.locator('.o_form_view').first().waitFor({ timeout: 90_000 });
    await ui.tab(/Bảo mật|Security/);
    await page.locator('button[name="preference_change_password"]').click();

    // Odoo 19 checks the current password first, then offers the new one.
    const identity = page.locator('.modal-dialog').filter({ has: page.locator('.o_field_widget[name="password"]') }).last();
    await identity.locator('.o_field_widget[name="password"] input').fill(current!);
    await identity.locator('.modal-footer button[name="run_check"]').click();

    const dialog = page.locator('.modal-dialog').filter({ has: page.locator('.o_field_widget[name="new_password"]') }).last();
    await dialog.waitFor({ timeout: 60_000 }).catch(async (error) => {
      await page.screenshot({ path: resolve(__dirname, '..', '..', 'test-results', 'prod', 'admin-password-dialog.png') });
      throw error;
    });
    await dialog.locator('.o_field_widget[name="new_password"] input').fill(next);
    await dialog.locator('.o_field_widget[name="confirm_password"] input').fill(next);
    await dialog.locator('.modal-footer button[name="change_password"]').click();
    await expect.poll(() => canLogin(next), { timeout: 60_000, message: 'new password logs in' }).toBe(true);
    await context.close();
  } finally {
    await browser.close();
  }
  expect(await canLogin(published!), 'published password must be dead').toBe(false);
});
