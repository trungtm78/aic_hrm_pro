import { expect, test } from '../../fixtures/test';
import { Backend, LoginPage } from '../../pages/odoo';

/**
 * The menu regroup, checked the only way it can honestly be checked: by
 * walking it. A unit test can prove every action still resolves; it cannot
 * prove a person can find the thing they came for.
 */
test.describe('Gate 2 - navigation', () => {
  test('the eight stages of the operating loop are all present', async ({ page }) => {
    const backend = new Backend(page);
    const errors = backend.collectConsoleErrors();
    await new LoginPage(page).loginAsAdmin();
    await backend.openPerformance();

    for (const stage of ['Cockpit', 'Plan', 'Execute', 'Monitor', 'Review',
                         'Reporting', 'Library', 'Configuration']) {
      await expect(backend.stage(stage), `${stage} is missing from the menu`)
        .toBeVisible();
    }
    expect(errors).toEqual([]);
  });

  test('operations sit in their stage, not in Configuration', async ({ page }) => {
    const backend = new Backend(page);
    await new LoginPage(page).loginAsAdmin();
    await backend.openPerformance();

    const plan = await backend.stageItems('Plan');
    const execute = await backend.stageItems('Execute');
    const configuration = await backend.stageItems('Configuration');

    // These five used to live under Configuration. Importing this month's
    // numbers is work, not a setting; a person doing it monthly will never
    // think to open Settings.
    expect(plan.join(' | ')).toContain('Import');
    expect(execute.join(' | ')).toContain('Import Actuals');
    for (const operation of ['Import Spreadsheet', 'Import Actuals',
                             'Roll Over Cycle', 'Apply Library Pack',
                             'Capture Knowledge']) {
      expect(configuration, `${operation} is an operation, not a setting`)
        .not.toContain(operation);
    }
  });

  test('period results are reachable from the menu', async ({ page }) => {
    // They hold the monthly and quarterly numbers and had no menu at all
    // until the reporting pass - the data the customer was asking for was
    // in the database and unreachable.
    const backend = new Backend(page);
    await new LoginPage(page).loginAsAdmin();
    await backend.openPerformance();
    await backend.openMenu('Execute', 'Period Results');
    await expect(backend.breadcrumb).toContainText('Period Results');
    await expect(backend.listRows.first()).toBeVisible();
  });

  test('every stage opens every one of its screens without a console error',
    async ({ page }) => {
      const backend = new Backend(page);
      const errors = backend.collectConsoleErrors();
      await new LoginPage(page).loginAsAdmin();
      await backend.openPerformance();

      const visited: string[] = [];
      for (const stage of ['Plan', 'Execute', 'Monitor', 'Review',
                           'Reporting', 'Library']) {
        for (const item of await backend.stageItems(stage)) {
          await backend.openMenu(stage, item);
          await backend.dismissDialog();
          visited.push(`${stage} > ${item}`);
        }
      }
      console.log(`[uat] visited ${visited.length} screens:\n  ` +
                  visited.join('\n  '));
      expect(visited.length).toBeGreaterThanOrEqual(15);
      expect(errors).toEqual([]);
    });
});
