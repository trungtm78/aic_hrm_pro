/** @odoo-module **/
// Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

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
            if (this.state.cycles.length) {
                this.state.cycleId = this.state.cycles[0].id;
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
        const [objectives, krs] = await Promise.all([
            this.orm.searchRead(
                "aic.hrm.objective",
                [["cycle_id", "=", cycleId]],
                ["id", "code", "name", "parent_id", "employee_id", "score",
                 "rag", "level", "weight", "objective_type",
                 "department_id"],
                { limit: 1000, order: "code" },
            ),
            this.orm.searchRead(
                "aic.hrm.key.result",
                [["cycle_id", "=", cycleId]],
                ["id", "code", "name", "objective_id", "employee_id",
                 "progress", "rag"],
                { limit: 2000, order: "code" },
            ),
        ]);
        const nodeById = new Map(objectives.map((objective) => [
            objective.id,
            { ...objective, children: [], krs: [] },
        ]));
        for (const kr of krs) {
            const parent = nodeById.get(kr.objective_id[0]);
            if (parent) {
                parent.krs.push(kr);
            }
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

    formatPercent(value) {
        return `${Math.round((value || 0) * 100)}%`;
    }
}

registry.category("actions").add("aic_hrm_alignment_tree", AicHrmAlignmentTree);
