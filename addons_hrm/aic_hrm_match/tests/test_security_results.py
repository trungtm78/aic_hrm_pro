# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Who may read a ranking, and who may not.

The four result models hold the thing this product exists to produce and the
thing it most has to keep quiet: a number saying how each colleague compares.
Odoo's rule semantics make the dangerous case the *default* one - a model with
no applicable record rule is readable by anyone the ACL lets in, so forgetting a
rule does not fail, it opens.

That is what happened here. The ACL granted read to the "own profile" group so
somebody could see their own candidacy, no rule narrowed it to their own, and
every employee could read every colleague's score through search, export or
RPC. Nothing on any screen showed it.

Each test below names the way in, because the screens are not the boundary:
a search, a direct read by id, and a read_group that leaks the same numbers as
aggregates without ever reading a row.
"""
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class ResultVisibilityCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['aic.hrm.match.engine']
        cls.criterion = cls._criterion('availability')
        cls.policy = cls.env['aic.hrm.match.policy'].create({
            'name': 'Visibility', 'code': 'visibility', 'sequence': 1,
            'persist_mode': 'full', 'show_own_candidacy': True})
        cls.env['aic.hrm.match.policy.line'].create({
            'policy_id': cls.policy.id, 'criterion_id': cls.criterion.id,
            'weight': 1.0})
        cls.policy.action_activate()

        cls.subject = cls._make_employee('Visible Subject')
        cls.peer = cls._make_employee('Nosy Peer')

        cls.subject_user = cls._make_user('Subject User', ['group_match_user'])
        cls.peer_user = cls._make_user('Peer User', ['group_match_user'])
        cls.subject.user_id = cls.subject_user.id
        cls.peer.user_id = cls.peer_user.id
        cls.planner = cls._make_user('Result Planner', ['group_match_planner'])

        request = cls.env['aic.hrm.match.request'].create({
            'name': 'Visibility run',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        cls.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Dev', 'required_hours': 8.0})
        cls.match_run = cls.engine.run_match(request, policy=cls.policy)
        cls.subject_candidate = cls.match_run.candidate_ids.filtered(
            lambda c: c.employee_id == cls.subject)

    def _as(self, user, model):
        return self.env[model].with_user(user)

    # -- what an ordinary employee may see -----------------------------------

    def test_an_employee_sees_only_their_own_candidacy(self):
        """The whole promise. A search returning colleagues is not a display
        problem, it is everybody's ranking readable by everybody."""
        visible = self._as(self.subject_user, 'aic.hrm.match.candidate').search([])
        self.assertTrue(visible, 'somebody must be able to see their own row')
        self.assertEqual(visible.employee_id, self.subject)

    def test_an_employee_cannot_read_a_colleague_by_id(self):
        """Search filters; a direct read does not, unless a rule says so. This
        is the way round the list view that costs nothing to try."""
        peer_candidate = self.match_run.candidate_ids.filtered(
            lambda c: c.employee_id == self.peer)
        self.assertTrue(peer_candidate)
        with self.assertRaises(AccessError):
            self._as(self.peer_user, 'aic.hrm.match.candidate').browse(
                self.subject_candidate.id).read(['total_score'])

    def test_an_employee_cannot_group_their_way_to_the_numbers(self):
        """read_group returns aggregates without reading rows, so a model that
        only filters searches still hands over the scores - averaged, but per
        person if you group by person."""
        grouped = self._as(self.subject_user, 'aic.hrm.match.candidate') \
            .read_group([], ['total_score:avg'], ['employee_id'])
        employees = {row['employee_id'][0] for row in grouped
                     if row.get('employee_id')}
        self.assertLessEqual(employees, {self.subject.id})

    def test_the_breakdown_is_no_more_visible_than_the_score(self):
        """A score line carries the same information one criterion at a time.
        Restricting the candidate and forgetting the lines leaks the ranking in
        instalments."""
        lines = self._as(self.subject_user, 'aic.hrm.match.score.line').search([])
        self.assertLessEqual(set(lines.mapped('candidate_id.employee_id.id')),
                             {self.subject.id, False})

    def test_the_evidence_is_no_more_visible_than_the_breakdown(self):
        evidence = self._as(self.subject_user, 'aic.hrm.match.evidence').search([])
        self.assertLessEqual(
            set(evidence.mapped('score_line_id.candidate_id.employee_id.id')),
            {self.subject.id, False})

    def test_an_employee_cannot_read_the_run_itself(self):
        """The run carries the counts - how many were considered, how many
        excluded - which is information about colleagues even without names.

        Refused at the access list rather than filtered to nothing by a rule.
        Both hide the rows; only this one also says plainly that an employee
        has no business here, so nobody later adds a rule to "fix" an empty
        list.
        """
        with self.assertRaises(AccessError):
            self._as(self.subject_user, 'aic.hrm.match.run').search([])

    def test_a_policy_can_close_own_candidacy_entirely(self):
        """Some companies do not show people their own ranking at all. The
        switch has to work by narrowing the rule's domain, never by disabling
        the rule - a disabled rule removes a restriction, it does not add one.
        """
        closed = self.policy.action_new_version()
        closed.show_own_candidacy = False
        closed.action_activate()

        request = self.env['aic.hrm.match.request'].create({
            'name': 'Closed run',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Dev', 'required_hours': 8.0})
        run = self.engine.run_match(request, policy=closed)

        visible = self._as(self.subject_user, 'aic.hrm.match.candidate').search(
            [('run_id', '=', run.id)])
        self.assertFalse(visible)

    # -- what a planner may see ----------------------------------------------

    def test_a_planner_sees_the_whole_shortlist(self):
        """The job requires it. A planner who can only see part of the ranking
        cannot staff from it."""
        visible = self._as(self.planner, 'aic.hrm.match.candidate').search(
            [('run_id', '=', self.match_run.id)])
        self.assertEqual(len(visible), len(self.match_run.candidate_ids))

    def test_a_planner_still_cannot_open_the_identity_mapping(self):
        """Anonymity does not bend for the person doing the staffing - that is
        the only case where it would matter."""
        with self.assertRaises(AccessError):
            self._as(self.planner, 'aic.hrm.match.identity').search([])
