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
            loading: true,
        });
        onWillStart(async () => {
            this.state.cycles = await this.orm.searchRead(
                "aic.hrm.cycle", [],
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
                 "rag", "level"],
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
    }

    toggle(nodeId) {
        this.state.collapsed[nodeId] = !this.state.collapsed[nodeId];
    }

    formatPercent(value) {
        return `${Math.round((value || 0) * 100)}%`;
    }
}

registry.category("actions").add("aic_hrm_alignment_tree", AicHrmAlignmentTree);
