# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
import base64
import io
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

OKR_SHEET = 'OKR_2026'
KPI_SHEET = 'KPI_CHI_TIET'
ASSIGN_SHEET = 'PHAN_CONG'


class AicHrmImportWizard(models.TransientModel):
    """Three-sheet OKR/KPI/assignment spreadsheet importer.

    Preview first (structure summary + warnings), then an idempotent import:
    records are matched by code inside the chosen cycle, so re-running the
    same file updates instead of duplicating.
    """
    _name = 'aic.hrm.import.wizard'
    _description = 'OKR/KPI Excel Import'

    cycle_id = fields.Many2one('aic.hrm.cycle', required=True)
    department_id = fields.Many2one(
        'hr.department',
        help="Department the imported objectives belong to. Empty = "
             "company-level objectives.")
    file = fields.Binary(required=True)
    filename = fields.Char()
    create_missing_employees = fields.Boolean(
        default=False,
        help="Create hr.employee records (flagged for HR completion) for "
             "names the matcher cannot find. Off by default: unmatched "
             "rows are skipped with a warning.")
    state = fields.Selection([
        ('upload', 'Upload'),
        ('preview', 'Preview'),
        ('error', 'Error'),
        ('done', 'Done'),
    ], default='upload')
    preview = fields.Html(readonly=True)
    warning_log = fields.Text(readonly=True)
    error_log = fields.Text(readonly=True)
    created_objective_count = fields.Integer(readonly=True)
    created_kpi_count = fields.Integer(readonly=True)
    created_assignment_count = fields.Integer(readonly=True)

    # ---- parsing ----

    def _load_workbook(self):
        try:
            import openpyxl
        except ImportError as error:
            raise UserError(_(
                "The Python library 'openpyxl' is required to read Excel "
                "files. Ask your administrator to install it "
                "(pip install openpyxl).")) from error
        data = base64.b64decode(self.file)
        return openpyxl.load_workbook(
            io.BytesIO(data), data_only=True, read_only=True)

    @staticmethod
    def _rows(sheet):
        rows = sheet.iter_rows(min_row=2, values_only=True)
        return [row for row in rows if any(
            cell not in (None, '') for cell in row)]

    def _parse(self):
        """Return (okr_rows, kpi_rows, assign_rows, warnings)."""
        workbook = self._load_workbook()
        warnings = []
        missing = [name for name in (OKR_SHEET, KPI_SHEET, ASSIGN_SHEET)
                   if name not in workbook.sheetnames]
        if missing:
            raise UserError(_(
                "Missing sheet(s): %(sheets)s. Expected %(expected)s.",
                sheets=', '.join(missing),
                expected=', '.join((OKR_SHEET, KPI_SHEET, ASSIGN_SHEET))))

        okr_rows = []
        current = {}
        for row in self._rows(workbook[OKR_SHEET]):
            code, name, weight, kr_code, kr_name, measure, target, unit, \
                owner, quarters, priority, note = (list(row) + [None] * 12)[:12]
            if code:
                current = {'code': str(code).strip(),
                           'name': str(name or '').strip(),
                           'weight': float(weight or 0.0)}
            if not current or not kr_code:
                continue
            okr_rows.append({
                'objective': dict(current),
                'kr_code': str(kr_code).strip(),
                'kr_name': str(kr_name or '').strip(),
                'measure': str(measure or '').strip(),
                'target': float(target or 0.0),
                'unit': str(unit or '').strip(),
                'owner': str(owner or '').strip(),
                'quarters': str(quarters or '').strip(),
                'priority': str(priority or '').strip(),
                'note': str(note or '').strip(),
            })

        kpi_rows = []
        for row in self._rows(workbook[KPI_SHEET]):
            kpi_id, group, objective_code, name, direction, aggregation, \
                unit, weight, target, owner, source, note = (
                    list(row) + [None] * 12)[:12]
            if not kpi_id:
                continue
            kpi_rows.append({
                'code': str(kpi_id).strip(),
                'group': str(group or '').strip(),
                'objective_code': str(objective_code or '').strip(),
                'name': str(name or '').strip(),
                'direction': str(direction or '').strip(),
                'aggregation': str(aggregation or '').strip(),
                'unit': str(unit or '').strip(),
                'weight': float(weight or 0.0),
                'target': float(target or 0.0),
                'owner': str(owner or '').strip(),
                'source': str(source or '').strip(),
                'note': str(note or '').strip(),
            })

        assign_rows = []
        for row in self._rows(workbook[ASSIGN_SHEET]):
            _tt, person, position, responsibility, _objectives, kpi_codes, \
                total = (list(row) + [None] * 7)[:7]
            if not person:
                continue
            codes = [code.strip() for code in
                     str(kpi_codes or '').split(',') if code.strip()]
            # A planning sheet often names several people on one row when
            # they share a set of KPIs. Read as one cell that produced an
            # employee called "Ha, Trung, Tan" - a person who does not
            # exist, holding a scorecard nobody owns. Each name gets its
            # own row, carrying the same KPIs.
            for name in self._split_people(str(person)):
                assign_rows.append({
                    'person': name,
                    'position': str(position or '').strip(),
                    'responsibility': str(responsibility or '').strip(),
                    'kpi_codes': list(codes),
                    'total': float(total or 0.0),
                })
        return okr_rows, kpi_rows, assign_rows, warnings

    @staticmethod
    def _normalise_scorecard(assignment, row, warnings):
        """Scale a personal scorecard so its weights total 100.

        The imported weights come from the KPI's share of the DEPARTMENT
        plan, which sums to 100 across every KPI in the sheet - so one
        person's slice landed anywhere from 7 to 20. A scorecard cannot
        be submitted unless its own lines total 100, which meant every
        imported scorecard was stuck in draft: the import produced data
        the product itself refuses.

        Relative proportions are what the planner expressed, so they are
        preserved and only the scale changes.
        """
        lines = assignment.line_ids
        if not lines:
            return
        total = sum(lines.mapped('weight'))
        if not total:
            share = round(100.0 / len(lines), 2)
            for line in lines:
                line.weight = share
        else:
            for line in lines:
                line.weight = round(line.weight * 100.0 / total, 2)
        # Rounding leaves a few hundredths; the last line absorbs them so
        # the gate sees exactly 100.
        drift = round(100.0 - sum(lines.mapped('weight')), 2)
        if drift:
            lines[-1].weight = round(lines[-1].weight + drift, 2)
        stated = row.get('total') or 0.0
        if stated and abs(stated - 100.0) > 0.01:
            warnings.append(_(
                "%(person)s's row states a total of %(stated)s; scorecard "
                "weights were scaled to 100 so it can be submitted.",
                person=row['person'], stated=stated))

    @staticmethod
    def _split_people(cell):
        """Split a cell that names more than one person.

        Separators are the ones planning sheets actually use. A slash is
        deliberately not one of them: it appears inside role titles more
        often than between names.
        """
        text = cell.replace('\n', ',').replace(';', ',').replace('&', ',')
        return [part.strip() for part in text.split(',') if part.strip()]

    def _match_employee(self, name, warnings, allow_create=False):
        """Find an employee by name. Creation (when enabled) happens only
        on the import pass — previewing must stay side-effect free."""
        if not name:
            return self.env['hr.employee']
        employee = self.env['hr.employee'].search(
            [('name', '=ilike', name)], limit=1)
        if not employee:
            warnings.append(_(
                "Employee '%(name)s' not found — row imported without "
                "owner or skipped.", name=name))
            if allow_create and self.create_missing_employees:
                employee = self.env['hr.employee'].create({
                    'name': name,
                    'company_id': self.cycle_id.company_id.id,
                    'active': True,
                })
        return employee

    # ---- actions ----

    def action_preview(self):
        self.ensure_one()
        try:
            okr_rows, kpi_rows, assign_rows, warnings = self._parse()
        except Exception as error:
            self.write({'state': 'error', 'error_log': str(error)})
            return self._reopen()
        for row in okr_rows:
            self._match_employee(row['owner'].split(',')[0], warnings)
        for row in assign_rows:
            self._match_employee(row['person'].split(',')[0], warnings)
        objective_codes = sorted({row['objective']['code']
                                  for row in okr_rows})
        lines = [
            _("Objectives: %(codes)s", codes=', '.join(objective_codes)),
            _("Key results: %(count)s rows", count=len(okr_rows)),
            _("KPIs: %(codes)s",
              codes=', '.join(row['code'] for row in kpi_rows)),
            _("Assignments: %(count)s people", count=len(assign_rows)),
        ]
        self.write({
            'state': 'preview',
            'preview': '<br/>'.join(lines),
            'warning_log': '\n'.join(warnings) or False,
        })
        return self._reopen()

    def action_import(self):
        self.ensure_one()
        if self.state != 'preview':
            raise UserError(_("Run the preview first."))
        okr_rows, kpi_rows, assign_rows, warnings = self._parse()
        Term = self.env['aic.hrm.import.term']
        direction_map = Term.get_map('direction')
        aggregation_map = Term.get_map('aggregation')
        priority_map = Term.get_map('priority')
        Objective = self.env['aic.hrm.objective']
        KeyResult = self.env['aic.hrm.key.result']
        Kpi = self.env['aic.hrm.kpi']
        KpiTarget = self.env['aic.hrm.kpi.target']
        Assignment = self.env['aic.hrm.kpi.assignment']

        objectives = {}
        created_objectives = 0
        for row in okr_rows:
            spec = row['objective']
            objective = objectives.get(spec['code'])
            if objective is None:
                objective = Objective.search([
                    ('cycle_id', '=', self.cycle_id.id),
                    ('code', '=', spec['code'])], limit=1)
                if not objective:
                    objective = Objective.create({
                        'code': spec['code'],
                        'name': spec['name'] or spec['code'],
                        'cycle_id': self.cycle_id.id,
                        'level': ('department' if self.department_id
                                  else 'company'),
                        'department_id': self.department_id.id or False,
                        'weight': spec['weight'],
                    })
                    created_objectives += 1
                objectives[spec['code']] = objective
            owner = self._match_employee(
                row['owner'].split(',')[0], warnings, allow_create=True)
            kr = KeyResult.search([
                ('objective_id', '=', objective.id),
                ('code', '=', row['kr_code'])], limit=1)
            kr_vals = {
                'name': row['kr_name'] or row['kr_code'],
                'target': row['target'],
                'unit': row['unit'],
                'employee_id': owner.id or False,
                'focus_quarters': row['quarters'],
                'priority': priority_map.get(
                    row['priority'].lower(), 'medium'),
                'note': row['note'],
            }
            if kr:
                kr.write(kr_vals)
            else:
                KeyResult.create({
                    **kr_vals,
                    'code': row['kr_code'],
                    'objective_id': objective.id,
                    'metric_type': 'number',
                    'baseline': 0.0,
                })

        kpi_targets = {}
        created_kpis = 0
        for row in kpi_rows:
            direction = direction_map.get(row['direction'].lower(), 'higher')
            aggregation = aggregation_map.get(
                row['aggregation'].lower(), 'last')
            kpi = Kpi.search([('code', '=', row['code'])], limit=1)
            kpi_vals = {
                'name': row['name'] or row['code'],
                'direction': direction,
                'aggregation': aggregation,
                'unit': row['unit'],
                'data_source': row['source'],
                'note': row['note'],
                'default_target': row['target'],
            }
            if kpi:
                kpi.write(kpi_vals)
            else:
                kpi = Kpi.create({**kpi_vals, 'code': row['code']})
                created_kpis += 1
            owner = self._match_employee(
                row['owner'].split(',')[0], warnings, allow_create=True)
            target = KpiTarget.search([
                ('kpi_id', '=', kpi.id),
                ('cycle_id', '=', self.cycle_id.id),
                ('employee_id', '=', owner.id or False)], limit=1)
            objective = objectives.get(row['objective_code']) or \
                Objective.search([
                    ('cycle_id', '=', self.cycle_id.id),
                    ('code', '=', row['objective_code'])], limit=1)
            target_vals = {
                'weight': row['weight'],
                'target_value': row['target'],
                'objective_id': objective.id if objective else False,
            }
            if target:
                target.write(target_vals)
            else:
                target = KpiTarget.create({
                    **target_vals,
                    'kpi_id': kpi.id,
                    'cycle_id': self.cycle_id.id,
                    'employee_id': owner.id or False,
                })
            kpi_targets[(row['code'], owner.id or False)] = target
            kpi_targets.setdefault(row['code'], target)

        created_assignments = 0
        for row in assign_rows:
            employee = self._match_employee(
                row['person'], warnings, allow_create=True)
            if not employee:
                continue
            assignment = Assignment.search([
                ('cycle_id', '=', self.cycle_id.id),
                ('employee_id', '=', employee.id)], limit=1)
            if not assignment:
                assignment = Assignment.create({
                    'cycle_id': self.cycle_id.id,
                    'employee_id': employee.id,
                    'job_note': row['position'],
                    'responsibility': row['responsibility'],
                })
                created_assignments += 1
            for code in row['kpi_codes']:
                target = kpi_targets.get((code, employee.id))
                if not target:
                    # Never fall back to another owner's target: clone the
                    # KPI's cycle setup for THIS employee instead.
                    reference = kpi_targets.get(code)
                    if not reference:
                        warnings.append(_(
                            "KPI %(code)s on %(person)s's row is not in "
                            "the KPI sheet — line skipped.",
                            code=code, person=row['person']))
                        continue
                    target = KpiTarget.create({
                        'kpi_id': reference.kpi_id.id,
                        'cycle_id': self.cycle_id.id,
                        'employee_id': employee.id,
                        'weight': reference.weight,
                        'target_value': reference.target_value,
                        'objective_id': reference.objective_id.id or False,
                    })
                    kpi_targets[(code, employee.id)] = target
                line = assignment.line_ids.filtered(
                    lambda l: l.kpi_target_id == target)
                if not line:
                    assignment.line_ids.create({
                        'assignment_id': assignment.id,
                        'kpi_target_id': target.id,
                        'weight': target.weight or 1.0,
                    })
            self._normalise_scorecard(assignment, row, warnings)
        self.write({
            'state': 'done',
            'warning_log': '\n'.join(warnings) or False,
            'created_objective_count': created_objectives,
            'created_kpi_count': created_kpis,
            'created_assignment_count': created_assignments,
        })
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
