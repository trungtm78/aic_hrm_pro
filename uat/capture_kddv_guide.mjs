/**
 * Screenshots of the customer's own data for the Sales & Services handbook.
 *
 * Read-only: it opens screens and takes pictures, nothing is saved in Odoo.
 * The database name is asserted before the first shot, because these images
 * carry real people and real revenue and must come from the live instance the
 * handbook describes - never from a demo or a test database.
 *
 * Run:  cd uat && node capture_kddv_guide.mjs
 *       (PROD_ADMIN_PASSWORD, or uat/data/prod_admin.json, must be available)
 */
import { chromium } from '@playwright/test';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';

const URL = process.env.PROD_URL ?? 'https://okr.aipower.vn';
const DB = process.env.PROD_DB ?? 'okr_aipower';
const OUT = 'C:/AIConnect/AIC_HRM_Pro/Docs/OKR/img_kddv';
const SECRET = 'data/prod_admin.json';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36';

const password = process.env.PROD_ADMIN_PASSWORD
  || (existsSync(SECRET) ? JSON.parse(readFileSync(SECRET, 'utf-8')).password : '');
if (!password) throw new Error('Set PROD_ADMIN_PASSWORD or keep uat/data/prod_admin.json');

async function rpc(model, method, args, kwargs = {}) {
  const body = {
    jsonrpc: '2.0', method: 'call', id: Date.now(),
    params: { service: 'object', method: 'execute_kw', args: [DB, uid, password, model, method, args, kwargs] },
  };
  const response = await fetch(`${URL}/jsonrpc`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'User-Agent': UA }, body: JSON.stringify(body),
  });
  const answer = await response.json();
  if (answer.error) throw new Error(answer.error.data?.message ?? JSON.stringify(answer.error));
  return answer.result;
}

async function login() {
  const response = await fetch(`${URL}/jsonrpc`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'User-Agent': UA },
    body: JSON.stringify({ jsonrpc: '2.0', method: 'call', id: 1,
      params: { service: 'common', method: 'login', args: [DB, 'admin', password] } }),
  });
  return (await response.json()).result;
}

const uid = await login();
if (!uid) throw new Error(`Cannot log in to ${DB}`);

async function xmlid(name) {
  const [module, ref] = name.split('.');
  const [row] = await rpc('ir.model.data', 'search_read', [[['module', '=', module], ['name', '=', ref]]], { fields: ['res_id'] });
  if (!row) throw new Error(`No record ${name}`);
  return row.res_id;
}

