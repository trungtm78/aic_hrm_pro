import { expect, test } from '@playwright/test';
import { call, catalog, target } from '../../fixtures/rpc';

/**
 * Gate 1 - API smoke.
 *
 * Its job is to fail fast and honestly. If the server is not up, or the
 * dataset is not there, or a persona cannot log in, then every browser
 * failure that follows would be a symptom of this and reading them as product
 * defects would waste a day. When this gate fails the verdict is NO-RUN, not
 * NO-GO: an environment that never started has told you nothing about the
 * product.
 */
test.describe('Gate 1 - API smoke', () => {
  test('the UAT server answers and it is the UAT database', async ({ request }) => {
    const response = await request.get(`${target.url}/web/login`);
    expect(response.status()).toBe(200);
    const dbs = await call('ir.model', 'search_count', [[]]);
    expect(dbs).toBeGreaterThan(0);
  });

  test('every catalogued fixture is applied', async () => {
    const rows = await catalog();
    const missing = rows.filter((row) => !row.applied).map((row) => row.id);
    expect(missing, 'global setup should have applied the whole catalogue')
      .toEqual([]);
    expect(rows.length).toBeGreaterThanOrEqual(20);
  });

  test('all three personas can authenticate', async ({ request }) => {
    const org = (await call('aic.hrm.uat.fixture', 'apply_fixtures', [['org.base.D0']]))['org.base.D0'];
    for (const login of [org.admin_login, org.manager_login, org.member_login]) {
      const response = await request.post(`${target.url}/web/session/authenticate`, {
        data: {
          jsonrpc: '2.0',
          params: { db: target.db, login, password: org.password },
        },
      });
      const body = await response.json();
      expect(body.error, `${login} could not authenticate`).toBeUndefined();
      expect(body.result?.uid, `${login} got no uid`).toBeTruthy();
    }
  });

  test('every core model reads', async () => {
    const models = [
      'aic.hrm.cycle', 'aic.hrm.objective', 'aic.hrm.key.result',
      'aic.hrm.checkin', 'aic.hrm.kpi', 'aic.hrm.kpi.target',
      'aic.hrm.kpi.period.result', 'aic.hrm.kpi.assignment',
      'aic.hrm.review', 'aic.hrm.feedback.request',
      'aic.hrm.calibration.line', 'aic.hrm.library.role',
      'aic.hrm.progress.report', 'aic.hrm.department.scorecard',
    ];
    for (const model of models) {
      const count = await call(model, 'search_count', [[]]);
      expect(count, `${model} returned nothing at all`).toBeGreaterThan(0);
    }
  });

  test('the progress report agrees with its own sources', async () => {
    const rows = await call('aic.hrm.progress.report', 'search_count', [[]]);
    const checkins = await call('aic.hrm.checkin', 'search_count', [[]]);
    const confirmed = await call('aic.hrm.kpi.period.result', 'search_count', [
      [['state', '=', 'confirmed']],
    ]);
    expect(rows, 'one row per measurement, and nothing invented')
      .toBe(checkins + confirmed);
  });
});
