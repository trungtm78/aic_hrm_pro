/** @odoo-module **/
// Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Executive overview — the reading of the progress report a leader wants
 * without touching a pivot: where the cycle stands month by month against
 * plan, which departments are furthest behind, and which goals are
 * dragging.
 *
 * Every number comes from aic.hrm.progress.report through read_group, so
 * this page and the pivot beside it can never disagree: one query source,
 * one definition of "behind plan".
 */
export class AicHrmReportOverview extends Component {
    static template = "aic_okr_kpi.ReportOverview";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            cycles: [],
            cycleId: false,
            months: [],
            scope: null,
            departments: [],
            laggards: [],
            summary: null,
            loading: true,
        });
        onWillStart(async () => {
            this.state.cycles = await this.orm.searchRead(
                "aic.hrm.cycle",
                [["state", "in", ["open", "review", "closed"]]],
                ["id", "name"],
                { order: "date_start desc" },
            );
            if (this.state.cycles.length) {
                this.state.cycleId = await this.defaultCycleId();
                await this.load();
            }
            this.state.loading = false;
        });
    }

    /**
     * Open on a cycle that has something in it.
     *
     * Picking the newest cycle by start date looks right and fails in the
     * commonest situation there is: somebody creates next period's cycle
     * ahead of time, and from that moment the leadership dashboard greets
     * everyone with "nothing measured yet" while the current period is full
     * of data. Prefer the most recent cycle that actually holds a
     * measurement, and fall back to the newest when none does - a genuinely
     * empty database should still show the empty state.
     */
    async defaultCycleId() {
        const measured = await this.orm.formattedReadGroup(
            "aic.hrm.progress.report",
            [["cycle_id", "in", this.state.cycles.map((cycle) => cycle.id)]],
            ["cycle_id"],
            ["__count"],
        );
        const withData = new Set(
            measured
                .filter((group) => group.__count)
                .map((group) => group.cycle_id && group.cycle_id[0]),
        );
        const preferred = this.state.cycles.find((cycle) => withData.has(cycle.id));
        return (preferred || this.state.cycles[0]).id;
    }

    get domain() {
        // Every period inside the cycle, not the cycle alone. Objectives are
        // set per quarter and KPIs assigned per month, so reading the
        // quarter alone showed one measurement out of thirty-nine and called
        // it "100% achieved, nothing behind plan". The server decides the
        // scope, and the same rule is tested there.
        return [["cycle_id", "in", this.state.scope ? this.state.scope.cycle_ids : []]];
    }

    async onCycleChange(ev) {
        const cycleId = parseInt(ev.target.value, 10);
        if (!cycleId) {
            return;
        }
        this.state.cycleId = cycleId;
        await this.load();
    }

    async load() {
        // Odoo 19 exposes formatted_read_group; the older readGroup is
        // gone from the ORM service.
        const model = "aic.hrm.progress.report";
        this.state.scope = await this.orm.call(model, "overview_scope",
                                               [this.state.cycleId]);
        if (!this.state.scope.cycle_ids.length) {
            this.state.months = [];
            this.state.departments = [];
            this.state.laggards = [];
            this.state.summary = { achieved: 0, expected: 0, gap: 0, measurements: 0 };
            return;
        }
        const [byMonth, byDepartment, worst, overall] = await Promise.all([
            this.orm.formattedReadGroup(
                model, this.domain, ["date:month"],
                ["__count", "achieved:avg", "expected:avg"]),
            this.orm.formattedReadGroup(
                model, this.domain, ["department_id"],
                ["__count", "achieved:avg", "gap:avg"]),
            this.orm.searchRead(
                // The owner, because the customer gives one KPI to several
                // people on purpose: three of them share the FAST Channel
                // revenue line, and without a name the rail printed the same
                // sentence three times with nothing to tell them apart.
                model, this.domain.concat([["gap", "<", 0]]),
                ["label", "gap", "achieved", "department_id", "employee_id", "date"],
                { order: "gap asc", limit: 8 }),
            this.orm.formattedReadGroup(
                model, this.domain, [],
                ["__count", "achieved:avg", "expected:avg"]),
        ]);

        // A date group comes back as [raw value, display label]; rendering
        // the pair puts "2026-06-01,June 2026" on the axis.
        this.state.months = byMonth.map((row) => ({
            key: Array.isArray(row["date:month"])
                ? row["date:month"][0] : row["date:month"],
            label: Array.isArray(row["date:month"])
                ? row["date:month"][1] : row["date:month"],
            count: row.__count,
            achieved: row["achieved:avg"] || 0,
            expected: row["expected:avg"] || 0,
        }));
        // Worst first: a ranking a manager reads top-down should start
        // where the attention is needed.
        this.state.departments = byDepartment
            .map((row) => ({
                id: row.department_id ? row.department_id[0] : 0,
                name: row.department_id ? row.department_id[1]
                    : _t("Not assigned to a department"),
                count: row.__count,
                achieved: row["achieved:avg"] || 0,
                gap: row["gap:avg"] || 0,
            }))
            .sort((a, b) => a.gap - b.gap);
        this.state.laggards = worst;
        const totals = overall[0] || {};
        this.state.summary = {
            achieved: totals["achieved:avg"] || 0,
            expected: totals["expected:avg"] || 0,
            gap: (totals["achieved:avg"] || 0) - (totals["expected:avg"] || 0),
            measurements: totals.__count || 0,
        };
    }

    /**
     * Which periods these figures speak for.
     *
     * A quarter reads as its months, so the strip above can say "39
     * measurements" while the selector says "Q3". Without this line a
     * reader cannot tell a quarter that gathered three months from one that
     * happened to hold three rows of its own.
     */
    scopeNote() {
        const scope = this.state.scope;
        if (!scope) {
            return "";
        }
        const names = scope.cycles.map((cycle) => cycle.name).join(", ");
        const notes = {
            own: _t("Measurements of %s.", names),
            children: _t("Gathered from the periods inside this cycle: %s.", names),
            none: _t("Nothing has been measured in this period or in any period inside it."),
        };
        return notes[scope.source] || "";
    }

    formatPercent(value) {
        return `${Math.round((value || 0) * 100)}%`;
    }

    /** Signed, because the sign is the whole message. */
    formatGap(value) {
        const points = Math.round((value || 0) * 100);
        return `${points > 0 ? "+" : ""}${points} pts`;
    }

    gapClass(value) {
        if (value < -0.1) {
            return "o_aic_band_red";
        }
        return value < 0 ? "o_aic_band_amber" : "o_aic_band_green";
    }

    /** Bar height as a share of the tallest bar on the chart. */
    barHeight(value) {
        const peak = Math.max(
            0.01,
            ...this.state.months.map((m) => Math.max(m.achieved, m.expected)));
        return `${Math.round((Math.max(value, 0) / peak) * 100)}%`;
    }

    openDetail(extraDomain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Progress vs Plan",
            res_model: "aic.hrm.progress.report",
            domain: this.domain.concat(extraDomain || []),
            views: [[false, "pivot"], [false, "graph"], [false, "list"]],
        });
    }
}

registry.category("actions").add("aic_hrm_report_overview",
                                 AicHrmReportOverview);
