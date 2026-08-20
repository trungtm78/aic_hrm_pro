# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""What the engine costs at the scale it is sold for.

Tagged ``perf`` and excluded from ordinary runs, because building the pool takes
longer than the rest of the suite put together. Run it with::

    odoo-bin -c odoo.conf -d <db> -u aic_hrm_match \\
        --test-enable --test-tags perf --log-level=test --stop-after-init

The scale comes from ``AIC_HRM_MATCH_PERF_EMPLOYEES`` so the same file can be a
quick check on a laptop and the real two thousand in CI.

Two of the budgets are about wall-clock and one is not. The query count is the
one that catches the regression that matters: a criterion that reaches for
something it did not prefetch still returns the right answer, so nothing fails -
it just issues one query per candidate, and the ranking a planner used to wait
three seconds for now takes a minute.
"""
import os
import time

from odoo.tests import tagged

from .common import MatchCase

SCALE_EMPLOYEES = int(os.environ.get('AIC_HRM_MATCH_PERF_EMPLOYEES', '2000'))

RANK_BUDGET_S = 3.0
BATCH_BUDGET_S = 60.0
# Writing N candidates is N rows, and Odoo splits a large INSERT into chunks,
# so the total query count for a run cannot be independent of the pool. The
# ceiling below is generous on purpose: the invariants worth asserting are the
# per-phase ones below it, not this number.
MAX_QUERIES_PER_RANK = 200

# What genuinely must not grow *with the pool*. Prefetch reads each source once
# for everybody, so its cost is a handful of queries per source plus whatever
# chunking the ORM applies to a long IN list - a few dozen either way. Stated as
# a fraction of the pool rather than a fixed number, because the claim being
# made is "not per person", and a magic constant would have to be re-guessed
# every time the scale changes.
def max_prefetch_queries(pool_size):
    return max(50, pool_size // 10)


@tagged('post_install', '-at_install', 'perf')
class RankingPerformanceCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['aic.hrm.match.engine']
        cls.policy = cls.env.ref('aic_hrm_match.policy_default')

        # Created in one call rather than in a loop: at two thousand rows the
        # difference between one INSERT and two thousand is most of the setup.
        cls.employees = cls.env['hr.employee'].create([
            {'name': 'Perf Candidate %04d' % index,
             'company_id': cls.company.id}
            for index in range(SCALE_EMPLOYEES)
        ])

    def _request(self, name='Perf request'):
        request = self.env['aic.hrm.match.request'].create({
            'name': name,
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59',
        })
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Developer',
            'required_hours': 8.0})
        return request

    def test_ranking_the_whole_pool_stays_inside_the_time_budget(self):
        """Three seconds is the number the product is sold on. Past it a
        planner stops pressing the button and goes back to picking from
        memory, which is the problem this exists to solve."""
        request = self._request()
        started = time.monotonic()
        run = self.engine.run_match(request, policy=self.policy)
        elapsed = time.monotonic() - started

        self.assertEqual(run.state, 'computed')
        # At least the pool this test built: the database already had
        # employees of its own, and they are ranked too.
        self.assertGreaterEqual(len(run.candidate_ids), len(self.employees))
        self.assertLess(elapsed, RANK_BUDGET_S,
                        'ranking %d people took %.2fs'
                        % (SCALE_EMPLOYEES, elapsed))

    def test_the_query_count_does_not_grow_with_the_pool(self):
        """The regression this file exists for.

        A criterion that reaches for something it did not prefetch still
        returns the right answer, so no assertion fails - it simply issues a
        query per candidate. Counting is the only way that shows up before a
        customer notices.

        The context-manager form is the only correct one: passing the number as
        a keyword makes Odoo read it as a per-login expectation, and the test
        then passes or fails for reasons unrelated to the query count.
        """
        request = self._request()
        with self.assertQueryCount(__system__=MAX_QUERIES_PER_RANK):
            self.engine.run_match(request, policy=self.policy)

    def test_scoring_issues_no_queries_at_all(self):
        """The property the whole budget rests on.

        It cannot be observed from outside the engine: a scorer reaching for
        something it did not prefetch still returns the right answer, so no
        assertion fails - it simply issues a query per candidate, and the
        three-second ranking becomes a minute. Driving the phases separately is
        the only way to see it.
        """
        request = self._request()
        ctx = self.engine._build_context(request, request.slot_ids[0],
                                         self.policy)
        self.engine._prefetch(ctx)
        self.env.flush_all()

        before = self.env.cr.sql_log_count
        self.engine._score(ctx)
        self.env.flush_all()
        self.assertEqual(self.env.cr.sql_log_count, before,
                         'scoring issued a query; everything it needs must '
                         'come from the prefetch phase')

    def test_prefetching_does_not_get_more_expensive_with_the_pool(self):
        """Each source read once for everybody, rather than once per person.

        Bounded rather than fixed: the ORM splits a large IN list, so a few
        more queries at two thousand than at a hundred is chunking, not a
        source being asked per candidate.
        """
        request = self._request()
        ctx = self.engine._build_context(request, request.slot_ids[0],
                                         self.policy)
        self.env.flush_all()
        before = self.env.cr.sql_log_count
        self.engine._prefetch(ctx)
        self.env.flush_all()
        used = self.env.cr.sql_log_count - before

        self.assertLess(used, max_prefetch_queries(SCALE_EMPLOYEES),
                        'prefetching %d people took %d queries, which is close '
                        'enough to one per person to suspect a source is being '
                        'read individually' % (SCALE_EMPLOYEES, used))

    def test_a_batch_of_requests_stays_inside_the_batch_budget(self):
        """Fifty seats in one planning round is an ordinary Monday for a
        delivery team of this size."""
        started = time.monotonic()
        for index in range(50):
            request = self._request(name='Perf batch %02d' % index)
            run = self.engine.run_match(request, policy=self.policy)
            self.assertEqual(run.state, 'computed')
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, BATCH_BUDGET_S,
                        '50 rankings over %d people took %.1fs'
                        % (SCALE_EMPLOYEES, elapsed))

    def test_two_runs_of_the_same_request_agree(self):
        """Determinism at scale. Two runs over the same unchanged data have to
        produce the same order, or none of the explanations mean anything."""
        request = self._request()
        first = self.engine.run_match(request, policy=self.policy)
        second = self.engine.run_match(request, policy=self.policy)
        self.assertEqual(
            [c.employee_id.id
             for c in first.candidate_ids.filtered('eligible').sorted('rank')],
            [c.employee_id.id
             for c in second.candidate_ids.filtered('eligible').sorted('rank')])
