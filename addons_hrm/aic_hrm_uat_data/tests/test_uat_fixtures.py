# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The fixtures are code, so they get tested like code.

Two things are being proved here. First that the engine holds its contract:
every catalogued fixture builds, promises no output it fails to return, is
idempotent, and cleans up to the record. Second - and this is the part worth
the file - that each fixture actually carries the *state it is named after*. A
fixture called `assignment.underweight.D0` that could be submitted would be
worse than no fixture at all: it would make a UAT run green while the gate it
exists to exercise had quietly stopped working.
"""
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'aic_hrm_uat_data')
class TestUatFixtures(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'aic_hrm.uat_mode', '1')
        cls.Fixture = cls.env['aic.hrm.uat.fixture']
        # Start from no fixtures applied, whatever the server was left in.
        # These cases run against a database a browser run has usually
        # already seeded, and two of them read false green on it: applying
        # an applied fixture creates nothing, so "cleanup restores the
        # counts" had nothing to restore, and the below-threshold review was
        # already at three of three. The reset rolls back with the test.
        cls.Fixture.reset_all()

    # ------------------------------------------------------------------
    # Engine contract
    # ------------------------------------------------------------------
    def test_every_fixture_applies(self):
        catalog = self.Fixture._catalog()
        self.assertTrue(catalog, "the catalog must not be empty")
        results = self.Fixture.apply_all()
        self.assertEqual(
            set(results), set(catalog),
            "apply_all must return outputs for every catalogued fixture")
        for fid, spec in catalog.items():
            for name in spec.get('outputs', ()):
                self.assertIn(name, results[fid],
                              "%s did not return its promised output %s"
                              % (fid, name))

    def test_catalog_ids_match_their_metadata(self):
        """The id is the documentation: `<entity>.<state>.<lifecycle>[.<shape>]`.

        An id that says one thing while the spec says another is how a
        dataset stops being self-describing.
        """
        for fid, spec in self.Fixture._catalog().items():
            parts = fid.split('.')
            self.assertGreaterEqual(len(parts), 3, "malformed id %s" % fid)
            self.assertEqual(parts[0], spec['entity'], fid)
            self.assertEqual(parts[1], spec['state'], fid)
            self.assertEqual(parts[2], spec['lifecycle'], fid)
            self.assertTrue(spec.get('doc'), "%s has no doc" % fid)
            self.assertTrue(spec.get('setup'), "%s has no setup" % fid)

    def test_apply_is_idempotent(self):
        first = self.Fixture.apply_fixtures(['objective.approved.D-30.normal'])
        count = self.env['aic.hrm.objective'].search_count([])
        second = self.Fixture.apply_fixtures(
            ['objective.approved.D-30.normal'])
        self.assertEqual(first, second, "re-applying must return the same ids")
        self.assertEqual(
            count, self.env['aic.hrm.objective'].search_count([]),
            "re-applying must not create a second copy")

    def test_dependencies_are_applied_first(self):
        results = self.Fixture.apply_fixtures(['kr.checkins.D0.normal'])
        self.assertIn('org.base.D0', results,
                      "the org chart underneath must be built and reported")
        self.assertIn('cycle.open.D-45', results)

    def test_cleanup_returns_the_database_to_where_it_started(self):
        models = ['aic.hrm.objective', 'aic.hrm.key.result',
                  'aic.hrm.checkin', 'aic.hrm.kpi.target',
                  'aic.hrm.kpi.period.result', 'aic.hrm.kpi.assignment',
                  'aic.hrm.cycle', 'hr.employee', 'res.users',
                  'aic.hrm.review', 'aic.hrm.calibration.line']
        before = {name: self.env[name].with_context(
            active_test=False).search_count([]) for name in models}
        self.Fixture.apply_all()
        grew = {name for name in models
                if self.env[name].with_context(active_test=False)
                .search_count([]) > before[name]}
        self.assertTrue(grew, "the fixtures must have created something")
        self.Fixture.reset_all()
        after = {name: self.env[name].with_context(
            active_test=False).search_count([]) for name in models}
        self.assertEqual(before, after,
                         "cleanup left records behind (or removed too many)")
        self.assertFalse(self.Fixture.search([]),
                         "no fixture instance may survive a reset")

    def test_cleanup_cascades_to_dependents(self):
        self.Fixture.apply_fixtures(['kr.checkins.D0.normal'])
        removed = self.Fixture.cleanup_fixtures(['org.base.D0'])
        self.assertIn('kr.checkins.D0.normal', removed['fixtures'],
                      "removing the org chart must remove what stands on it")
        self.assertIn('objective.approved.D-30.normal', removed['fixtures'],
                      "and the objective in between it")
        surviving = set(self.Fixture.search([]).mapped('fixture_id'))
        self.assertNotIn('kr.checkins.D0.normal', surviving)
        # The cycle does not depend on the org chart, so it stays. Cascade
        # follows declared dependencies, not everything applied that day.
        self.assertIn('cycle.open.D-45', surviving)

    def test_unknown_fixture_is_refused(self):
        with self.assertRaises(UserError):
            self.Fixture.apply_fixtures(['no.such.fixture'])

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    def test_uat_mode_off_blocks_everything(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'aic_hrm.uat_mode', '0')
        with self.assertRaises(UserError):
            self.Fixture.apply_fixtures(['org.base.D0'])
        self.env['ir.config_parameter'].sudo().set_param(
            'aic_hrm.uat_mode', '1')

    def test_non_admin_cannot_seed(self):
        user = self.env['res.users'].create({
            'name': 'Plain User', 'login': 'uat_plain_user',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('aic_hrm_base.group_hrm_manager').id])],
        })
        with self.assertRaises(AccessError):
            self.Fixture.with_user(user).apply_fixtures(['org.base.D0'])

    # ------------------------------------------------------------------
    # Each fixture carries the state its name claims
    # ------------------------------------------------------------------
    def test_locked_cycle_refuses_edits(self):
        out = self.Fixture.apply_fixtures(['cycle.locked.D0'])[
            'cycle.locked.D0']
        kr = self.env['aic.hrm.key.result'].browse(out['kr_id'])
        with self.assertRaises(UserError):
            kr.write({'current': 99.0})

    def test_single_day_cycle_does_not_divide_by_zero(self):
        out = self.Fixture.apply_fixtures(['cycle.open.oneday'])[
            'cycle.open.oneday']
        cycle = self.env['aic.hrm.cycle'].browse(out['cycle_id'])
        self.assertEqual(cycle.date_start, cycle.date_end)
        # The report reads the cycle calendar in SQL; a zero-length cycle is
        # the divisor that used to be missing a NULLIF.
        self.env['aic.hrm.progress.report'].search(
            [('cycle_id', '=', cycle.id)])

    def test_empty_objective_has_no_key_results(self):
        out = self.Fixture.apply_fixtures(['objective.draft.D-30.empty'])[
            'objective.draft.D-30.empty']
        objective = self.env['aic.hrm.objective'].browse(out['objective_id'])
        self.assertFalse(objective.kr_ids)
        self.assertEqual(objective.state, 'draft')

    def test_full_objective_spans_all_five_levels(self):
        out = self.Fixture.apply_fixtures(['objective.done.D-30.full'])[
            'objective.done.D-30.full']
        levels = {
            self.env['aic.hrm.objective'].browse(out[key]).level
            for key in ('company_objective_id', 'branch_objective_id',
                        'department_objective_id', 'team_objective_id',
                        'individual_objective_id')
        }
        self.assertEqual(
            levels, {'company', 'branch', 'department', 'team', 'individual'})

    def test_stale_key_result_reads_as_stale(self):
        out = self.Fixture.apply_fixtures(['kr.stale.D-30.with_holes'])[
            'kr.stale.D-30.with_holes']
        kr = self.env['aic.hrm.key.result'].browse(out['kr_id'])
        self.assertTrue(kr.is_stale,
                        "a key result last touched 30 days ago is stale")

    def test_checkin_series_keeps_its_order_and_dates(self):
        out = self.Fixture.apply_fixtures(['kr.checkins.D0.normal'])[
            'kr.checkins.D0.normal']
        checkins = self.env['aic.hrm.checkin'].browse(
            out['checkin_ids']).sorted('date')
        self.assertEqual(len(checkins), 3)
        self.assertEqual([c.confidence for c in checkins], [8, 6, 4],
                         "confidence falls while the number rises - that "
                         "divergence is the diagnosis signal")

    def test_draft_period_results_stay_out_of_the_report(self):
        out = self.Fixture.apply_fixtures(
            ['kpi_target.draft_results.D-30.normal'])[
            'kpi_target.draft_results.D-30.normal']
        rows = self.env['aic.hrm.progress.report'].search(
            [('kpi_target_id', '=', out['target_id'])])
        self.assertFalse(
            rows, "a number nobody confirmed must not reach a report")

    def test_lower_is_better_target_stays_positive(self):
        out = self.Fixture.apply_fixtures(
            ['kpi_target.lower_better.D-60.normal'])[
            'kpi_target.lower_better.D-60.normal']
        target = self.env['aic.hrm.kpi.target'].browse(out['target_id'])
        self.assertEqual(target.direction, 'lower')
        self.assertGreater(target.target_value, 0.0)
        self.assertAlmostEqual(
            target.achievement, 1.0, places=4,
            msg="1.2% against a 2% ceiling is 1.4 raw, clamped to this cycle's "
            "cap of 1.0 - overachievement is only visible where the cap "
            "allows it, which is what kpi_target.cap12 exists to show")

    def test_overachievement_is_clamped_to_the_cycle_cap(self):
        out = self.Fixture.apply_fixtures(['kpi_target.cap12.D-60.normal'])[
            'kpi_target.cap12.D-60.normal']
        target = self.env['aic.hrm.kpi.target'].browse(out['target_id'])
        self.assertAlmostEqual(target.score, 1.2, places=4)

    def test_balanced_scorecard_is_approved_at_exactly_100(self):
        out = self.Fixture.apply_fixtures(['assignment.balanced.D0'])[
            'assignment.balanced.D0']
        assignment = self.env['aic.hrm.kpi.assignment'].browse(
            out['assignment_id'])
        self.assertEqual(assignment.state, 'approved')
        self.assertAlmostEqual(assignment.total_weight, 100.0, places=2)

    def test_underweight_scorecard_cannot_be_submitted(self):
        out = self.Fixture.apply_fixtures(['assignment.underweight.D0'])[
            'assignment.underweight.D0']
        assignment = self.env['aic.hrm.kpi.assignment'].browse(
            out['assignment_id'])
        self.assertEqual(assignment.state, 'draft')
        with self.assertRaises(UserError):
            assignment.action_submit()

    def test_three_thirds_are_accepted_despite_the_rounding(self):
        out = self.Fixture.apply_fixtures(['assignment.rounding.D0'])[
            'assignment.rounding.D0']
        assignment = self.env['aic.hrm.kpi.assignment'].browse(
            out['assignment_id'])
        self.assertEqual(assignment.state, 'submitted',
                         "33.33 + 33.33 + 33.34 must clear the weight gate")
        self.assertEqual(len(assignment.line_ids), 3)

    def test_below_threshold_hides_the_peer_aggregate(self):
        out = self.Fixture.apply_fixtures(['review.below_threshold.D0'])[
            'review.below_threshold.D0']
        review = self.env['aic.hrm.review'].browse(out['review_id'])
        self.assertFalse(review.peer_feedback_ready)
        self.assertEqual(review.peer_score_avg, 0.0,
                         "two raters is a name, not a statistic")

    def test_third_answer_releases_the_aggregate(self):
        self.Fixture.apply_fixtures(['review.ready.D0'])
        out = self.Fixture.search(
            [('fixture_id', '=', 'review.below_threshold.D0')]).outputs
        review = self.env['aic.hrm.review'].browse(out['review_id'])
        self.assertTrue(review.peer_feedback_ready)
        self.assertGreater(review.peer_score_avg, 0.0)

    def test_external_rater_cannot_be_spoken_for(self):
        out = self.Fixture.apply_fixtures(['review.external_rater.D0'])
        request = self.env['aic.hrm.feedback.request'].browse(
            out['review.external_rater.D0']['request_id'])
        template = out['review_template.active.D0']
        peer_user = self.env['hr.employee'].browse(
            out['org.base.D0']['peer_employee_ids'][0]).user_id
        with self.assertRaises(UserError):
            request.with_user(peer_user).submit_feedback([
                {'question_id': template['question_rating_id'], 'rating': 5}])
        self.assertEqual(request.state, 'invited')

    def test_applied_calibration_line_is_immutable_and_undeletable(self):
        out = self.Fixture.apply_fixtures(['calibration.applied.D0'])[
            'calibration.applied.D0']
        line = self.env['aic.hrm.calibration.line'].browse(out['line_id'])
        self.assertEqual(line.state, 'applied')
        with self.assertRaises(ValidationError):
            line.write({'score_after': 0.99})
        with self.assertRaises(ValidationError):
            line.unlink()

    def test_library_pack_applies_as_draft_and_stamps_the_role(self):
        out = self.Fixture.apply_fixtures(['library.applied.D0'])[
            'library.applied.D0']
        objectives = self.env['aic.hrm.objective'].browse(out['objective_ids'])
        self.assertTrue(objectives)
        self.assertEqual(set(objectives.mapped('state')), {'draft'},
                         "an applied pack is a starting point, not a plan")
        employee = self.env['hr.employee'].browse(out['employee_id'])
        self.assertEqual(employee.aic_library_role_id.id, out['role_id'])

    def test_org_chart_carries_the_awkward_people(self):
        out = self.Fixture.apply_fixtures(['org.base.D0'])['org.base.D0']
        Employee = self.env['hr.employee'].with_context(active_test=False)
        external = Employee.browse(out['external_rater_id'])
        leaver = Employee.browse(out['leaver_id'])
        self.assertFalse(external.user_id,
                         "the external rater must have no login")
        self.assertFalse(leaver.active, "the leaver must be archived")
        self.assertFalse(
            Employee.browse(out['no_department_employee_id']).department_id)
        self.assertFalse(Employee.browse(out['no_job_employee_id']).job_id)
