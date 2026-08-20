/**
 * Re-capture the screenshots for Docs/Gioi-thieu-he-thong-AIC-HRM-Pro.html.
 *
 * Every existing shot was taken before the menu was regrouped, so each one
 * shows a menu bar the product no longer has.
 *
 * Source is AIC_HRM_Pro on :8073 - the database that document names in its
 * own access table, and the only one that carries the whole picture. The
 * DLSP demo on :8074 holds the imported plan and nothing else: no alert
 * rules, no review cycle, no calibration, no teams. Capturing from it
 * replaced ten working screenshots with empty lists before this was caught.
 *
 * Screens are addressed by xmlid, never by label: this database renders the
 * interface in Vietnamese, so "Plan" is on screen as "Kế hoạch" and a
 * name-based locator waits thirty seconds for something that is right in
 * front of it.
 */
import { chromium } from '@playwright/test';

const BASE = 'http://127.0.0.1:8073';
const DB = 'AIC_HRM_Pro';
const OUT = 'C:/AIConnect/AIC_HRM_Pro/Docs/gioi-thieu-assets';

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});
await page.route(/\/(longpolling|bus)\//, (r) => r.abort());

await page.goto(`${BASE}/web/login`);
await page.getByLabel('Email').fill('admin');
await page.getByLabel('Password').fill('admin');
await page.getByRole('button', { name: 'Log in' }).click();
await page.waitForURL(/\/(odoo|aic)\b/);

const registry = await page.evaluate(() => window.odoo?.info?.db);
if (registry !== DB) throw new Error(`connected to ${registry}, not ${DB}`);
console.log(`connected to ${registry}`);

const actionCache = new Map();

async function actionIdFor(xmlid) {
  if (actionCache.has(xmlid)) return actionCache.get(xmlid);
  const [module, name] = xmlid.split('.');
  const result = await page.evaluate(async ([module, name]) => {
    const call = async (model, method, args, kwargs = {}) => {
      const res = await fetch('/web/dataset/call_kw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', method: 'call',
          params: { model, method, args, kwargs } }),
      });
      return (await res.json()).result;
    };
    const data = await call('ir.model.data', 'search_read',
      [[['module', '=', module], ['name', '=', name]], ['res_id']], { limit: 1 });
    if (!data.length) return null;
    const menu = await call('ir.ui.menu', 'read', [[data[0].res_id], ['action']]);
    return menu[0].action;
  }, [module, name]);
  if (!result) throw new Error(`no action behind ${xmlid}`);
  const id = String(result).split(',')[1];
  actionCache.set(xmlid, id);
  return id;
}

async function open(xmlid) {
  await page.goto(`${BASE}/odoo/action-${await actionIdFor(xmlid)}`);
  await page.locator('.o_action, .modal-dialog').first().waitFor({ state: 'visible' });
  await page.waitForTimeout(2200);
}

async function shot(file, options = {}) {
  await page.screenshot({ path: `${OUT}/${file}`, ...options });
  console.log(`  ${file}`);
}

async function list(file, xmlid) {
  await open(xmlid);
  await shot(file);
}

const skipped = [];

async function form(file, xmlid) {
  try {
    await formInner(file, xmlid);
  } catch (error) {
    // Keep the previous image rather than fail the run: a form shot that
    // cannot be reached automatically is a gap to report, not a reason to
    // lose the thirty shots that did work.
    const first = String(error).split(String.fromCharCode(10))[0];
    skipped.push(`${file} (${first.slice(0, 60)})`);
    console.log(`  SKIPPED ${file}`);
  }
}

async function formInner(file, xmlid) {
  await open(xmlid);
  // Not every action opens as a flat list: Objectives arrives grouped, so
  // the rows are folded inside group headers and clicking a row finds
  // nothing until a group is opened.
  const groups = page.locator('.o_group_header');
  if (await groups.count()) {
    await groups.first().click();
    await page.waitForTimeout(1200);
  }
  const record = page.locator('.o_data_row, .o_kanban_record:not(.o_kanban_ghost)').first();
  await record.click();
  await page.locator('.o_form_view').waitFor({ state: 'visible' });
  await page.waitForTimeout(2000);
  await shot(file);
}

async function wizard(file, xmlid) {
  await open(xmlid);
  await page.locator('.modal-dialog').first().waitFor({ state: 'visible' });
  await page.waitForTimeout(1200);
  await shot(file);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
}

async function openStage(stageXmlid) {
  // The bar renders a desktop button and a mobile variant of the same
  // menu, so the xmlid alone matches three nodes; take the visible one.
  await page.locator(
    `.o_menu_sections [data-menu-xmlid='${stageXmlid}']:visible`).first().click();
  await page.waitForTimeout(900);
}

console.log('capturing:');

