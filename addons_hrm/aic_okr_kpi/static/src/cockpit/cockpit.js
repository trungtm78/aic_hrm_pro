/** @odoo-module **/
// Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Leadership cockpit — the "reading desk": one health strip, a RAG heatmap
 * per department, and the risk queue. Data comes from three batched ORM
 * calls per cycle switch; everything else is client-side arithmetic.
 */
/**
 * Score of a set of objectives, weighted the way an objective roll-up is
 * weighted everywhere else: a 50% objective must not count the same as a 10%
 * one. Falls back to a flat average when no weight is set at all.
 */
export function weightedScore(objectives) {
    if (!objectives.length) {
        return 0;
    }
    const weight = objectives.reduce((total, o) => total + (o.weight || 0), 0);
    if (!weight) {
        return objectives.reduce((total, o) => total + (o.score || 0), 0)
            / objectives.length;
    }
    return objectives.reduce(
        (total, o) => total + (o.score || 0) * (o.weight || 0), 0) / weight;
}

/** Share of the weight that has figures behind it, in percent. */
export function coverageOf(objectives) {
    if (!objectives.length) {
        return 0;
    }
    const weight = objectives.reduce((total, o) => total + (o.weight || 0), 0);
    if (!weight) {
        return objectives.reduce((total, o) => total + (o.data_coverage || 0), 0)
            / objectives.length;
    }
    return objectives.reduce(
        (total, o) => total + (o.data_coverage || 0) * (o.weight || 0), 0) / weight;
}

export class AicHrmCockpit extends Component {
    static template = "aic_okr_kpi.Cockpit";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            cycles: [],
            cycleId: false,
            stats: null,
            heatmapRows: [],
            risks: [],
            loading: true,
        });
        onWillStart(async () => {
            this.state.cycles = await this.orm.searchRead(
                "aic.hrm.cycle",
                [["state", "in", ["open", "review", "closed"]]],
                ["id", "name", "code", "state"],
                { order: "date_start desc" },
            );
            if (this.state.cycles.length) {
                // The newest cycle is often a month that carries scorecards
                // but no objectives; open on the newest one that actually has
                // objectives, so the desk does not start empty.
                const counts = await this.orm.readGroup(
                    "aic.hrm.objective",
                    [["cycle_id", "in", this.state.cycles.map((c) => c.id)]],
                    ["cycle_id"],
                    ["cycle_id"],
                );
                const withObjectives = new Set(
                    counts.map((group) => group.cycle_id && group.cycle_id[0]));
                const first = this.state.cycles.find(
                    (cycle) => withObjectives.has(cycle.id)) || this.state.cycles[0];
                this.state.cycleId = first.id;
                await this.loadCycle();
            }
            this.state.loading = false;
        });
    }

    async onCycleChange(ev) {
        const cycleId = parseInt(ev.target.value, 10);
        if (!cycleId) {
            return;
        }
        this.state.cycleId = cycleId;
        await this.loadCycle();
    }

    async loadCycle() {
        const cycleId = this.state.cycleId;
        const [objectives, krs, risks] = await Promise.all([
            this.orm.searchRead(
                "aic.hrm.objective",
                [["cycle_id", "=", cycleId]],
                ["id", "code", "name", "department_id", "objective_type",
                 "score", "score_covered", "data_coverage", "weight", "rag",
                 "state"],
                { limit: 500 },
            ),
            this.orm.searchRead(
                "aic.hrm.key.result",
                [["cycle_id", "=", cycleId]],
                ["id", "is_stale", "rag", "has_actual", "last_checkin_date"],
                { limit: 2000 },
            ),
            this.orm.searchRead(
                "aic.hrm.key.result",
                ["&", ["cycle_id", "=", cycleId],
                 "|", ["rag", "=", "red"], ["is_stale", "=", true]],
                ["id", "code", "name", "employee_id", "rag", "is_stale",
                 "progress"],
                { limit: 10 },
            ),
        ]);
        const committed = objectives.filter(
            (o) => o.objective_type === "committed");
        const measured = objectives.filter((o) => o.data_coverage > 0);
        const reported = krs.filter((kr) => kr.has_actual);
        const stale = krs.filter((kr) => kr.is_stale);
        this.state.stats = {
            overall: weightedScore(objectives),
            committed: weightedScore(committed),
            // What has been reported at all, not what has been reported
            // recently: `is_stale` only flags a key result that was checked
            // in once and then left, so counting "not stale" as fresh read
            // 100% while nine of ten key results had no update whatsoever.
            reportedRate: krs.length ? reported.length / krs.length : 0,
            staleCount: stale.length,
            krCount: krs.length,
            objectiveCount: objectives.length,
            unmeasuredCount: objectives.length - measured.length,
            coverage: coverageOf(objectives),
        };
        this.state.heatmapRows = this.buildHeatmap(objectives);
        this.state.risks = risks;
    }

    /**
     * Group objectives per department and give every row the two things a
     * reader needs before any individual cell means anything: how the
     * department is doing overall, and how many objectives sit in each
     * band. Rows and cells are both ordered worst-first, so the eye lands
     * on the problem instead of hunting for it.
     */
    buildHeatmap(objectives) {
        const RANK = { red: 0, amber: 1, none: 2, green: 3 };
        const unassigned = _t("Not assigned to a department");
        const byDepartment = new Map();
        for (const objective of objectives) {
            const key = objective.department_id
                ? objective.department_id[1] : unassigned;
            if (!byDepartment.has(key)) {
                byDepartment.set(key, []);
            }
            byDepartment.get(key).push(objective);
        }
        const rows = [...byDepartment.entries()].map(([department, list]) => {
            const counts = { red: 0, amber: 0, green: 0, none: 0 };
            for (const objective of list) {
                counts[objective.rag || "none"] += 1;
            }
            list.sort((a, b) => (RANK[a.rag || "none"] - RANK[b.rag || "none"])
                || ((a.score || 0) - (b.score || 0)));
            return {
                department,
                objectives: list,
                counts,
                score: weightedScore(list),
                coverage: coverageOf(list),
                isUnassigned: department === unassigned,
            };
        });
        // Worst department first; the unassigned bucket is bookkeeping, not
        // a business unit, so it never outranks a real one.
        rows.sort((a, b) => (a.isUnassigned - b.isUnassigned)
            || (a.score - b.score));
        return rows;
    }

    formatPercent(value) {
        return `${Math.round((value || 0) * 100)}%`;
    }

    /** A percentage that is already 0..100 (coverage), not 0..1. */
    formatShare(value) {
        return `${Math.round(value || 0)}%`;
    }

    ragLabel(rag) {
        const labels = {
            green: _t("On track"),
            amber: _t("At risk"),
            red: _t("Off track"),
            none: _t("Not scored"),
        };
        return labels[rag] || labels.none;
    }

    /** Tooltip text for a heatmap cell: name, band and score in one line. */
    cellTitle(objective) {
        return `${objective.code} · ${objective.name} — `
            + `${this.ragLabel(objective.rag)} `
            + `(${this.formatPercent(objective.score)})`;
    }
}

registry.category("actions").add("aic_hrm_cockpit", AicHrmCockpit);
