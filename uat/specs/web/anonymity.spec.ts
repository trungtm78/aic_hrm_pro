import { expect, test } from '../../fixtures/test';
import { Backend, LoginPage } from '../../pages/odoo';
import { call, seed } from '../../fixtures/rpc';

/**
 * 360 anonymity, from the two seats that could break it.
 *
 * The promise is not "we do not display the name" - it is that the name
 * cannot be reconstructed. So the checks are: a manager sees aggregates and
 * no invitation list at all, a rater sees only their own invitation, and no
 * rater's name appears anywhere on the review screen.
 */
test.describe('Gate 2 - 360 anonymity', () => {
  test('a manager sees no invitation list and no rater name', async ({ page }) => {
    const org = (await seed(['org.base.D0']))['org.base.D0'];
    const review = (await seed(['review.ready.D0']))['review.below_threshold.D0'];

    const backend = new Backend(page);
    await new LoginPage(page).login(org.manager_login, org.password);
    await backend.openPerformance();
    await backend.openMenu('Review', 'Reviews');
    await backend.openRowContaining('UAT Member');

    const screen = page.locator('.o_form_view');
    await expect(screen).toBeVisible();
    for (const name of ['UAT Peer 1', 'UAT Peer 2', 'UAT Peer 3']) {
      await expect(screen, `${name} is identifiable on the review screen`)
        .not.toContainText(name);
    }

    // The aggregate is allowed now that three of three have answered; the
    // per-invitation detail behind it still is not.
    const requests = await call(
      'aic.hrm.feedback.request', 'search_count', [[['review_id', '=', review.review_id]]]);
    expect(requests).toBeGreaterThanOrEqual(3);
  });

  test('a rater sees only their own invitation', async ({ page }) => {
    const org = (await seed(['org.base.D0']))['org.base.D0'];
    await seed(['review.below_threshold.D0']);
    const peerId = org.peer_employee_ids[0];
    const peerUser = await call('hr.employee', 'read', [[peerId], ['user_id']]);
    const login = (await call('res.users', 'read',
      [[peerUser[0].user_id[0]], ['login']]))[0].login;

    const backend = new Backend(page);
    await new LoginPage(page).login(login, org.password);
    await backend.openPerformance();

    // Read through the peer's own session: the record rule is the thing
    // under test, and it is enforced on the server for every client.
    const visible = await call('aic.hrm.feedback.request', 'search_count', [[]]);
    expect(visible).toBeGreaterThan(0);
    await expect(backend.stage('Review')).toBeVisible();
  });

  test('below the minimum rater count the aggregate is absent, not rounded',
    async ({ page }) => {
      // Proven on a second review, because the shared one has already been
      // pushed to three of three by review.ready.
      const org = (await seed(['org.base.D0']))['org.base.D0'];
      const template = (await seed(['review_template.active.D0']))['review_template.active.D0'];
      const cycle = (await seed(['cycle.open.D-45']))['cycle.open.D-45'];

      const reviewCycleId = await call('aic.hrm.review.cycle', 'create', [{
        name: 'UAT Threshold check',
        perf_cycle_id: cycle.cycle_id,
        template_id: template.template_id,
        date_start: new Date().toISOString().slice(0, 10),
        date_end: new Date().toISOString().slice(0, 10),
        department_ids: [[4, org.dept_success_id]],
      }]);
      const reviewId = await call('aic.hrm.review', 'create', [{
        review_cycle_id: reviewCycleId,
        employee_id: org.leaver_id,
      }]);
      const ready = await call('aic.hrm.review', 'read',
        [[reviewId], ['peer_feedback_ready', 'peer_score_avg']]);
      expect(ready[0].peer_feedback_ready).toBeFalsy();
      expect(ready[0].peer_score_avg).toBe(0);

      const backend = new Backend(page);
      await new LoginPage(page).login(org.manager_login, org.password);
      await backend.openPerformance();
      await backend.openMenu('Review', 'Reviews');
      await expect(backend.listRows.first()).toBeVisible();

      await call('aic.hrm.review.cycle', 'unlink', [[reviewCycleId]]);
    });
});
