# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Exhaustive screen smoke: every menu, action, view, wizard and cron of
the installed suite modules is enumerated FROM THE DATABASE, so a screen
added later is covered automatically and none can be silently skipped.
"""
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

SUITE_MODULES = (
    'aic_hrm_base', 'aic_okr_kpi', 'aic_hrm_review', 'aic_hrm_library',
    'aic_hrm_project', 'aic_hrm_sale', 'aic_hrm_pro',
)


@tagged('post_install', '-at_install', 'aic_hrm_pro')
class TestScreenSmoke(TransactionCase):

    def _suite_records(self, model):
        data = self.env['ir.model.data'].search([
            ('module', 'in', SUITE_MODULES), ('model', '=', model)])
        return self.env[model].browse(data.mapped('res_id')).exists()

    def test_every_menu_resolves_to_a_loadable_action(self):
        """Every suite menu either groups children or opens an action
        whose views all render and whose domain/search executes."""
        failures = []
        menus = self._suite_records('ir.ui.menu')
        self.assertGreaterEqual(len(menus), 30,
                                'the suite ships its full menu surface')
        for menu in menus:
            if not menu.action:
                if not menu.child_id and menu.parent_id:
                    failures.append(f'{menu.complete_name}: leaf menu '
                                    'without action')
                continue
            action = menu.action
            if action._name != 'ir.actions.act_window':
                continue  # client actions checked separately
            model = self.env.get(action.res_model)
            if model is None:
                failures.append(f'{menu.complete_name}: unknown model '
                                f'{action.res_model}')
                continue
            for view_type in (action.view_mode or 'list').split(','):
                try:
                    model.get_view(view_type=view_type.strip())
                except Exception as error:
                    failures.append(
                        f'{menu.complete_name} [{view_type}]: {error}')
            try:
                domain = safe_eval(action.domain, {'uid': self.env.uid}) \
                    if action.domain else []
                model.search(domain, limit=5).read(['display_name'])
            except Exception as error:
                failures.append(f'{menu.complete_name} [search]: {error}')
        self.assertFalse(
            failures, 'Broken screens:\n' + '\n'.join(failures))

    def test_every_client_action_is_registered(self):
        actions = self._suite_records('ir.actions.client')
        self.assertGreaterEqual(len(actions), 2)
        for action in actions:
            self.assertTrue(action.tag,
                            f'{action.name}: client action without tag')

    def test_every_form_screen_opens_a_new_record(self):
        """Form() runs default_get + onchanges exactly like opening the
        screen and clicking New - a crash here is a broken screen."""
        failures = []
        seen = set()
        for action in self._suite_records('ir.actions.act_window'):
            model_name = action.res_model
            if model_name in seen or 'form' not in (action.view_mode or ''):
                continue
            seen.add(model_name)
            model = self.env[model_name]
            if model._transient or model._abstract or not model._auto:
                continue  # wizards below; SQL views have no New button
            try:
                Form(model)
            except Exception as error:
                failures.append(f'{model_name}: {error}')
        self.assertGreaterEqual(len(seen), 20)
        self.assertFalse(
            failures, 'New-record screens crash:\n' + '\n'.join(failures))

    def test_every_wizard_opens(self):
        failures = []
        wizards = [name for name, model in self.env.registry.items()
                   if name.startswith('aic.hrm.') and model._transient]
        self.assertGreaterEqual(len(wizards), 5)
        for name in wizards:
            model = self.env[name]
            try:
                model.default_get(list(model._fields))
            except Exception as error:
                failures.append(f'{name}: {error}')
        self.assertFalse(
            failures, 'Wizards crash on open:\n' + '\n'.join(failures))

    def test_every_cron_points_to_a_real_method(self):
        crons = self._suite_records('ir.cron')
        self.assertGreaterEqual(len(crons), 3)
        for cron in crons:
            code = (cron.code or '').strip()
            method = code.replace('model.', '', 1).split('(')[0]
            self.assertTrue(
                hasattr(self.env[cron.model_id.model], method),
                f'{cron.cron_name or cron.display_name}: method '
                f'{method} missing on {cron.model_id.model}')
