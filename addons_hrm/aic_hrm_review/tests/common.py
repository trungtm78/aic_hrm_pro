# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.tests import TransactionCase


class ReviewCase(TransactionCase):
    """Org fixture: manager + three peers reporting to them, a perf cycle
    with a scorecard for the reviewee, and a default review template."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.department = env['hr.department'].create({'name': 'Review Dept'})

        def make_user(name, login, groups):
            return env['res.users'].create({
                'name': name, 'login': login,
                'groups_id': [(6, 0, [env.ref('base.group_user').id,
                                      env.ref(groups).id])],
            })

        cls.manager_user = make_user(
            'Rev Manager', 'rev_manager', 'aic_hrm_base.group_hrm_manager')
        cls.reviewee_user = make_user(
            'Rev Employee', 'rev_employee', 'aic_hrm_base.group_hrm_user')
        cls.peer1_user = make_user(
            'Peer One', 'rev_peer1', 'aic_hrm_base.group_hrm_user')
        cls.peer2_user = make_user(
            'Peer Two', 'rev_peer2', 'aic_hrm_base.group_hrm_user')
        cls.peer3_user = make_user(
            'Peer Three', 'rev_peer3', 'aic_hrm_base.group_hrm_user')

        cls.manager_employee = env['hr.employee'].create({
            'name': 'Rev Manager', 'user_id': cls.manager_user.id,
            'department_id': cls.department.id})
        cls.reviewee = env['hr.employee'].create({
            'name': 'Rev Employee', 'user_id': cls.reviewee_user.id,
            'department_id': cls.department.id,
            'parent_id': cls.manager_employee.id})
        cls.peer1 = env['hr.employee'].create({
            'name': 'Peer One', 'user_id': cls.peer1_user.id,
            'department_id': cls.department.id,
            'parent_id': cls.manager_employee.id})
        cls.peer2 = env['hr.employee'].create({
            'name': 'Peer Two', 'user_id': cls.peer2_user.id,
            'department_id': cls.department.id,
            'parent_id': cls.manager_employee.id})
        cls.peer3 = env['hr.employee'].create({
            'name': 'Peer Three', 'user_id': cls.peer3_user.id,
            'department_id': cls.department.id,
            'parent_id': cls.manager_employee.id})

        cls.perf_cycle = env['aic.hrm.cycle'].create({
            'name': 'Review FY', 'code': 'REV-FY', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31'})
        kpi = env['aic.hrm.kpi'].create({
            'name': 'Review KPI', 'code': 'REV-KPI'})
        target = env['aic.hrm.kpi.target'].create({
            'kpi_id': kpi.id, 'cycle_id': cls.perf_cycle.id,
            'employee_id': cls.reviewee.id, 'target_value': 100.0})
        env['aic.hrm.kpi.period.result'].create({
            'kpi_target_id': target.id, 'date_from': '2026-01-01',
            'date_to': '2026-01-31', 'actual': 90.0, 'state': 'confirmed'})
        cls.assignment = env['aic.hrm.kpi.assignment'].create({
            'employee_id': cls.reviewee.id, 'cycle_id': cls.perf_cycle.id,
            'line_ids': [(0, 0, {'kpi_target_id': target.id,
                                 'weight': 100.0})]})

        cls.form = env['aic.hrm.review.form'].create({
            'name': 'Standard form',
            'section_ids': [(0, 0, {
                'name': 'Competencies',
                'question_ids': [
                    (0, 0, {'name': 'Delivers on commitments',
                            'question_type': 'rating_10'}),
                    (0, 0, {'name': 'What should they keep doing?',
                            'question_type': 'text'}),
                ],
            })],
        })
        cls.template = env['aic.hrm.review.template'].create({
            'name': 'Annual template',
            'form_id': cls.form.id,
            'stage_ids': [
                (0, 0, {'sequence': 1, 'name': 'Self', 'stage_type': 'self'}),
                (0, 0, {'sequence': 2, 'name': 'Peers',
                        'stage_type': 'peer_feedback', 'min_raters': 3}),
                (0, 0, {'sequence': 3, 'name': 'Manager',
                        'stage_type': 'manager'}),
                (0, 0, {'sequence': 4, 'name': 'Final',
                        'stage_type': 'final'}),
            ],
        })

    @classmethod
    def _make_review_cycle(cls):
        self = cls
        review_cycle = self.env['aic.hrm.review.cycle'].create({
            'name': 'Annual review',
            'perf_cycle_id': self.perf_cycle.id,
            'template_id': self.template.id,
            'date_start': '2026-12-01',
            'date_end': '2026-12-31',
            'department_ids': [(4, self.department.id)],
        })
        review_cycle.action_generate_reviews()
        return review_cycle
