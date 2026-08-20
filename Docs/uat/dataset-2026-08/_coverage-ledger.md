# Coverage Ledger — UAT dataset & acceptance run (2026-08-20)

Every claim this run makes appears here as one row, with the evidence that
supports it and the layer that evidence lives at. Coverage is **counted from
this table**, never asserted in prose.

## Layer parity rule

Read each row out loud and ask who the subject is. If the subject is a
**person** — "a manager cannot see who rated them" — the evidence has to come
through HTTP or a browser. If the subject is a **function, table or
constraint** — "achievement clamps at the cap" — a unit case is the right
evidence and the sentence must say so.

The rule exists because of a failure worth remembering: a recovery-code
feature was covered 66/66 by unit cases that called the function directly,
while the only endpoint that could read those codes rejected them by schema.
The ledger said "usable when the phone is lost". Nobody could use one.

Two rows below are marked `layer: unit (narrowed)` for exactly this reason:
the claim was rewritten to name the function, because the browser evidence
does not exist yet.

| cov_id | Claim | Layer | Evidence | TC |
|---|---|---|---|---|
| COV-ENG-01 | Every catalogued fixture builds and returns its declared outputs | unit | `TestUatFixtures.test_every_fixture_applies` | TC-001 |
| COV-ENG-02 | A fixture id agrees with its own metadata | unit | `test_catalog_ids_match_their_metadata` | TC-002 |
| COV-ENG-03 | Re-applying a fixture does not duplicate it | unit | `test_apply_is_idempotent` | TC-003 |
| COV-ENG-04 | Cleanup restores the exact row counts of eleven models | unit | `test_cleanup_returns_the_database_to_where_it_started` | TC-004 |
| COV-ENG-05 | Cleanup cascades to dependants and no further | unit | `test_cleanup_cascades_to_dependents` | TC-005 |
| COV-ENG-06 | The dataset contains the awkward people, not only well-formed ones | unit | `test_org_chart_carries_the_awkward_people` | TC-023 |
| COV-SEC-01 | With UAT mode off, no fixture may write | unit (narrowed: the RPC refuses) | `test_uat_mode_off_blocks_everything` | TC-006 |
| COV-SEC-02 | A manager cannot drive the fixtures | unit (narrowed: the RPC refuses) | `test_non_admin_cannot_seed` | TC-007 |
| COV-GOV-01 | A locked cycle refuses every edit | unit | `test_locked_cycle_refuses_edits` | TC-008 |
| COV-SCORE-01 | Beating a lower-is-better target clamps at the cycle cap | unit | `test_lower_is_better_target_stays_positive` | TC-014 |
| COV-SCORE-02 | Overachievement clamps at 1.2 in a cap-1.2 cycle | unit | `test_overachievement_is_clamped_to_the_cycle_cap` | TC-015 |
| COV-SCORE-03 | An objective with no key results is not scored as zero | unit | `test_empty_objective_has_no_key_results` | TC-010 |
| COV-SCORE-04 | All five objective levels exist in one roll-up chain | unit | `test_full_objective_spans_all_five_levels` | TC-011 |
| COV-WGT-01 | A scorecard weighing 80 cannot be submitted, and the person is told the number | **e2e** | `test_underweight_scorecard_cannot_be_submitted` + `uat/specs/web/scorecard.spec.ts` | TC-016, TC-032 |
| COV-WGT-02 | Thirds (33.33+33.33+33.34) are accepted | unit | `test_three_thirds_are_accepted_despite_the_rounding` | TC-017 |
| COV-MON-01 | A key result untouched for 30 days reads as stale | unit | `test_stale_key_result_reads_as_stale` | TC-012 |
| COV-ANON-01 | Below the rater minimum, the aggregate is absent | unit + **e2e** | `test_below_threshold_hides_the_peer_aggregate`, `anonymity.spec.ts` | TC-018, TC-037 |
| COV-ANON-02 | At the minimum, the aggregate appears | unit | `test_third_answer_releases_the_aggregate` | TC-019 |
| COV-ANON-03 | Nobody may answer for a rater with no login | unit | `test_external_rater_cannot_be_spoken_for` | TC-020 |
| COV-ANON-04 | A manager reading a review sees no rater name on screen | **e2e** | `uat/specs/web/anonymity.spec.ts` | TC-036 |
| COV-CAL-01 | An applied calibration line cannot be edited or deleted | unit | `test_applied_calibration_line_is_immutable_and_undeletable` | TC-021 |
| COV-LIB-01 | An applied library pack produces draft objectives | unit | `test_library_pack_applies_as_draft_and_stamps_the_role` | TC-022 |
| COV-RPT-01 | The report contains exactly one row per measurement | **api** | `uat/specs/api/smoke.spec.ts` | TC-026 |
| COV-RPT-02 | Draft period results never reach the report | unit | `test_draft_period_results_stay_out_of_the_report` | TC-013 |
| COV-RPT-03 | Progress vs Plan renders as chart, pivot and list | **e2e** | `uat/specs/web/reporting.spec.ts` | TC-033 |
| COV-RPT-04 | A one-day cycle does not divide by zero | unit | `test_single_day_cycle_does_not_divide_by_zero` | TC-009 |
| COV-RPT-05 | The report groups by week, month, quarter, department, job and owner | **api** | `uat/specs/web/reporting.spec.ts` | TC-034 |
| COV-RPT-06 | The executive overview opens on a cycle that has data | **e2e** | `uat/specs/web/reporting.spec.ts` | TC-035 |
| COV-NAV-01 | The eight stages of the operating loop are in the menu bar | **e2e** | `uat/specs/web/menu.spec.ts` | TC-028 |
| COV-NAV-02 | The five wizards sit in their stage, not in Configuration | **e2e** | `uat/specs/web/menu.spec.ts` | TC-029 |
| COV-NAV-03 | Period results are reachable from the menu | **e2e** | `uat/specs/web/menu.spec.ts` | TC-030 |
| COV-NAV-04 | All 24 screens open with an empty browser console | **e2e** | `uat/specs/web/menu.spec.ts` | TC-031 |
| COV-ENV-01 | The run is scored against the UAT database, not the customer's | **api** | `uat/specs/api/smoke.spec.ts` + dbfilter in odoo.uat.conf | TC-024 |
| COV-ENV-02 | All three personas authenticate | **api** | `uat/specs/api/smoke.spec.ts` | TC-025 |
| COV-ENV-03 | All fourteen core models answer a read | **api** | `uat/specs/api/smoke.spec.ts` | TC-027 |
| COV-UX-01 | The refusal message names both the actual and the required weight | **e2e** | `uat/specs/web/scorecard.spec.ts` | TC-032 |
| COV-UX-02 | The dashboard shows figures, not the empty state, on a seeded database | **e2e** | `uat/specs/web/reporting.spec.ts` | TC-035 |
| COV-MOB-01..06 | Six screens fit a 320px viewport with no sideways scroll | **e2e** | `uat/specs/web/responsive.spec.ts` | TC-038..TC-043 |
| COV-MOB-07 | No control in our own components is under 44px high | **e2e** | `uat/specs/web/responsive.spec.ts` | TC-044 |
| COV-PERF-01 | Closing a cycle at 2,000 employees stays under 60s | **api** | `tools/seed_uat_scale.py` — measured 0.02s | TC-045 |
| COV-PERF-02 | Grouping the report by department stays under 3s | **api** | `tools/seed_uat_scale.py` — measured 0.10s (0.90s cold) | TC-046 |
| COV-PERF-03 | Recomputing every scorecard stays under 60s | **api** | `tools/seed_uat_scale.py` — measured 2.73s | TC-047 |

