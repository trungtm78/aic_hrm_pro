# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Whether somebody can do the work, and whether they are allowed to.

Two criteria that look alike and behave nothing alike.

**Skills are a distance.** Being one level short of what a seat asks for is a
worse fit, not a disqualification, and a shortlist that only ever offers exact
matches is a shortlist nobody can staff from. So the gap becomes a score that
falls off, and a policy decides how far short is too far.

**Certificates are a fact.** Somebody either holds a valid one for the whole
window or they do not, and no weighting makes an expired certificate acceptable
on regulated work. That one is a gate, and it compares dates directly rather
than reading a nightly-refreshed field: a cron running late must not be able to
put an unlicensed person on site.
"""
from odoo.tests import tagged

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class SkillScoringCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['aic.hrm.match.engine']
        cls.compat = cls.env['aic.hrm.match.skill.compat']
        cls.skill_type, cls.python, cls.expert = cls._make_skill_set(
            'Programming', 'Python')
        cls.levels = cls.skill_type.skill_level_ids.sorted('level_progress')
        cls.beginner, cls.confirmed = cls.levels[0], cls.levels[1]

        cls.criterion = cls.env['aic.hrm.match.criterion'].create({
            'code': 'skill_match', 'name': 'Skills',
            'category': 'skill', 'normalization': 'none'})
        cls.policy = cls.env['aic.hrm.match.policy'].create({
            'name': 'Skills', 'code': 'skills_policy', 'is_default': True,
            'persist_mode': 'full'})
        cls.env['aic.hrm.match.policy.line'].create({
            'policy_id': cls.policy.id, 'criterion_id': cls.criterion.id})
        cls.policy.action_activate()

    def _request(self, requirement='important', level=None, weight=1.0):
        request = self.env['aic.hrm.match.request'].create({
            'name': 'Needs Python',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        slot = self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Dev',
            'required_hours': 8.0})
        self.env['aic.hrm.match.request.slot.skill'].create({
            'slot_id': slot.id, 'skill_id': self.python.id,
            'min_level_id': (level or self.confirmed).id,
            'requirement': requirement, 'weight': weight})
        return request

    def _skill(self, employee, skill=None, level=None, verified=True):
        """Give somebody a skill, verified unless the test says otherwise.

        Verified is the interesting default: an unverified line is discounted,
        so a fixture that left it unverified would make every "meets the
        requirement" assertion fail by a factor nobody was testing.
        """
        line = self._make_employee_skill(
            employee, skill or self.python, level or self.confirmed)
        if verified:
            line.sudo().write({'verify_state': 'submitted'})
            line.sudo().write({'verify_state': 'verified'})
        return line

    def _score_for(self, employee, request=None):
        run = self.engine.run_match(request or self._request())
        candidate = run.candidate_ids.filtered(
            lambda c: c.employee_id == employee)
        line = candidate.score_line_ids.filtered(
            lambda l: l.criterion_code == 'skill_match')
        return candidate, line

    # -- the distance --------------------------------------------------------

    def test_meeting_the_requirement_scores_full_marks(self):
        employee = self._make_employee('Meets It')
        self._make_employee_skill(employee, self.python, self.confirmed)
        _candidate, line = self._score_for(employee)
        self.assertAlmostEqual(line.normalized_score, 1.0, places=6)

    def test_exceeding_the_requirement_is_not_worth_more_than_meeting_it(self):
        """A seat asking for confirmed Python is filled equally well by an
        expert. Paying for the surplus would send every request to the most
        senior person available and call it a match."""
        meets = self._make_employee('Meets')
        exceeds = self._make_employee('Exceeds')
        self._make_employee_skill(meets, self.python, self.confirmed)
        self._make_employee_skill(exceeds, self.python, self.expert)
        request = self._request()
        _c1, meets_line = self._score_for(meets, request)
        _c2, exceeds_line = self._score_for(exceeds, request)
        self.assertAlmostEqual(meets_line.normalized_score,
                               exceeds_line.normalized_score, places=6)

    def test_falling_short_costs_score_in_proportion(self):
        """The whole point of scoring rather than gating: somebody one level
        down is a worse fit and still a candidate. Ranking them last is a
        judgement; removing them is a decision nobody asked for."""
        short = self._make_employee('One Level Down')
        self._make_employee_skill(short, self.python, self.beginner)
        _candidate, line = self._score_for(short)
        self.assertGreater(line.normalized_score, 0.0)
        self.assertLess(line.normalized_score, 1.0)

    def test_falling_far_short_scores_zero_rather_than_going_negative(self):
        """A gap wider than the tolerance is simply the worst score there is.
        Letting it run negative would make one missing skill drag down a total
        that other criteria had legitimately earned."""
        request = self._request(level=self.expert)
        far = self._make_employee('Far Short')
        self._make_employee_skill(far, self.python, self.beginner)
        _candidate, line = self._score_for(far, request)
        self.assertGreaterEqual(line.normalized_score, 0.0)

    def test_having_no_record_of_the_skill_scores_zero_not_missing(self):
        """The one place where absence is evidence. Everywhere else a blank
        means nobody filled the form in; here the skills file is the record of
        what somebody can do, and not appearing in it for Python is the answer
        to whether they know Python.
        """
        nobody = self._make_employee('No Python')
        _candidate, line = self._score_for(nobody)
        self.assertFalse(line.is_missing)
        self.assertAlmostEqual(line.normalized_score, 0.0, places=6)

    def test_a_slot_asking_for_nothing_says_nothing(self):
        """No skill lines on the seat means the criterion has no question to
        answer, which is missing data - not a score of zero for everybody,
        which would flatten the whole ranking."""
        request = self.env['aic.hrm.match.request'].create({
            'name': 'No skills asked',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Any', 'required_hours': 8.0})
        employee = self._make_employee('Anyone')
        _candidate, line = self._score_for(employee, request)
        self.assertTrue(line.is_missing)

    def test_the_weight_on_a_skill_line_decides_how_much_it_counts(self):
        """Two skills, one of them what the work is actually about. Averaging
        them evenly makes the seat's own priorities invisible."""
        _type, sql, sql_expert = self._make_skill_set('Data', 'SQL')
        request = self._request(weight=3.0)
        slot = request.slot_ids[0]
        self.env['aic.hrm.match.request.slot.skill'].create({
            'slot_id': slot.id, 'skill_id': sql.id,
            'min_level_id': sql_expert.id,
            'requirement': 'important', 'weight': 1.0})

        strong_where_it_counts = self._make_employee('Python Strong')
        self._make_employee_skill(
            strong_where_it_counts, self.python, self.confirmed)
        strong_elsewhere = self._make_employee('SQL Strong')
        self._make_employee_skill(strong_elsewhere, sql, sql_expert)

        _c1, heavy = self._score_for(strong_where_it_counts, request)
        _c2, light = self._score_for(strong_elsewhere, request)
        self.assertGreater(heavy.normalized_score, light.normalized_score)

    def test_the_evidence_names_the_skill_and_the_gap(self):
        """A score of 0.6 on "skills" tells a planner nothing. Which skill, how
        far short, is what they can act on."""
        short = self._make_employee('Evidenced')
        self._make_employee_skill(short, self.python, self.beginner)
        _candidate, line = self._score_for(short)
        text = ' '.join(line.evidence_ids.mapped('label'))
        self.assertIn('Python', text)

    # -- the gate ------------------------------------------------------------

    def test_a_mandatory_skill_below_the_bar_removes_the_candidate(self):
        """Mandatory means mandatory. A seat that cannot be done without the
        skill is not served by offering somebody who lacks it, however well
        they score elsewhere."""
        request = self._request(requirement='mandatory')
        short = self._make_employee('Mandatory Short')
        self._make_employee_skill(short, self.python, self.beginner)
        candidate, _line = self._score_for(short, request)
        self.assertFalse(candidate.eligible)
        self.assertEqual(candidate.rejection_code, 'missing_mandatory_skill')
        self.assertIn('Python', candidate.rejection_detail)

    def test_a_mandatory_skill_that_is_met_does_not_remove_anybody(self):
        request = self._request(requirement='mandatory')
        fine = self._make_employee('Mandatory Met')
        self._make_employee_skill(fine, self.python, self.confirmed)
        candidate, _line = self._score_for(fine, request)
        self.assertTrue(candidate.eligible)

    def test_an_important_skill_below_the_bar_only_costs_score(self):
        request = self._request(requirement='important')
        short = self._make_employee('Important Short')
        self._make_employee_skill(short, self.python, self.beginner)
        candidate, line = self._score_for(short, request)
        self.assertTrue(candidate.eligible)
        self.assertLess(line.normalized_score, 1.0)

    def test_a_stretch_line_lets_somebody_grow_into_the_seat(self):
        """The only way past a mandatory line, and it is deliberate: somebody
        has to have marked this seat as one worth stretching into. It is also
        recorded, because a stretch assignment that nobody can find afterwards
        is indistinguishable from a mistake."""
        request = self._request(requirement='mandatory')
        request.slot_ids[0].skill_line_ids.stretch_allowed = True
        short = self._make_employee('Stretching')
        self._make_employee_skill(short, self.python, self.beginner)
        candidate, _line = self._score_for(short, request)
        self.assertTrue(candidate.eligible)
        self.assertTrue(candidate.is_stretch)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class CertificationGateCase(MatchCase):
    """Holding the certificate for the whole window, or not being offered.

    Compared against the dates directly rather than a stored field a cron
    refreshes: the cron running late would otherwise put somebody unlicensed in
    front of a planner, and the screen would look exactly the same as if they
    were licensed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['aic.hrm.match.engine']
        cls.compat = cls.env['aic.hrm.match.skill.compat']
        cls.cert_type, cls.licence, cls.held = cls._make_skill_set(
            'Safety', 'Site Safety Licence', certification=True)

        cls.criterion = cls.env['aic.hrm.match.criterion'].create({
            'code': 'certification', 'name': 'Certification',
            'category': 'skill', 'mode': 'hard',
            'normalization': 'none'})
        cls.policy = cls.env['aic.hrm.match.policy'].create({
            'name': 'Certified', 'code': 'cert_policy', 'is_default': True,
            'persist_mode': 'full'})
        cls.env['aic.hrm.match.policy.line'].create({
            'policy_id': cls.policy.id, 'criterion_id': cls.criterion.id})
        cls.policy.action_activate()

    def _request(self):
        request = self.env['aic.hrm.match.request'].create({
            'name': 'Regulated work',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Site engineer',
            'required_hours': 8.0,
            'required_certification_skill_ids': [(6, 0, self.licence.ids)]})
        return request

    def _certify(self, employee, valid_from=None, valid_to=None,
                 verify_state='verified'):
        line = self._make_employee_skill(
            employee, self.licence, self.held,
            valid_from=valid_from, valid_to=valid_to)
        line.sudo().write({'verify_state': 'submitted'})
        if verify_state != 'submitted':
            line.sudo().write({'verify_state': verify_state})
        return line

    def _candidate(self, employee, request=None):
        run = self.engine.run_match(request or self._request())
        return run.candidate_ids.filtered(
            lambda c: c.employee_id == employee)

    def test_a_certificate_covering_the_window_lets_somebody_through(self):
        employee = self._make_employee('Licensed')
        self._certify(employee, '2026-01-01', '2027-01-01')
        self.assertTrue(self._candidate(employee).eligible)

    def test_a_certificate_with_no_end_date_never_expires(self):
        """An open-ended certificate is the common case for qualifications that
        do not lapse. Treating a blank end date as expired would exclude
        everybody who holds one."""
        employee = self._make_employee('Permanently Licensed')
        self._certify(employee, '2026-01-01', None)
        self.assertTrue(self._candidate(employee).eligible)

    def test_a_certificate_expiring_inside_the_window_is_not_enough(self):
        """The trap this test exists for: comparing the expiry against today
        passes somebody whose licence runs out on the Wednesday of the job."""
        employee = self._make_employee('Expires Midway')
        self._certify(employee, '2026-01-01', '2026-09-16')
        candidate = self._candidate(employee)
        self.assertFalse(candidate.eligible)
        self.assertEqual(candidate.rejection_code, 'certification_expired')

    def test_a_certificate_starting_after_the_work_does_is_not_enough(self):
        """The mirror of the same trap. Checking only the expiry date accepts a
        licence that begins after the job has already started."""
        employee = self._make_employee('Starts Late')
        self._certify(employee, '2026-09-16', '2027-01-01')
        candidate = self._candidate(employee)
        self.assertFalse(candidate.eligible)
        self.assertEqual(candidate.rejection_code, 'certification_expired')

    def test_an_unverified_certificate_does_not_open_the_gate(self):
        """Somebody typed it in. That is a claim, not a credential, and the
        difference is the entire reason the verification workflow exists."""
        employee = self._make_employee('Self Declared')
        self._certify(employee, '2026-01-01', '2027-01-01',
                      verify_state='submitted')
        candidate = self._candidate(employee)
        self.assertFalse(candidate.eligible)
        self.assertEqual(candidate.rejection_code, 'certification_expired')

    def test_not_holding_the_certificate_at_all_removes_the_candidate(self):
        employee = self._make_employee('Unlicensed')
        candidate = self._candidate(employee)
        self.assertFalse(candidate.eligible)
        self.assertEqual(candidate.rejection_code, 'certification_expired')
        self.assertIn('Site Safety Licence', candidate.rejection_detail)

    def test_a_seat_needing_no_certificate_excludes_nobody(self):
        employee = self._make_employee('Unregulated Work')
        request = self.env['aic.hrm.match.request'].create({
            'name': 'Ordinary work',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Dev', 'required_hours': 8.0})
        self.assertTrue(self._candidate(employee, request).eligible)