async function recordId(model, domain) {
  const [row] = await rpc(model, 'search_read', [domain], { fields: ['id'], limit: 1 });
  if (!row) throw new Error(`Nothing matches ${model} ${JSON.stringify(domain)}`);
  return row.id;
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({ baseURL: URL, locale: 'vi-VN', viewport: { width: 1500, height: 950 } });
const page = await context.newPage();
await page.route(/\/(longpolling|bus)\/|\/websocket/, (route) => route.abort());

await page.goto('/web/login', { waitUntil: 'domcontentloaded', timeout: 90_000 });
await page.locator('input[name="login"]').fill('admin');
await page.locator('input[name="password"]').fill(password);
await page.locator('form button[type="submit"]').click();
await page.waitForURL(/\/(odoo|aic)(\/|$|\?)/, { timeout: 90_000, waitUntil: 'domcontentloaded' });
await page.locator('.o_action_manager').first().waitFor({ timeout: 90_000 });

const live = await page.evaluate(() => window.odoo?.info?.db);
if (live !== DB) throw new Error(`Browser is on database "${live}", expected "${DB}" - refusing to take pictures.`);
console.log(`database verified: ${live}`);

async function open(action, suffix = '') {
  await page.goto(`/odoo/action-${action}${suffix}`, { waitUntil: 'domcontentloaded', timeout: 90_000 });
  await page.locator('.o_action_manager .o_view_controller').first().waitFor({ timeout: 90_000 });
  await page.waitForTimeout(2500);
}

/**
 * Picture of the content area only. The theme's app menu is a fixed column
 * over the page, so clipping by its width is what leaves it out; a locator
 * screenshot of the action manager still includes it.
 */
async function shot(name) {
  const gutter = await page.evaluate(() => {
    // The app menu is the fixed, narrow, full-height column on the left.
    const column = Array.from(document.querySelectorAll('.o_main_navbar, .o_navbar')).find((element) => {
      const box = element.getBoundingClientRect();
      return box.height > 400 && box.width > 100 && box.width < 400 && box.left < 20;
    });
    return column ? Math.ceil(column.getBoundingClientRect().right) : 0;
  });
  const size = page.viewportSize();
  await page.screenshot({
    path: `${OUT}/${name}.png`,
    clip: { x: gutter, y: 0, width: size.width - gutter, height: size.height },
  });
  console.log(`  ${name}.png (cắt ${gutter}px menu)`);
}

async function search(text) {
  const input = page.locator('.o_searchview_input').first();
  await input.fill(text);
  await input.press('Enter');
  await page.waitForTimeout(2500);
}

const scorecards = await xmlid('aic_okr_kpi.action_aic_hrm_kpi_assignment');
const targets = await xmlid('aic_okr_kpi.action_aic_hrm_kpi_target');
const results = await xmlid('aic_okr_kpi.action_aic_hrm_period_result');
const objectives = await xmlid('aic_okr_kpi.action_aic_hrm_objective');
const checkins = await xmlid('aic_okr_kpi.action_aic_hrm_checkin');
const invoices = await xmlid('account.action_move_out_invoice_type');
const entries = await xmlid('account.action_move_journal_line');
const report = await xmlid('aic_okr_kpi.action_aic_hrm_department_scorecard');
const sources = await xmlid('aic_hrm_base.action_aic_hrm_metric_source');
const auditTrail = await xmlid('aic_okr_kpi.action_aic_hrm_result_audit');
const reviewCycles = await xmlid('aic_hrm_review.action_review_cycle');
const reviews = await xmlid('aic_hrm_review.action_review');

console.log('capturing:');
await open(scorecards);
await shot('01-scorecard-list');

const card = await recordId('aic.hrm.kpi.assignment',
  [['employee_id.name', '=', 'Trần Ngọc Tú'], ['cycle_id.code', '=', 'KDDV-2026-07']]);
await open(scorecards, `/${card}`);
await shot('02-scorecard-form');

const target = await recordId('aic.hrm.kpi.target',
  [['kpi_id.code', '=', 'KDDV.TP-KD.B1.2'], ['cycle_id.code', '=', 'KDDV-2026-07']]);
await open(targets, `/${target}`);
await shot('03-kpi-target-form');
await page.locator('.o_notebook .nav-link').filter({ hasText: /Kết quả theo kỳ|Period Results/ }).first().click();
await page.waitForTimeout(1500);
await shot('04-kpi-target-periods');

await open(results);
await search('KDDV.');
await shot('05-period-results');

const objective = await recordId('aic.hrm.objective', [['code', '=', 'O1']]);
await open(objectives, `/${objective}`);
await shot('06-objective-form');

await open(checkins);
await shot('07-checkins');

await open(invoices);
await search('PT2026-T07');
await shot('08-invoice-list');
const invoice = await recordId('account.move', [['ref', '=like', 'PT2026-T07-II-%']]);
await open(invoices, `/${invoice}`);
await shot('09-invoice-form');

const cost = await recordId('account.move', [['ref', '=', 'CPTH2026-T07']]);
await open(entries, `/${cost}`);
await shot('10-cost-entry');

await open(sources);
await shot('11-metric-sources');

await open(report);
await shot('12-department-report');

// The controls a director asks about: who confirmed which figure, and the
// quarterly appraisal the KPI score is fixed onto.
await open(auditTrail);
await shot('13-audit-trail');

const reviewCycle = await recordId('aic.hrm.review.cycle', [['name', 'like', 'Đánh giá Quý III/2026']]);
await open(reviewCycles, `/${reviewCycle}`);
await shot('14-review-cycle');

const review = await recordId('aic.hrm.review',
  [['employee_id.name', '=', 'Trần Ngọc Tú'], ['review_cycle_id', '=', reviewCycle]]);
await open(reviews, `/${review}`);
await shot('15-review-form');

// The screens a progress report is presented from. Two of them are client
// actions: they render no list or form, so they need their own wait.
const cockpit = await xmlid('aic_okr_kpi.action_aic_hrm_cockpit');
const overview = await xmlid('aic_okr_kpi.action_aic_hrm_report_overview');
const progress = await xmlid('aic_okr_kpi.action_aic_hrm_progress_report');

async function openDesk(action, marker) {
  await page.goto(`/odoo/action-${action}`, { waitUntil: 'domcontentloaded', timeout: 90_000 });
  await page.locator(marker).first().waitFor({ timeout: 90_000 });
  await page.waitForTimeout(2500);
}

async function pickCycle(name) {
  const select = page.locator('.o_aic_cycle_select').first();
  const value = await select.locator('option', { hasText: name }).first().getAttribute('value');
  const loaded = page.waitForResponse((response) => response.url().includes('/cockpit_data') && response.ok());
  await select.selectOption(value);
  await loaded;
  await page.waitForTimeout(1500);
}

await openDesk(cockpit, '.o_aic_health_strip');
await pickCycle('Quý III/2026');
await shot('16-cockpit-quarter');
await pickCycle('Tháng 7/2026');
await shot('17-cockpit-month');

await openDesk(overview, '.o_aic_hrm');
await shot('18-executive-overview');

await open(progress);
await shot('19-progress-vs-plan');

// The rest of the screens, so a reader who never opens the system still sees
// what it is made of.
const alignment = await xmlid('aic_okr_kpi.action_aic_hrm_alignment_tree');
const cycles = await xmlid('aic_hrm_base.action_aic_hrm_cycle');
const library = await xmlid('aic_okr_kpi.action_aic_hrm_kpi');
const keyResults = await xmlid('aic_okr_kpi.action_aic_hrm_key_result');
const alerts = await xmlid('aic_okr_kpi.action_aic_hrm_alert_rule');
const meetings = await xmlid('aic_okr_kpi.action_aic_hrm_review_meeting');
const calibration = await xmlid('aic_hrm_review.action_calibration_session');
const idp = await xmlid('aic_hrm_review.action_idp');

await openDesk(alignment, '.o_aic_hrm');
await shot('20-alignment-tree');

await open(cycles);
await shot('21-cycles');

await open(library);
await shot('22-kpi-library');

await open(keyResults);
await shot('23-key-results');

const objectiveForm = await recordId('aic.hrm.objective', [['code', '=', 'O1']]);
await open(objectives, `/${objectiveForm}`);
await shot('24-objective-with-key-results');

await open(alerts);
await shot('25-alert-rules');

await open(meetings);
await shot('26-review-meetings');

await open(calibration);
await shot('27-calibration');

await open(idp);
await shot('28-development-plans');

await context.close();
await browser.close();
console.log(`done -> ${OUT}`);
