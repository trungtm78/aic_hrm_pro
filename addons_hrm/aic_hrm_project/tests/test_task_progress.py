# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'aic_hrm_project')
class TestTaskProgress(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.cycle = env['aic.hrm.cycle'].create({
            'name': 'Project FY', 'code': 'PRJ-FY', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31'})
        cls.objective = env['aic.hrm.objective'].create({
            'name': 'Ship the platform', 'cycle_id': cls.cycle.id,
            'weight': 100})
        cls.project = env['project.project'].create({'name': 'Platform'})
        cls.tasks = env['project.task'].create([
            {'name': f'Task {index}', 'project_id': cls.project.id}
            for index in range(4)])

    def _make_kr(self, **kw):
        vals = {
            'name': 'Delivery KR', 'objective_id': self.objective.id,
            'baseline': 0.0, 'target': 4.0,
        }
        vals.update(kw)
        return self.env['aic.hrm.key.result'].create(vals)

    def test_task_links_to_kr(self):
        kr = self._make_kr()
        self.tasks.write({'aic_kr_id': kr.id})
        self.assertEqual(kr.task_count, 4)

    def test_count_done_mode_syncs_current(self):
        kr = self._make_kr(task_progress_mode='count_done', target=4.0)
        self.tasks.write({'aic_kr_id': kr.id})
        self.assertAlmostEqual(kr.current, 0.0)
        self.tasks[0].write({'state': '1_done'})
        self.assertAlmostEqual(kr.current, 1.0)
        self.assertAlmostEqual(kr.progress, 0.25)
        self.tasks[1].write({'state': '1_done'})
        self.assertAlmostEqual(kr.current, 2.0)
        self.assertAlmostEqual(kr.progress, 0.5)

    def test_percent_done_mode(self):
        kr = self._make_kr(
            task_progress_mode='percent_done', metric_type='percent',
            target=100.0)
        self.tasks.write({'aic_kr_id': kr.id})
        self.tasks[0].write({'state': '1_done'})
        self.tasks[1].write({'state': '1_done'})
        self.tasks[2].write({'state': '1_done'})
        self.assertAlmostEqual(kr.current, 75.0)
        self.assertAlmostEqual(kr.progress, 0.75)

    def test_cancelled_tasks_do_not_count(self):
        kr = self._make_kr(task_progress_mode='percent_done',
                           metric_type='percent', target=100.0)
        self.tasks.write({'aic_kr_id': kr.id})
        self.tasks[0].write({'state': '1_done'})
        self.tasks[1].write({'state': '1_canceled'})
        # cancelled tasks leave the denominator: 1 done of 3 live tasks
        self.assertAlmostEqual(kr.current, 100.0 / 3, places=2)

    def test_manual_mode_untouched(self):
        kr = self._make_kr(current=2.5)
        self.tasks.write({'aic_kr_id': kr.id})
        self.tasks[0].write({'state': '1_done'})
        self.assertAlmostEqual(kr.current, 2.5,
                               msg='mode off: task changes never overwrite '
                                   'manual figures')

    def test_unlinking_task_resyncs(self):
        kr = self._make_kr(task_progress_mode='count_done', target=4.0)
        self.tasks.write({'aic_kr_id': kr.id})
        self.tasks[0].write({'state': '1_done'})
        self.assertAlmostEqual(kr.current, 1.0)
        self.tasks[0].write({'aic_kr_id': False})
        self.assertAlmostEqual(kr.current, 0.0)

    def test_project_task_allowlisted_for_metric_sources(self):
        allowed = self.env['aic.hrm.metric.allowed.model'].search(
            [('model_name', '=', 'project.task')])
        self.assertTrue(allowed, 'bridge seeds the metric-source allowlist')

    def test_cron_safety_net(self):
        kr = self._make_kr(task_progress_mode='count_done', target=4.0)
        self.tasks.write({'aic_kr_id': kr.id})
        self.env.cr.execute(
            "UPDATE project_task SET state = '1_done' WHERE id = %s",
            (self.tasks[0].id,))
        # the stale cache after a raw-SQL change sits on the TASK model
        self.env['project.task'].invalidate_model(['state'])
        self.env['aic.hrm.key.result']._cron_sync_task_progress()
        self.assertAlmostEqual(kr.current, 1.0)
