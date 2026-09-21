import { test, expect, read, loginAsAdmin } from '../../fixtures/prod';
import { OdooUi } from '../../pages/prod';
import type { Page } from '@playwright/test';

/**
 * The alignment tree, measured rather than looked at.
 *
 * Two faults hid behind a screen that rendered without an error. The carrier
 * line under a key result listed one entry per person per monthly scorecard,
 * so a quarterly key result carried by seven people printed twenty-one
 * entries, the same name three times over with three different scores. And
 * the carrier block asked for the full width of its row on top of a left
 * margin, so it was always wider than the row: the page grew a horizontal
 * scrollbar and cut the cycle selector off at the right edge.
 *
 * Both are invisible to the Python suite - the first is an aggregation the
 * browser does, the second is layout - so they are checked here, in the
 * browser, on the customer's own data.
 */

async function xmlid(name: string): Promise<number> {
  const [module, ref] = name.split('.');
  const [row] = await read('ir.model.data', 'search_read',
    [[['module', '=', module], ['name', '=', ref]]], { fields: ['res_id'] });
  if (!row) throw new Error(`No record ${name}`);
  return row.res_id;
}

async function openTree(page: Page) {
  const ui = new OdooUi(page);
  await loginAsAdmin(page);
  // A client action never renders `.o_view_controller`, so `openAction` would
  // wait for something that is not coming.
  await ui.gotoWithRetry(`/odoo/action-${await xmlid('aic_okr_kpi.action_aic_hrm_alignment_tree')}`);
  await page.locator('.o_aic_kr_row').first().waitFor({ timeout: 90_000 });
  await expect(page.locator('.o_dialog, .modal-dialog'), 'no error dialog').toHaveCount(0);
}

/** The carrier entries of every key result on screen, as plain text. */
function carriers(page: Page) {
  return page.locator('.o_aic_kr_row').evaluateAll((rows) => rows.map((row) => ({
    code: row.querySelector('.o_aic_kr_code')?.textContent?.trim() ?? '',
    people: Array.from(row.querySelectorAll('.o_aic_kr_person'))
      .map((node) => node.textContent!.trim()),
  })).filter((row) => row.people.length));
}

test('a person carrying a key result is named once, not once per month', async ({ page }) => {
  test.setTimeout(15 * 60_000);
  await openTree(page);

  const rows = await carriers(page);
  expect(rows.length, 'the tree must show who carries its key results').toBeGreaterThan(0);

  for (const row of rows) {
    const names = row.people.map((entry) => entry.split('·')[0].trim());
    const seen = new Map<string, number>();
    for (const name of names) seen.set(name, (seen.get(name) ?? 0) + 1);
    const repeated = [...seen.entries()].filter(([, count]) => count > 1);
    expect(repeated, `${row.code} names ${repeated.map(([n, c]) => `${n} ${c}x`).join(', ')}`)
      .toEqual([]);
  }

  // The rows behind the screen: monthly scorecards under a quarterly key
  // result, which is exactly the shape that produced the repetition.
  const selected = Number(await page.locator('.o_aic_hrm select').first().inputValue());
  const backing = await read('aic.hrm.objective.contribution', 'search_read',
    [[['objective_id.cycle_id', '=', selected]]], { fields: ['kr_id', 'employee_id'] });
  const pairs = new Set(backing.map((r: any) => `${r.kr_id?.[0]}-${r.employee_id[0]}`));
  const shown = rows.reduce((sum, row) => sum + row.people.length, 0);
  console.log(`contribution rows ${backing.length}, distinct people per key result ${pairs.size}, entries on screen ${shown}`);
  expect(shown, 'one entry per person per key result').toBeLessThanOrEqual(pairs.size);
});

test('a carrier entry states the weight in the reader language', async ({ page }) => {
  test.setTimeout(15 * 60_000);
  await openTree(page);
  const entry = await page.locator('.o_aic_kr_person').first().innerText();
  console.log(`carrier entry: ${entry}`);
  // The label came out of `_t("weight")`, which had no Vietnamese entry, so a
  // Vietnamese screen read "80 weight".
  expect(entry, 'the weight is labelled in Vietnamese').not.toMatch(/\bweight\b/);
});

for (const width of [1440, 768, 375]) {
  test(`the tree does not scroll sideways at ${width}px`, async ({ page }) => {
    test.setTimeout(15 * 60_000);
    await page.setViewportSize({ width, height: 900 });
    await openTree(page);
    // Expand nothing and collapse nothing: the state the reader lands on.
    //
    // Measured inside the screen this module owns, not across the document.
    // The customer's backend theme parks its menu drawer off the right edge
    // on every screen of the instance - at 375px it alone takes the document
    // to 399 - and that belongs to `aic_sale_pro_theme`, a separate product.
    // Asserting on the document here would report somebody else's fault as
    // this screen's, every run, forever.
    const overflow = await page.evaluate(() => {
      const doc = document.documentElement;
      const widest = Array.from(document.querySelectorAll('.o_aic_hrm, .o_aic_hrm *'))
        .map((node) => ({
          cls: (node as HTMLElement).className?.toString().slice(0, 60),
          right: Math.round(node.getBoundingClientRect().right),
        }))
        .sort((a, b) => b.right - a.right)[0];
      return { scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth, widest };
    });
    console.log(`${width}px: scrollWidth ${overflow.scrollWidth} client ${overflow.clientWidth} widest ${JSON.stringify(overflow.widest)}`);
    await page.screenshot({ path: test.info().outputPath(`tree-${width}.png`), fullPage: true });
    expect(overflow.widest.right, `nothing on the tree reaches past ${width}px`)
      .toBeLessThanOrEqual(width);
  });
}
