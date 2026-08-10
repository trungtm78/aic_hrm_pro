# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The two screens somebody actually starts from.

A planner does not begin at a staffing request; they begin at a task that needs
somebody on it. So the first wizard turns "this task, this fortnight" into a
request, a slot and a ranking in one press, filling in everything the task
already knows.

Both wizards are transient, which is exactly why neither may be where the
decision lives. A transient record is garbage-collected and carries no chatter,
so a wizard that recorded an assignment in itself would leave an assignment
nobody can explain a week later. What each one produces is a stored record.
"""
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class FindFitWizardCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['aic.hrm.match.wizard.find_fit']
        cls.criterion = cls._criterion('availability', category='availability', normalization='ratio')
        cls.policy = cls.env['aic.hrm.match.policy'].create({
            'name': 'Wizard', 'code': 'wizard_policy', 'is_default': True})
        cls.env['aic.hrm.match.policy.line'].create({
            'policy_id': cls.policy.id, 'criterion_id': cls.criterion.id})
        cls.policy.action_activate()

        cls.customer = cls.env['res.partner'].create({'name': 'Wizard Corp'})
        cls.project = cls.env['project.project'].create({
            'name': 'Billing migration', 'partner_id': cls.customer.id})
        cls.task = cls.env['project.task'].create({
            'name': 'Migrate the billing API',
            'project_id': cls.project.id,
            'date_deadline': '2026-09-18'})
        cls.employee = cls._make_employee('Wizard Candidate')

    def test_opening_it_from_a_task_fills_in_what_the_task_knows(self):
        """The planner arrived from a task. Making them retype the project, the
        customer and the deadline is how a two-click flow becomes a form nobody
        opens twice."""
        wizard = self.Wizard.with_context(
            active_model='project.task', active_id=self.task.id).create({})
        self.assertEqual(wizard.task_id, self.task)
        self.assertEqual(wizard.project_id, self.project)
        self.assertEqual(wizard.partner_id, self.customer)
        self.assertTrue(wizard.date_start)
        self.assertTrue(wizard.date_end)

    def test_the_window_ends_on_the_deadline_it_was_given(self):
        wizard = self.Wizard.with_context(
            active_model='project.task', active_id=self.task.id).create({})
        self.assertEqual(str(wizard.date_end)[:10], '2026-09-18')

    def test_a_task_with_no_deadline_still_opens_with_a_usable_window(self):
        """Most tasks have no deadline. Refusing to open, or opening with an
        empty window that fails validation on save, both end the flow at the
        first screen."""
        task = self.env['project.task'].create({
            'name': 'Undated work', 'project_id': self.project.id})
        wizard = self.Wizard.with_context(
            active_model='project.task', active_id=task.id).create({})
        self.assertTrue(wizard.date_start)
        self.assertLess(wizard.date_start, wizard.date_end)

    def test_it_produces_a_stored_request_and_ranking(self):
        """The wizard is transient and the answer must not be. A shortlist that
        disappears when the dialog closes cannot be revisited, compared, or
        used to explain a decision afterwards."""
        wizard = self.Wizard.with_context(
            active_model='project.task', active_id=self.task.id).create({})
        action = wizard.action_create_and_rank()

        request = self.env['aic.hrm.match.request'].search(
            [('task_id', '=', self.task.id)])
        self.assertEqual(len(request), 1)
        self.assertEqual(len(request.slot_ids), 1)
        self.assertTrue(request.latest_run_id)
        self.assertEqual(request.state, 'ranked')
        self.assertEqual(action['res_model'], 'aic.hrm.match.run')
        self.assertEqual(action['res_id'], request.latest_run_id.id)

    def test_the_request_it_creates_remembers_the_task_by_name(self):
        """The link is set null on purpose, so the name has to be captured now.
        A tidied-up task must not turn the staffing record into a mystery."""
        wizard = self.Wizard.with_context(
            active_model='project.task', active_id=self.task.id).create({})
        wizard.action_create_and_rank()
        request = self.env['aic.hrm.match.request'].search(
            [('task_id', '=', self.task.id)])
        self.assertIn('billing', request.task_ref_snapshot)

    def test_the_hours_asked_for_reach_the_slot(self):
        wizard = self.Wizard.with_context(
            active_model='project.task', active_id=self.task.id).create({})
        wizard.required_hours = 12.0
        wizard.action_create_and_rank()
        request = self.env['aic.hrm.match.request'].search(
            [('task_id', '=', self.task.id)])
        self.assertAlmostEqual(request.slot_ids.required_hours, 12.0, places=1)

    def test_a_window_that_ends_before_it_starts_is_refused_at_the_wizard(self):
        """Caught here rather than by the request's own constraint, so the
        planner sees it on the screen they typed it on."""
        wizard = self.Wizard.with_context(
            active_model='project.task', active_id=self.task.id).create({})
        wizard.write({'date_start': '2026-09-20 00:00:00',
                      'date_end': '2026-09-14 00:00:00'})
        with self.assertRaises(UserError):
            wizard.action_create_and_rank()

    def test_opening_it_without_a_task_is_allowed(self):
        """Not every staffing need comes from a task - a role on a project, or
        a standalone request, are both normal. The wizard has to open cold."""
        wizard = self.Wizard.create({
            'name': 'Standalone need',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        wizard.action_create_and_rank()
        request = self.env['aic.hrm.match.request'].search(
            [('name', '=', 'Standalone need')])
        self.assertEqual(len(request), 1)
        self.assertFalse(request.task_id)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class AssignWizardCase(MatchCase):
    """Turning a shortlist into bookings, in one transaction.

    The point of doing it here rather than one candidate at a time is that
    half-applied staffing is worse than none: two of three seats booked and the
    third refused for a clash leaves a plan nobody agreed to, and no screen
    shows that is what happened.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['aic.hrm.match.wizard.assign']
        cls.engine = cls.env['aic.hrm.match.engine']
        cls.criterion = cls._criterion('availability', category='availability', normalization='ratio')
        cls.policy = cls.env['aic.hrm.match.policy'].create({
            'name': 'Assign', 'code': 'assign_policy', 'is_default': True})
        cls.env['aic.hrm.match.policy.line'].create({
            'policy_id': cls.policy.id, 'criterion_id': cls.criterion.id})
        cls.policy.action_activate()
        cls.employee = cls._make_employee('Assignable')

    def _ranked_request(self):
        request = self.env['aic.hrm.match.request'].create({
            'name': 'To staff',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Dev', 'required_hours': 8.0})
        request.action_rank()
        return request

    def _wizard_for(self, request):
        run = request.latest_run_id
        return self.Wizard.with_context(
            active_model='aic.hrm.match.run', active_id=run.id).create({})

    def test_it_opens_with_the_top_candidate_already_chosen(self):
        """The common case is agreeing with the ranking. Making the planner
        pick the name the screen just recommended adds a step that teaches
        nothing."""
        request = self._ranked_request()
        wizard = self._wizard_for(request)
        self.assertTrue(wizard.decision_ids)
        top = request.latest_run_id.candidate_ids.filtered(
            lambda c: c.rank == 1)
        self.assertEqual(wizard.decision_ids[0].employee_id, top.employee_id)

    def test_confirming_creates_a_decision_and_the_bookings_behind_it(self):
        request = self._ranked_request()
        wizard = self._wizard_for(request)
        wizard.action_assign()

        self.assertTrue(request.decision_ids)
        decision = request.decision_ids[0]
        self.assertEqual(decision.state, 'confirmed')
        self.assertTrue(decision.allocation_ids)
        self.assertEqual(request.state, 'staffed')

    def test_the_booking_covers_the_window_the_seat_asked_for(self):
        request = self._ranked_request()
        self._wizard_for(request).action_assign()
        allocation = request.decision_ids.allocation_ids
        self.assertEqual(allocation.date_start, request.slot_ids.date_start
                         or request.date_start)
        self.assertAlmostEqual(allocation.allocated_hours, 8.0, places=1)

    def test_assigning_advances_the_rotation_so_the_next_tie_breaks_elsewhere(self):
        """Ties rotate between staffing rounds, not between re-ranks of the
        same round. A decision is what marks the end of a round."""
        request = self._ranked_request()
        before = request.rotation_epoch
        self._wizard_for(request).action_assign()
        self.assertGreater(request.rotation_epoch, before)

    def _somebody_else(self, wizard, request):
        """Anybody the ranking did not put first.

        Taken from the run rather than freshly created: everybody is equally
        free in these fixtures, so a new employee can win the tie-break and
        turn out to be the recommendation - which would make the override
        tests pass or fail on a hash.
        """
        recommended = wizard.decision_ids[0].employee_id
        return request.latest_run_id.candidate_ids.filtered(
            lambda c: c.eligible and c.employee_id
            and c.employee_id != recommended)[:1].employee_id

    def test_choosing_below_the_top_is_recorded_as_an_override(self):
        """Overrides are the most valuable thing the log collects: they are
        where the weights disagree with the people who know the work."""
        self._make_employee('Second Choice')
        request = self._ranked_request()
        wizard = self._wizard_for(request)
        other = self._somebody_else(wizard, request)
        self.assertTrue(other)
        wizard.decision_ids[0].write({
            'employee_id': other.id,
            'override_reason': 'Knows the customer from last year.'})
        wizard.action_assign()

        decision = request.decision_ids[0]
        self.assertTrue(decision.is_override)
        self.assertEqual(decision.employee_id, other)
        self.assertGreater(decision.rank_at_decision, 1,
                           'the rank recorded must belong to the person who '
                           'was chosen, not to the one recommended')

    def test_an_override_without_a_reason_is_refused(self):
        """An override nobody explained teaches the next round nothing, and
        the override log exists precisely to be read back."""
        self._make_employee('Unexplained Choice')
        request = self._ranked_request()
        wizard = self._wizard_for(request)
        other = self._somebody_else(wizard, request)
        self.assertTrue(other)
        wizard.decision_ids[0].employee_id = other.id
        with self.assertRaises(UserError):
            wizard.action_assign()

    def test_assigning_nobody_is_refused_rather_than_silently_doing_nothing(self):
        request = self._ranked_request()
        wizard = self._wizard_for(request)
        wizard.decision_ids.unlink()
        with self.assertRaises(UserError):
            wizard.action_assign()
