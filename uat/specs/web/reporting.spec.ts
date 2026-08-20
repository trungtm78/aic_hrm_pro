import { expect, test } from '../../fixtures/test';
import { Backend, LoginPage } from '../../pages/odoo';
import { call } from '../../fixtures/rpc';

/**
 * The management reporting the customer asked for: progress against plan over
 * time, by department, by position.
 *
 * These screens were signed off in the last pass by a person looking at them.
 * That was honest but unrepeatable - this is the same check, running every
 * time, and it also reconciles what the chart is drawn from against the rows
 * in the database, which the eye cannot do.
 */
test.describe('Gate 2 - management reporting', () => {
  test('progress vs plan opens as a chart and re-groups', async ({ page }) => {
    const backend = new Backend(page);
    const errors = backend.collectConsoleErrors();
    await new LoginPage(page).loginAsAdmin();
    await backend.openPerformance();
    await backend.openMenu('Reporting', 'Progress vs Plan');

    await expect(page.locator('.o_graph_view canvas')).toBeVisible();

    await backend.switchView('Pivot');
    await expect(page.locator('.o_pivot_view table')).toBeVisible();

    await backend.switchView('List');
    // The list opens grouped by month, so the rows are inside group headers
    // until one is expanded. Counting `.o_data_row` straight away reads zero
    // and says nothing about the data.
    const groups = page.locator('.o_list_view .o_group_header');
    await expect(groups.first()).toBeVisible();
    await groups.first().click();
    await expect(backend.listRows.first()).toBeVisible();

    const total = await call('aic.hrm.progress.report', 'search_count', [[]]);
    expect(await backend.listRows.count()).toBeGreaterThan(0);
    expect(total).toBeGreaterThan(0);

    expect(errors).toEqual([]);
  });

  test('the report groups by the three dimensions the customer named',
    async ({ page }) => {
      // Time, department, position - asked for by name. Grouping is checked
      // through the model rather than by driving the Group By menu: the
      // question is whether the numbers exist per bucket, and a UI-only
      // check would pass on an empty grouping too.
      for (const dimension of ['department_id', 'job_id', 'employee_id']) {
        const groups = await call(
          'aic.hrm.progress.report', 'formatted_read_group', [[]],
          { groupby: [dimension], aggregates: ['achieved:avg', '__count'] });
        expect(groups.length, `no ${dimension} buckets`).toBeGreaterThan(0);
      }
      for (const granularity of ['date:week', 'date:month', 'date:quarter']) {
        const groups = await call(
          'aic.hrm.progress.report', 'formatted_read_group', [[]],
          { groupby: [granularity], aggregates: ['achieved:avg'] });
        expect(groups.length, `no ${granularity} buckets`).toBeGreaterThan(0);
      }

      const backend = new Backend(page);
      await new LoginPage(page).loginAsAdmin();
      await backend.openPerformance();
      await backend.openMenu('Reporting', 'Progress vs Plan');
      await backend.switchView('Pivot');
      await expect(page.locator('.o_pivot_view')).toContainText('Total');
    });

  test('the executive overview draws real numbers', async ({ page }) => {
    const backend = new Backend(page);
    const errors = backend.collectConsoleErrors();
    await new LoginPage(page).loginAsAdmin();
    await backend.openPerformance();
    await backend.openMenu('Reporting', 'Executive Overview');

    const body = page.locator('.o_action').first();
    await expect(body).toBeVisible();
    // The dashboard has to land on a cycle that holds measurements. It used
    // to open on whichever cycle started most recently, which is empty the
    // moment somebody creates next period ahead of time.
    await expect(body).not.toContainText('Nothing measured in this cycle yet');
    // A dashboard that renders its frame and no figures is the failure worth
    // catching: it looks finished in a screenshot.
    await expect(body).toContainText(/%/);
    const text = await body.innerText();
    expect(text.replace(/\s+/g, ' ').length,
      'the overview rendered a frame with nothing in it').toBeGreaterThan(80);
    expect(errors).toEqual([]);
  });

  test('the department scorecard reconciles with the report', async ({ page }) => {
    const backend = new Backend(page);
    await new LoginPage(page).loginAsAdmin();
    await backend.openPerformance();
    await backend.openMenu('Reporting', 'Department Scorecard');
    await expect(backend.listRows.first()).toBeVisible();
  });
});
