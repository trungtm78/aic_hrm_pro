import { expect, test } from '../../fixtures/test';
import { Backend, LoginPage } from '../../pages/odoo';
import { seed } from '../../fixtures/rpc';

/**
 * The weight gate, seen from where it matters: the screen.
 *
 * A scorecard whose lines do not add up to 100 cannot be submitted. The
 * import once produced dozens of those and reported success, so every one sat
 * in draft while the person who ran the import believed the plan was in
 * place. The product's job is not only to refuse - it is to say so where the
 * person is looking, with the number that is wrong.
 */
test.describe('Gate 2 - scorecard weight gate', () => {
  test('an 80% scorecard refuses to submit and says why', async ({ page }) => {
    const outputs = await seed(['assignment.underweight.D0']);
    const assignmentId = outputs['assignment.underweight.D0'].assignment_id;
    expect(outputs['assignment.underweight.D0'].total_weight).toBe(80);

    const backend = new Backend(page);
    await new LoginPage(page).loginAsAdmin();
    await backend.openPerformance();
    await backend.openMenu('Plan', 'Scorecards');
    await backend.openRowContaining('UAT Manager');

    await page.getByRole('button', { name: 'Submit' }).click();

    const message = page.locator('.o_notification, .modal-body').first();
    await expect(message).toBeVisible();
    await expect(message).toContainText('80');
    await expect(message).toContainText('100');

    // And it really did not move.
    await expect(page.getByText('Draft', { exact: true }).first()).toBeVisible();
    console.log(`[uat] scorecard ${assignmentId} refused submission at 80%`);
  });

  test('a balanced scorecard is already approved', async ({ page }) => {
    await seed(['assignment.balanced.D0']);
    const backend = new Backend(page);
    await new LoginPage(page).loginAsAdmin();
    await backend.openPerformance();
    await backend.openMenu('Plan', 'Scorecards');
    await backend.openRowContaining('UAT Member');
    await expect(page.getByText('Approved', { exact: true }).first())
      .toBeVisible();
  });
});
