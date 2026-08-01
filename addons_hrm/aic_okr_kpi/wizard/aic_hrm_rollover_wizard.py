# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, _
from odoo.exceptions import UserError


class AicHrmRolloverWizard(models.TransientModel):
    """Clone a cycle's goal structure into a new cycle.

    Structure and targets carry over (still editable in draft); every
    actual — current values, check-ins, period results, states — resets.
    Alignment links are remapped inside the copied set.
    """
    _name = 'aic.hrm.rollover.wizard'
    _description = 'Cycle Rollover'

    source_cycle_id = fields.Many2one('aic.hrm.cycle', required=True)
    target_cycle_id = fields.Many2one('aic.hrm.cycle', required=True)
    copy_objectives = fields.Boolean(default=True)
    copy_kpi_targets = fields.Boolean(default=True)
    copy_assignments = fields.Boolean(default=True)

    def action_rollover(self):
        self.ensure_one()
        if self.source_cycle_id == self.target_cycle_id:
            raise UserError(_(
                "Source and target cycles must differ."))
        self.target_cycle_id.ensure_editable()
        objective_map = {}
        if self.copy_objectives:
            objectives = self.env['aic.hrm.objective'].search(
                [('cycle_id', '=', self.source_cycle_id.id)])
            existing_codes = set(self.env['aic.hrm.objective'].search(
                [('cycle_id', '=', self.target_cycle_id.id)])
                .mapped('code'))
            for objective in objectives:
                if objective.code in existing_codes:
                    # Re-running the wizard must not duplicate structure.
                    continue
                objective_map[objective.id] = objective.copy({
                    'cycle_id': self.target_cycle_id.id,
                    'code': objective.code,
                    'parent_id': False,
                    'contributes_to_ids': [(5, 0, 0)],
                })
            for objective in objectives:
                new_objective = objective_map[objective.id]
                if objective.parent_id and \
                        objective.parent_id.id in objective_map:
                    new_objective.parent_id = objective_map[
                        objective.parent_id.id]
                contributions = [
                    objective_map[target.id].id
                    for target in objective.contributes_to_ids
                    if target.id in objective_map]
                if contributions:
                    new_objective.contributes_to_ids = [
                        (6, 0, contributions)]
                for kr in objective.kr_ids:
                    kr.copy({
                        'objective_id': new_objective.id,
                        'code': kr.code,
                        'current': 0.0,
                        'last_checkin_date': False,
                    })

        target_map = {}
        if self.copy_kpi_targets:
            kpi_targets = self.env['aic.hrm.kpi.target'].search(
                [('cycle_id', '=', self.source_cycle_id.id)])
            existing_targets = {
                (target.kpi_id.id, target.employee_id.id)
                for target in self.env['aic.hrm.kpi.target'].search(
                    [('cycle_id', '=', self.target_cycle_id.id)])}
            for kpi_target in kpi_targets:
                key = (kpi_target.kpi_id.id, kpi_target.employee_id.id)
                if key in existing_targets:
                    continue
                target_map[kpi_target.id] = kpi_target.copy({
                    'cycle_id': self.target_cycle_id.id,
                    'state': 'draft',
                    'objective_id': objective_map.get(
                        kpi_target.objective_id.id,
                        self.env['aic.hrm.objective']).id or False,
                })

        if self.copy_assignments and self.copy_kpi_targets:
            assignments = self.env['aic.hrm.kpi.assignment'].search(
                [('cycle_id', '=', self.source_cycle_id.id)])
            existing_owners = set(self.env['aic.hrm.kpi.assignment'].search(
                [('cycle_id', '=', self.target_cycle_id.id)])
                .mapped('employee_id').ids)
            for assignment in assignments:
                if assignment.employee_id.id in existing_owners:
                    continue
                new_assignment = assignment.copy({
                    'cycle_id': self.target_cycle_id.id,
                    'state': 'draft',
                    'line_ids': [(5, 0, 0)],
                })
                for line in assignment.line_ids:
                    new_target = target_map.get(line.kpi_target_id.id)
                    if new_target:
                        line.copy({
                            'assignment_id': new_assignment.id,
                            'kpi_target_id': new_target.id,
                        })
        return {'type': 'ir.actions.act_window_close'}
