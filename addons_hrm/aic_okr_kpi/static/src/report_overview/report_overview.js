/** @odoo-module **/
// Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

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
                this.state.cycleId = this.state.cycles[0].id;
                await this.load();
            }
            this.state.loading = false;
        });
    }

    get domain() {
        return [["cycle_id", "=", this.state.cycleId]];
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
        const [byMonth, byDepartment, worst, overall] = await Promise.all([
            this.orm.formattedReadGroup(
                model, this.domain, ["date:month"],
                ["__count", "achieved:avg", "expected:avg"]),
            this.orm.formattedReadGroup(
                model, this.domain, ["department_id"],
                ["__count", "achieved:avg", "gap:avg"]),
            this.orm.searchRead(
                model, this.domain.concat([["gap", "<", 0]]),
                ["label", "gap", "achieved", "department_id", "date"],
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
                    : "Not assigned to a department",
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