**47 coverage items, 47 with evidence, 0 orphan test cases.**
Layers: 24 unit · 6 api · 17 e2e (of which 7 at 320px).

## Gaps, declared

| Gap | Why it is a gap, not an omission |
|---|---|
| `COV-SEC-01/02` are unit-level | The claims are written narrowly — "the RPC refuses" — because there is no UI for seeding and never will be. A wider claim about a person would need evidence that cannot exist. |
| Import journey not driven through the browser | The spreadsheet import is covered by `test_actuals_import.py` and `test_import_rollover.py` at unit level with real files. Driving a file upload through Playwright would add a fragile step and no new oracle. Recorded as a gap rather than claimed. |
| Cockpit and Alignment Tree have no data assertions | They open, render and log no console error (COV-NAV-04). What their numbers should be is asserted at model level. A visual claim about them would need a person. |
| Odoo 18 backport unverified for this change | The report-overview default-cycle fix lands on 19.0 only in this pass; the 18.0 branch carries its own copy. Tracked in PROGRESS. |
| `last_checkin_date` staleness | Known defect, reported and deliberately unfixed. No fixture claims correct behaviour for it. |

## Fault seeding — does the set actually catch anything?

Four faults were introduced into the product on purpose, each a defect this
codebase either had or could regress into, then reverted. A green suite that
survives a seeded fault is a weak suite, and this is how you find out.

| Fault | Caught by |
|---|---|
| F1 `clamp` loses its upper bound | `test_overachievement_is_clamped_to_the_cycle_cap`, `test_lower_is_better_target_stays_positive` |
| F2 scorecard weight gate always open | `test_underweight_scorecard_cannot_be_submitted` |
| F3 authorisation skipped for a rater with no login (the /cso hole, restored) | `test_external_rater_cannot_be_spoken_for` |
| F4 applied calibration line becomes deletable | `test_applied_calibration_line_is_immutable_and_undeletable` |

**4 seeded, 4 caught.**

The first run of this experiment reported two of them as SURVIVED, and that
was the experiment's fault, not the product's: it updated the module carrying
the fault, and Odoo only runs the tests of modules it is updating, so the UAT
cases never executed. It also scored "caught" by grepping the log for the word
*failed*, which appears in warnings. Both are fixed - the runner now updates
the fixture module and parses Odoo's own tally.
