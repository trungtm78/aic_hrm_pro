# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'aic_hrm_library')
class TestLibrary(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cycle = cls.env['aic.hrm.cycle'].create({
            'name': 'Lib FY', 'code': 'LIB-FY', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31'})
        cls.employee = cls.env['hr.employee'].create({'name': 'Lib Owner'})

    def test_builtin_roles_seeded(self):
        roles = self.env['aic.hrm.library.role'].search(
            [('company_id', '=', False)])
        self.assertGreaterEqual(
            len(roles), 10,
            'the library ships at least 10 shared role packs')
        for role in roles:
            self.assertTrue(
                role.objective_template_ids,
                f'{role.name}: every built-in role has objective templates')
            self.assertTrue(
                role.kpi_template_ids,
                f'{role.name}: every built-in role has KPI templates')
            self.assertTrue(
                role.collection_playbook,
                f'{role.name}: every built-in role documents how to '
                'collect its numbers')

    def test_industry_filter(self):
        Industry = self.env['aic.hrm.library.industry']
        mfg = Industry.search([('code', '=', 'MFG')], limit=1)
        self.assertTrue(mfg, 'built-in industries are seeded')
        self.assertGreaterEqual(len(Industry.search([])), 4)
        production = self.env['aic.hrm.library.role'].search(
            [('code', '=', 'PROD')], limit=1)
        self.assertIn(mfg, production.industry_ids,
                      'manufacturing role is tagged with its industry')
        # Same domain the apply wizard puts on role_id: industry roles
        # plus every cross-industry role.
        visible = self.env['aic.hrm.library.role'].search(
            ['|', ('industry_ids', '=', False),
             ('industry_ids', '=', mfg.id)])
        self.assertIn(production, visible)
        sales = self.env['aic.hrm.library.role'].search(
            [('code', '=', 'SALES')], limit=1)
        self.assertIn(sales, visible,
                      'cross-industry roles stay available under any filter')
        trade_only = self.env['aic.hrm.library.role'].search(
            [('code', '=', 'PURCH')], limit=1)
        self.assertNotIn(trade_only, visible,
                         'roles tagged for another industry are filtered out')

    def test_apply_pack_creates_draft_goals(self):
        sales = self.env['aic.hrm.library.role'].search(
            [('code', '=', 'SALES')], limit=1)
        wizard = self.env['aic.hrm.library.apply.wizard'].create({
            'role_id': sales.id,
            'cycle_id': self.cycle.id,
            'employee_id': self.employee.id,
        })
        wizard.action_apply()
        objectives = self.env['aic.hrm.objective'].search(
            [('cycle_id', '=', self.cycle.id)])
        self.assertTrue(objectives)
        self.assertTrue(all(o.state == 'draft' for o in objectives),
                        'library packs land as drafts to tailor')
        self.assertTrue(objectives.kr_ids, 'key results came along')
        targets = self.env['aic.hrm.kpi.target'].search(
            [('cycle_id', '=', self.cycle.id),
             ('employee_id', '=', self.employee.id)])
        self.assertTrue(targets, 'role KPI templates became targets')

    def test_apply_pack_for_team(self):
        team = self.env['aic.hrm.team'].create({
            'name': 'Library Squad'})
        engineering = self.env['aic.hrm.library.role'].search(
            [('code', '=', 'ENG')], limit=1)
        self.env['aic.hrm.library.apply.wizard'].create({
            'role_id': engineering.id,
            'cycle_id': self.cycle.id,
            'team_id': team.id,
            'include_kpis': False,
        }).action_apply()
        objectives = self.env['aic.hrm.objective'].search(
            [('cycle_id', '=', self.cycle.id), ('team_id', '=', team.id)])
        self.assertTrue(objectives)
        self.assertTrue(all(o.level == 'team' for o in objectives),
                        'a pack applied to a team lands at team level')

    def test_apply_twice_no_duplicate_targets(self):
        sales = self.env['aic.hrm.library.role'].search(
            [('code', '=', 'SALES')], limit=1)
        for _round in range(2):
            self.env['aic.hrm.library.apply.wizard'].create({
                'role_id': sales.id,
                'cycle_id': self.cycle.id,
                'employee_id': self.employee.id,
                'template_ids': [(5, 0, 0)],
            }).action_apply()
        targets = self.env['aic.hrm.kpi.target'].search([
            ('cycle_id', '=', self.cycle.id),
            ('employee_id', '=', self.employee.id)])
        codes = targets.mapped('kpi_id.code')
        self.assertEqual(len(codes), len(set(codes)),
                         'KPI targets are not duplicated on re-apply')

    def test_capture_grows_company_knowledge(self):
        role = self.env['aic.hrm.library.role'].create(
            {'name': 'Custom Role', 'code': 'CUST-ROLE'})
        wizard = self.env['aic.hrm.library.capture.wizard'].create({
            'role_id': role.id,
            'raw_text': (
                'ghi chú linh tinh bị bỏ qua\n'
                'OBJ: Win the enterprise segment | aspirational\n'
                'KR: Enterprise deals closed | number | higher | 12 | deals\n'
                'KR: Expansion revenue share | percent | higher | 30 | %\n'
                'KPI: Pipeline coverage ratio | x | higher | last | 3\n'
            ),
        })
        wizard.action_capture()
        template = role.objective_template_ids
        self.assertEqual(len(template), 1)
        self.assertEqual(template.objective_type, 'aspirational')
        self.assertEqual(len(template.kr_line_ids), 2)
        self.assertEqual(template.company_id, self.env.company,
                         'captured knowledge is company-scoped, not shared')
        kpi = role.kpi_template_ids
        self.assertEqual(len(kpi), 1)
        self.assertEqual(kpi.aggregation, 'last')

    def test_capture_rejects_orphan_kr(self):
        role = self.env['aic.hrm.library.role'].create(
            {'name': 'Bad Role', 'code': 'BAD-ROLE'})
        wizard = self.env['aic.hrm.library.capture.wizard'].create({
            'role_id': role.id,
            'raw_text': 'KR: orphan | number | higher | 1 | x\n',
        })
        with self.assertRaises(UserError):
            wizard.action_capture()
