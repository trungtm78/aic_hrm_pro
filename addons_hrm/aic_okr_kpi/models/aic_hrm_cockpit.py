# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""What the leadership desk reads for one cycle.

Objectives and scorecards rarely live on the same cycle: a company sets
objectives per quarter and assigns KPIs per month, and a year holds neither
directly. Reading only the selected cycle left every cycle but one empty on
the customer's desk. The cycle is therefore read through its tree, and the
answer names the cycles it came from so the reader never has to guess.

Record rules apply: the desk shows what the reader may see, nothing more.
"""
from odoo import models

_OBJECTIVE_FIELDS = [
    'id', 'code', 'name', 'department_id', 'objective_type', 'score',
    'score_covered', 'data_coverage', 'weight', 'rag', 'state', 'cycle_id',
]
_KR_FIELDS = ['id', 'is_stale', 'rag', 'has_actual', 'last_checkin_date']
_RISK_FIELDS = ['id', 'code', 'name', 'employee_id', 'rag', 'is_stale',
                'progress', 'cycle_id']
_RISK_LIMIT = 10
_WEAKEST_LIMIT = 5


class AicHrmCycle(models.Model):
    _inherit = 'aic.hrm.cycle'

    def _cockpit_descendants(self):
        """This cycle and every cycle inside it."""
        self.ensure_one()
        return self.search([('id', 'child_of', self.id)])

    def _cockpit_gather(self, model_name, borrow_upwards=True):
        """Pick the cycles whose records of `model_name` add up into this one.

        Records belong to the period they were made in, so the periods
        inside a cycle belong to it and add up: a quarter is its own rows
        plus its months, a year is everything under it. Nothing is ever
        borrowed downwards - a quarterly figure is not a June figure.

        With nothing anywhere inside it, a cycle names the nearest cycle
        above that has records, so an empty month still shows the scorecards
        it works towards. `borrow_upwards=False` switches that off, for a
        reading that is about a period rather than about a commitment: a
        month with no measurements has no measurements, and showing the
        quarter's instead would date them to the wrong month.

        Returns (source, cycles) in calendar order, where source is one of
        own / children / parent / none.
        """
        self.ensure_one()
        Model = self.env[model_name]
        groups = Model._read_group(
            [('cycle_id', 'in', self._cockpit_descendants().ids)],
            ['cycle_id'], ['__count'])
        cycles = self.browse([cycle.id for cycle, _count in groups])
        if cycles:
            source = 'own' if cycles == self else 'children'
        else:
            source = 'none'
            for ancestor in (self._lineage() - self) if borrow_upwards else self.browse():
                if Model.search_count([('cycle_id', '=', ancestor.id)], limit=1):
                    source, cycles = 'parent', ancestor
                    break
        return source, cycles.sorted(lambda c: (c.date_start, c.id))

    def _cockpit_resolve(self, model_name):
        """Pick the cycles whose records of `model_name` speak for this one.

        Own records win; else the cycles inside it (a year gathers its
        quarters); else the nearest cycle above it that has any (a month
        works towards its quarter). Returns (source, cycles).
        """
        self.ensure_one()
        Model = self.env[model_name]
        if Model.search_count([('cycle_id', '=', self.id)], limit=1):
            return 'own', self
        inside = self._cockpit_descendants() - self
        if inside:
            groups = Model._read_group(
                [('cycle_id', 'in', inside.ids)], ['cycle_id'], ['__count'])
            cycles = self.browse([cycle.id for cycle, _count in groups])
            if cycles:
                return 'children', cycles.sorted(lambda c: (c.date_start, c.id))
        for ancestor in self._lineage() - self:
            if Model.search_count([('cycle_id', '=', ancestor.id)], limit=1):
                return 'parent', ancestor
        return 'none', self.browse()

    @staticmethod
    def _cockpit_cycle_refs(cycles):
        return [{'id': cycle.id, 'name': cycle.name} for cycle in cycles]

    def _cockpit_okr(self):
        source, cycles = self._cockpit_resolve('aic.hrm.objective')
        domain = [('cycle_id', 'in', cycles.ids)]
        KeyResult = self.env['aic.hrm.key.result']
        return {
            'source': source,
            'cycles': self._cockpit_cycle_refs(cycles),
            'objectives': self.env['aic.hrm.objective'].search_read(
                domain, _OBJECTIVE_FIELDS),
            'key_results': KeyResult.search_read(domain, _KR_FIELDS),
            # Red first, then stale; an unscored key result is neither.
            'risks': sorted(
                KeyResult.search_read(
                    domain + ['|', ('rag', '=', 'red'), ('is_stale', '=', True)],
                    _RISK_FIELDS, order='progress asc, id', limit=_RISK_LIMIT),
                key=lambda kr: kr['rag'] != 'red'),
        }

    def _cockpit_kpi(self):
        Scorecard = self.env['aic.hrm.kpi.assignment']
        # Scorecards add up across the tree, the same way measurements do.
        source, cycles = self._cockpit_gather('aic.hrm.kpi.assignment')
        domain = [('cycle_id', 'in', cycles.ids)]

        # "Measured" is a scorecard with at least one confirmed figure: the
        # score on measured KPIs, read together with the coverage, is the
        # honest pair. An unmeasured scorecard scores 0 and would drag every
        # average down while meaning only "nobody has reported yet".
        measured = domain + [('data_coverage', '>', 0)]
        [(count, coverage)] = Scorecard._read_group(
            domain, [], ['__count', 'data_coverage:avg'])
        [(measured_count, score_covered)] = Scorecard._read_group(
            measured, [], ['__count', 'score_covered:avg'])

        def breakdown(groupby):
            totals = {key: (n, cov) for key, n, cov in Scorecard._read_group(
                domain, [groupby], ['__count', 'data_coverage:avg'])}
            scored = {key: (n, score) for key, n, score in Scorecard._read_group(
                measured, [groupby], ['__count', 'score_covered:avg'])}
            rows = []
            for key, (n, cov) in totals.items():
                n_measured, score = scored.get(key, (0, 0.0))
                rows.append({
                    f'{groupby}': key.id or False,
                    'name': key.display_name if key else False,
                    'count': n,
                    'measured_count': n_measured,
                    'coverage': cov or 0.0,
                    'score_covered': score or 0.0,
                })
            return rows

        by_cycle = breakdown('cycle_id')
        order = {cycle.id: index for index, cycle in enumerate(cycles)}
        by_cycle.sort(key=lambda row: order.get(row['cycle_id'], len(order)))
        by_department = breakdown('department_id')
        # Weakest measured department first; a department with no figures
        # yet goes last, since it cannot be ranked.
        by_department.sort(key=lambda row: (not row['measured_count'],
                                            row['score_covered'],
                                            row['name'] or ''))

        weakest = Scorecard.search_read(
            measured, ['id', 'employee_id', 'department_id', 'cycle_id',
                       'score_covered', 'data_coverage', 'rag'],
            order='score_covered asc, id', limit=_WEAKEST_LIMIT)
        return {
            'source': source,
            'cycles': self._cockpit_cycle_refs(cycles),
            'scorecard_count': count,
            'measured_count': measured_count,
            'unmeasured_count': count - measured_count,
            'red_count': Scorecard.search_count(measured + [('rag', '=', 'red')]),
            'coverage': coverage or 0.0,
            'score_covered': score_covered or 0.0,
            'by_cycle': by_cycle,
            'by_department': by_department,
            'weakest': weakest,
        }

    def cockpit_data(self):
        """Everything the leadership desk shows for this cycle, in one call."""
        self.ensure_one()
        return {
            'cycle': {'id': self.id, 'name': self.name,
                      'cycle_type': self.cycle_type},
            'okr': self._cockpit_okr(),
            'kpi': self._cockpit_kpi(),
        }
