/**
 * JSON-RPC access to the UAT database.
 *
 * Used for SETUP and for reading back what the UI should be showing - never
 * to perform the act under test. When a spec claims "a manager approves the
 * scorecard", the approval happens by clicking, or the claim is false.
 */

const URL_BASE = process.env.UAT_URL ?? 'http://127.0.0.1:8075';
const DB = process.env.UAT_DB ?? 'AIC_HRM_UAT';
const LOGIN = process.env.UAT_ADMIN ?? 'admin';
const PASSWORD = process.env.UAT_ADMIN_PASSWORD ?? 'admin';

export interface Outputs { [key: string]: any }
export interface FixtureOutputs { [fixtureId: string]: Outputs }

let cachedUid: number | null = null;

async function jsonRpc(service: string, method: string, args: any[]): Promise<any> {
  const response = await fetch(`${URL_BASE}/jsonrpc`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      jsonrpc: '2.0',
      method: 'call',
      params: { service, method, args },
      id: Date.now(),
    }),
  });
  if (!response.ok) {
    throw new Error(`RPC transport failure: HTTP ${response.status}`);
  }
  const body: any = await response.json();
  if (body.error) {
    const message = body.error?.data?.message ?? JSON.stringify(body.error);
    throw new Error(`RPC error: ${message}`);
  }
  return body.result;
}

async function uid(): Promise<number> {
  if (cachedUid === null) {
    cachedUid = await jsonRpc('common', 'login', [DB, LOGIN, PASSWORD]);
    if (!cachedUid) {
      throw new Error(
        `Cannot log in to ${DB} at ${URL_BASE}. Start the UAT server with ` +
        '"python odoo-bin -c odoo.uat.conf" before running the suite.');
    }
  }
  return cachedUid;
}

export async function call(model: string, method: string, args: any[] = [], kwargs: object = {}): Promise<any> {
  return jsonRpc('object', 'execute_kw', [DB, await uid(), PASSWORD, model, method, args, kwargs]);
}

export async function enableUatMode(): Promise<void> {
  await call('ir.config_parameter', 'set_param', ['aic_hrm.uat_mode', '1']);
}

/** Build the named fixtures (and their dependencies) and return every output. */
export async function seed(fixtureIds: string[]): Promise<FixtureOutputs> {
  await enableUatMode();
  return call('aic.hrm.uat.fixture', 'apply_fixtures', [fixtureIds]);
}

export async function seedAll(): Promise<FixtureOutputs> {
  await enableUatMode();
  return call('aic.hrm.uat.fixture', 'apply_all', []);
}

export async function resetAll(): Promise<any> {
  await enableUatMode();
  return call('aic.hrm.uat.fixture', 'reset_all', []);
}

export async function catalog(): Promise<any[]> {
  await enableUatMode();
  return call('aic.hrm.uat.fixture', 'catalog', []);
}

export const target = { url: URL_BASE, db: DB, login: LOGIN, password: PASSWORD };