// The menu bar is NOT captured here. This database runs the Executive
// theme, which moves the menus into its own left sidebar, so a screenshot
// of the stock top bar would show a layout this customer never sees - and
// driving the theme's sidebar means automating a third-party component that
// changes on its own schedule. The document draws the menu as a diagram
// instead, which is accurate whatever the theme does with it.

// --- the reporting screens, none of which existed before ----------------
await list('40-executive-overview.png', 'aic_okr_kpi.menu_aic_hrm_report_overview');

await open('aic_okr_kpi.menu_aic_hrm_progress_report');
await page.waitForTimeout(1500);
await shot('41-progress-graph.png');
const switcher = (name) => page.locator(`.o_switch_view.o_${name}`);
await switcher('pivot').click();
await page.waitForTimeout(2500);
await shot('42-progress-pivot.png');
await switcher('list').click();
await page.waitForTimeout(2500);
await shot('43-progress-list.png');

await list('44-period-results.png', 'aic_okr_kpi.menu_aic_hrm_period_results');

// --- everything the document already showed, re-shot under the new menu --
await list('01-cycles.png', 'aic_hrm_base.menu_aic_hrm_cycles');
await list('02-objectives.png', 'aic_okr_kpi.menu_aic_hrm_objectives');
await form('03-objective-form.png', 'aic_okr_kpi.menu_aic_hrm_objectives');
await list('04-key-results.png', 'aic_okr_kpi.menu_aic_hrm_key_results');
await form('05-kr-form-diagnosis.png', 'aic_okr_kpi.menu_aic_hrm_key_results');
await list('06-checkins.png', 'aic_okr_kpi.menu_aic_hrm_checkins');
await list('07-kpi-library.png', 'aic_okr_kpi.menu_aic_hrm_kpi_library');
await list('08-kpi-targets.png', 'aic_okr_kpi.menu_aic_hrm_kpi_targets');
await form('09-kpi-target-form.png', 'aic_okr_kpi.menu_aic_hrm_kpi_targets');
await list('10-scorecards.png', 'aic_okr_kpi.menu_aic_hrm_assignments');
await form('11-scorecard-form.png', 'aic_okr_kpi.menu_aic_hrm_assignments');
await list('12-dept-scorecard.png', 'aic_okr_kpi.menu_aic_hrm_department_scorecard');
await list('13-cockpit.png', 'aic_okr_kpi.menu_aic_hrm_cockpit');
await list('14-alignment-tree.png', 'aic_okr_kpi.menu_aic_hrm_alignment_tree');
await list('15-review-meetings.png', 'aic_okr_kpi.menu_aic_hrm_review_meetings');
await form('16-meeting-agenda.png', 'aic_okr_kpi.menu_aic_hrm_review_meetings');
await list('17-alert-rules.png', 'aic_okr_kpi.menu_aic_hrm_alert_rules');
await list('18-target-revisions.png', 'aic_hrm_base.menu_aic_hrm_target_revisions');
await list('19-teams.png', 'aic_hrm_base.menu_aic_hrm_teams');
await list('20-metric-sources.png', 'aic_hrm_base.menu_aic_hrm_metric_sources');
await list('21-library-roles.png', 'aic_hrm_library.menu_library');
await form('22-library-role-form.png', 'aic_hrm_library.menu_library');
await list('23-knowledge-guide.png', 'aic_hrm_library.menu_knowledge_guide');
await form('24-knowledge-article.png', 'aic_hrm_library.menu_knowledge_guide');
await list('25-frameworks.png', 'aic_okr_kpi.menu_aic_hrm_frameworks');
await list('26-perspectives.png', 'aic_okr_kpi.menu_aic_hrm_perspectives');
await list('27-ksf.png', 'aic_okr_kpi.menu_aic_hrm_ksf');
await list('28-review-cycles.png', 'aic_hrm_review.menu_review_cycles');
await list('29-reviews.png', 'aic_hrm_review.menu_reviews');
await form('30-review-form-9box.png', 'aic_hrm_review.menu_reviews');
await list('31-calibration.png', 'aic_hrm_review.menu_calibration');
await form('32-calibration-form.png', 'aic_hrm_review.menu_calibration');
await list('33-idp-pip.png', 'aic_hrm_review.menu_idp');
await form('34-idp-form.png', 'aic_hrm_review.menu_idp');
await wizard('35-import-wizard.png', 'aic_okr_kpi.menu_aic_hrm_import');
await wizard('36-actuals-import-wizard.png', 'aic_okr_kpi.menu_aic_hrm_actuals_import');
await wizard('37-library-apply-wizard.png', 'aic_hrm_library.menu_library_apply');

await browser.close();
if (skipped.length) {
  console.log(`
${skipped.length} form shot(s) kept their previous image:`);
  skipped.forEach((line) => console.log('  ' + line));
}
console.log('done');
