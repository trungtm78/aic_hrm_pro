/** @odoo-module **/
// Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { cycleWithObjectives } from "../cycle_choice";

/**
 * Alignment tree — indented rails, no bubble charts. Objectives nest by
 * parent link (cross-cycle parents render at the root of their cycle
 * grouping); key results are the leaves. Expand/collapse is pure state,
 * opacity-only motion.
 */
export class AicHrmAlignmentTree extends Component {
    static template = "aic_okr_kpi.AlignmentTree";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            cycles: [],
            cycleId: false,
            roots: [],
            scope: null,
            collapsed: {},
            summary: null,
            loading: true,
        });
        onWillStart(async () => {
            // Same filter as the cockpit. This read every cycle including
            // drafts, so the tree opened on a cycle that had not started -
            // typically empty - while the cockpit next to it showed the
            // live one. Two dashboards disagreeing about which cycles
            // count is worse than either being wrong.
            this.state.cycles = await this.orm.searchRead(
                "aic.hrm.cycle",
                [["state", "in", ["open", "review", "closed"]]],
                ["id", "name", "code", "state"],
                { order: "date_start desc" },
            );
            // The newest cycle is usually a month with scorecards but no
            // objectives; opening there showed "chu kỳ chưa có mục tiêu"
            // on a system that holds four of them.
            this.state.cycleId = await cycleWithObjectives(this.orm, this.state.cycles);
            if (this.state.cycleId) {
                await this.loadTree();
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
        await this.loadTree();
    }

    async loadTree() {
        const cycleId = this.state.cycleId;
        // Objectives are set on the quarter while the selector also offers
        // the year and each month, so reading the selected cycle alone drew
        // "this cycle has no objectives" on four of the customer's five
        // cycles. The server decides which cycles speak for this one, by the
        // same rule the leadership desk uses, and the rule is tested there.
        this.state.scope = await this.orm.call(
            "aic.hrm.objective", "alignment_scope", [cycleId]);
        const cycleIds = this.state.scope.cycle_ids;
        const [objectives, krs, contributions] = await Promise.all([
            this.orm.searchRead(
                "aic.hrm.objective",
                [["cycle_id", "in", cycleIds]],
                ["id", "code", "name", "parent_id", "employee_id", "score",
                 "rag", "level", "weight", "objective_type",
                 "department_id"],
                { limit: 1000, order: "code" },
            ),
            this.orm.searchRead(
                "aic.hrm.key.result",
                [["cycle_id", "in", cycleIds]],
                ["id", "code", "name", "objective_id", "employee_id",
                 "progress", "rag"],
                { limit: 2000, order: "code" },
            ),
            // Who is carrying each key result through their own KPIs. The
            // KPIs are monthly while the key result is quarterly, so the
            // server folds a person's months into one entry: reading the
            // report rows raw named the same person once per scorecard,
            // three deep with three different scores.
            this.orm.call(
                "aic.hrm.objective.contribution",
                "carriers_for_cycle",
                [cycleId],
            ),
        ]);
        const carriedBy = new Map();
        for (const row of contributions) {
            const key = row.kr_id ? `kr-${row.kr_id}` : `o-${row.objective_id}`;
            if (!carriedBy.has(key)) {
                carriedBy.set(key, []);
            }
            carriedBy.get(key).push(row);
        }
        const nodeById = new Map(objectives.map((objective) => [
            objective.id,
            { ...objective, children: [], krs: [] },
        ]));
        for (const kr of krs) {
            const parent = nodeById.get(kr.objective_id[0]);
            if (parent) {
                parent.krs.push({ ...kr, people: carriedBy.get(`kr-${kr.id}`) || [] });
            }
        }
        for (const node of nodeById.values()) {
            node.people = carriedBy.get(`o-${node.id}`) || [];
        }
        const roots = [];
        for (const node of nodeById.values()) {
            const parent = node.parent_id && nodeById.get(node.parent_id[0]);
            if (parent) {
                parent.children.push(node);
            } else {
                roots.push(node);
            }
        }
        this.state.roots = roots;
        this.state.collapsed = {};
        this.state.summary = this.summarise(objectives, krs);
    }

    /**
     * A tree of rows says how things are arranged but not how the cycle is
     * doing. The strip above it answers that first, so the detail below
     * has something to be detail of.
     */
    summarise(objectives, krs) {
        const counts = { red: 0, amber: 0, green: 0, none: 0 };
        let weighted = 0;
        let weight = 0;
        for (const objective of objectives) {
            counts[objective.rag || "none"] += 1;
            const w = objective.weight || 0;
            weighted += (objective.score || 0) * w;
            weight += w;
        }
        return {
            objectives: objectives.length,
            keyResults: krs.length,
            counts,
            score: weight ? weighted / weight : 0,
        };
    }

    /**
     * Which cycle's objectives are on screen.
     *
     * A month draws the objectives of its quarter, which is right but only
     * if the screen says so: otherwise a reader takes a quarterly objective
     * for a monthly one.
     */
    scopeNote() {
        const scope = this.state.scope;
        if (!scope) {
            return "";
        }
        const names = scope.cycles.map((cycle) => cycle.name).join(", ");
        const notes = {
            own: "",
            parent: _t("No objectives are set on this cycle itself: showing those of %s, the cycle it belongs to.", names),
            children: _t("Gathered from the cycles inside this one: %s.", names),
            none: _t("No objectives in this cycle, inside it or above it."),
        };
        return notes[scope.source] || "";
    }

    /** Levels are stored as keys; a reader wants the word. */
    levelLabel(level) {
        const labels = {
            company: "Company",
            branch: "Branch",
            department: "Department",
            team: "Team",
            individual: "Individual",
        };
        return labels[level] || level || "";
    }

    toggle(nodeId) {
        this.state.collapsed[nodeId] = !this.state.collapsed[nodeId];
    }

    /**
     * One carrier, one line: "Chu Thị Lâm Oanh · 92 trọng số · 100%".
     *
     * A carrier who has figures for some of their months but not all is the
     * common case mid-quarter, and a bare percentage would read as finished.
     * The line says how many periods it speaks for.
     */
    carrierLabel(row) {
        const name = row.employee_name || _t("Not assigned");
        // The word is part of the phrase, not a term on its own: as a bare
        // msgid "weight" was never translated and a Vietnamese screen read
        // "80 weight".
        const weight = _t("%s weight", Math.round(row.weight || 0));
        if (!row.measured_periods) {
            return `${name} · ${weight} · ${_t("no figures yet")}`;
        }
        const score = this.formatPercent(row.score_covered);
        if (row.measured_periods < row.periods) {
            return `${name} · ${weight} · ${score} ` + _t(
                "(%(measured)s of %(total)s periods measured)",
                { measured: row.measured_periods, total: row.periods });
        }
        return `${name} · ${weight} · ${score}`;
    }

    formatPercent(value) {
        return `${Math.round((value || 0) * 100)}%`;
    }
}

registry.category("actions").add("aic_hrm_alignment_tree", AicHrmAlignmentTree);
