/**
 * Capture the screenshots for the performance-suite user guide.
 *
 * Source is AIC_STORE_DEMO on :8079 - the fictional Acme Digital dataset that
 * ships with the app, which is also exactly what a buyer sees after
 * installing. Never the customer database on :8074: this project has twice
 * had to delete screenshots taken from it by accident, so the port is written
 * once, here, and the registry name is asserted before a single shot is taken.
 */
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const BASE = 'http://127.0.0.1:8079';
const DB = 'AIC_STORE_DEMO';
const OUT = 'C:/AIConnect/AIC_HRM_Pro/Docs/guide/performance/img';

mkdirSync(OUT, { recursive: true });

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

const registry = await page.evaluate(() => odoo?.info?.db ?? window.odoo?.info?.db);
if (registry !== DB) {
  throw new Error(`Refusing to capture: connected to "${registry}", not ${DB}`);
}
console.log(`connected to ${registry}`);

async function actionIdFor(menuName) {
  const menus = await page.evaluate(async (name) => {
    const res = await fetch('/web/dataset/call_kw', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {
        model: 'ir.ui.menu', method: 'search_read',
        args: [[['name', '=', name]], ['action']], kwargs: { limit: 1 } } }),
    });
    return (await res.json()).result;
  }, menuName);
  if (!menus.length) throw new Error(`no menu named ${menuName}`);
  return String(menus[0].action).split(',')[1];
}

async function shot(file, menuName, { wait = 2500, view = null } = {}) {
  await page.goto(`${BASE}/odoo/action-${await actionIdFor(menuName)}`);
  await page.locator('.o_action').first().waitFor({ state: 'visible' });
  if (view) {
    await page.getByRole('button', { name: view }).first().click();
  }
  await page.waitForTimeout(wait);
  await page.screenshot({ path: `${OUT}/${file}`, fullPage: false });
  console.log(`  ${file}`);
}

console.log('capturing:');
await shot('01-cockpit.png', 'Cockpit');
await shot('02-cycles.png', 'Cycles');
await shot('03-objectives.png', 'Objectives');
await shot('04-key-results.png', 'Key Results');
await shot('05-checkins.png', 'Check-ins');
await shot('06-scorecards.png', 'Scorecards');
await shot('07-alignment.png', 'Alignment Tree', { wait: 3500 });
await shot('08-overview.png', 'Executive Overview', { wait: 3500 });
await shot('09-progress-graph.png', 'Progress vs Plan', { wait: 3500 });
await shot('10-progress-pivot.png', 'Progress vs Plan', { view: 'Pivot', wait: 3000 });
await shot('11-period-results.png', 'Period Results');
await shot('12-alert-rules.png', 'Alert Rules');
await shot('13-role-packs.png', 'Role Packs');

// The menu bar itself: the eight stages, opened on Plan.
await page.goto(`${BASE}/odoo/action-${await actionIdFor('Objectives')}`);
await page.waitForTimeout(1500);
await page.locator('.o_menu_sections').getByRole('button', { name: 'Plan', exact: true }).click();
await page.waitForTimeout(800);
await page.locator('.o_main_navbar').screenshot({ path: `${OUT}/00-menu.png` })
  .catch(async () => { await page.screenshot({ path: `${OUT}/00-menu.png`, clip: { x: 0, y: 0, width: 1440, height: 420 } }); });
console.log('  00-menu.png');

await browser.close();
