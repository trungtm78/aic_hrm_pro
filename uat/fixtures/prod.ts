import { test as base, expect, Page } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * Production access for the data-entry specs.
 *
 * RPC here is READ-ONLY by construction: `read()` refuses any method that is
 * not a query. The data itself is entered through the browser, because that
 * is what the customer asked for and because it exercises the same
 * constraints, onchanges and access rules a person would hit. RPC is used to
 * find what already exists (so a rerun does not duplicate) and to check the
 * result afterwards.
 *
 * Credentials come from the environment, or from git-ignored files under
 * uat/data that the account specs write; nothing with a password is committed.
 */
export const PROD_URL = process.env.PROD_URL ?? 'https://okr.aipower.vn';
export const PROD_DB = process.env.PROD_DB ?? 'okr_aipower';
const ADMIN = process.env.PROD_ADMIN ?? 'admin';

// Cloudflare in front of the site rejects requests without a browser-like
// user agent with HTTP 403, before they ever reach Odoo.
const USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
  + '(KHTML, like Gecko) Chrome/130.0 Safari/537.36';

const QUERY_METHODS = new Set(['search_read', 'search_count', 'search', 'read', 'fields_get', 'read_group']);

const ADMIN_SECRET = resolve(__dirname, '..', 'data', 'prod_admin.json');

/** From PROD_ADMIN_PASSWORD, else from the git-ignored file 08_admin_password writes. */
export function adminPassword(): string {
  const password = process.env.PROD_ADMIN_PASSWORD
    || (existsSync(ADMIN_SECRET) ? JSON.parse(readFileSync(ADMIN_SECRET, 'utf-8')).password : '');
  if (!password) {
    throw new Error('Set PROD_ADMIN_PASSWORD (or keep uat/data/prod_admin.json) to run the production profile.');
  }
  return password;
}

async function jsonRpc(service: string, method: string, args: any[]): Promise<any> {
  // Transport failures (the network between this machine and the CDN drops
  // for seconds at a time) are retried with backoff. Answers from Odoo,
  // including errors, are never retried: those are results, not hiccups.
  let response: Response | undefined;
  for (let attempt = 1; !response; attempt += 1) {
    try {
      response = await fetch(`${PROD_URL}/jsonrpc`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'User-Agent': USER_AGENT },
        body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: { service, method, args }, id: Date.now() }),
        signal: AbortSignal.timeout(60_000),
      });
    } catch (error) {
      if (attempt >= 6) throw error;
      await new Promise((done) => setTimeout(done, 5_000 * attempt));
    }
  }
  if (!response.ok) {
    throw new Error(`RPC transport failure: HTTP ${response.status}`);
  }
  const body: any = await response.json();
  if (body.error) {
    throw new Error(`RPC error: ${body.error?.data?.message ?? JSON.stringify(body.error)}`);
  }
  return body.result;
}

let cachedUid: number | null = null;

export async function read(model: string, method: string, args: any[] = [], kwargs: object = {}): Promise<any> {
  if (!QUERY_METHODS.has(method)) {
    throw new Error(`read() only runs queries; "${method}" would change data - do it through the UI.`);
  }
  if (cachedUid === null) {
    cachedUid = await jsonRpc('common', 'login', [PROD_DB, ADMIN, adminPassword()]);
    if (!cachedUid) throw new Error(`Cannot log in to ${PROD_DB} at ${PROD_URL} as ${ADMIN}.`);
  }
  return jsonRpc('object', 'execute_kw', [PROD_DB, cachedUid, adminPassword(), model, method, args, kwargs]);
}

/** Every record, archived ones included - leftovers hide in the archive. */
export const ALL = { context: { active_test: false } };

/** First window action on a model, so a spec can open its screens by URL. */
export async function actionFor(model: string): Promise<number> {
  const actions = await read('ir.actions.act_window', 'search_read',
    [[['res_model', '=', model], ['view_mode', 'ilike', 'list']]], { fields: ['id'], limit: 1, order: 'id' });
  if (!actions.length) throw new Error(`No list action for ${model}`);
  return actions[0].id;
}

export async function login(page: Page, loginName: string, password: string) {
  // A fresh browser context downloads the whole asset bundle; retry a stalled
  // load instead of reporting a network hiccup as a failed login.
  for (let attempt = 1; ; attempt += 1) {
    try {
      await page.goto('/web/login', { waitUntil: 'domcontentloaded', timeout: 90_000 });
      await page.locator('input[name="login"]').fill(loginName);
      await page.locator('input[name="password"]').fill(password);
      await page.locator('form button[type="submit"]').click();
      await page.waitForURL(/\/(odoo|aic)(\/|$|\?)/, { timeout: 90_000, waitUntil: 'domcontentloaded' });
      await page.locator('.o_action_manager').first().waitFor({ timeout: 90_000 });
      break;
    } catch (error) {
      if (attempt >= 3 || page.url().includes('/web/login') && await page.locator('.alert-danger').count()) {
        throw error;
      }
    }
  }
  const db = await page.evaluate(() => (window as any).odoo?.info?.db);
  if (db !== PROD_DB) {
    throw new Error(`Logged in to database "${db}", expected "${PROD_DB}". Stopping before touching anything.`);
  }
}

export async function loginAsAdmin(page: Page) {
  await login(page, ADMIN, adminPassword());
}

export interface Dataset { [key: string]: any }

export function dataset(): Dataset {
  return JSON.parse(readFileSync(resolve(__dirname, '..', 'data', 'kddv_q3_2026.json'), 'utf-8'));
}

/**
 * Same long-polling block as the UAT fixture: held bus connections are not
 * what is being entered, and a dropped one raises a modal over the form.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route(/\/(longpolling|bus)\/|\/websocket/, (route) => route.abort());
    await use(page);
  },
});

export { expect };
