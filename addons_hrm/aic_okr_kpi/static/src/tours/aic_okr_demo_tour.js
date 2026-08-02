/** @odoo-module **/
// Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_service/tour_utils";

/**
 * Demo walk: Performance app -> Objectives list -> Leadership Cockpit.
 * Used both as the customer demo script and as the E2E smoke test.
 */
registry.category("web_tour.tours").add("aic_okr_demo", {
    url: "/odoo",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open the Performance app",
            trigger: ".o_app[data-menu-xmlid='aic_hrm_base.menu_aic_hrm_root']",
            run: "click",
        },
        {
            content: "Open the Objectives menu",
            trigger: "[data-menu-xmlid='aic_okr_kpi.menu_aic_hrm_objectives']",
            run: "click",
        },
        {
            content: "Objective list renders",
            trigger: ".o_list_view, .o_view_nocontent",
        },
        {
            content: "Open the Cockpit",
            trigger: "[data-menu-xmlid='aic_okr_kpi.menu_aic_hrm_cockpit']",
            run: "click",
        },
        {
            content: "Cockpit renders with the Muc & Thep shell",
            trigger: ".o_aic_hrm",
        },
    ],
});

/**
 * Screens walk: every core menu of the OKR/KPI app opens and renders.
 * Complements the ORM-level screen smoke with a real-browser pass.
 */
registry.category("web_tour.tours").add("aic_okr_screens", {
    url: "/odoo",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open the Performance app",
            trigger: ".o_app[data-menu-xmlid='aic_hrm_base.menu_aic_hrm_root']",
            run: "click",
        },
        {
            content: "Open Key Results",
            trigger: "[data-menu-xmlid='aic_okr_kpi.menu_aic_hrm_key_results']",
            run: "click",
        },
        {
            content: "Key Results list renders",
            trigger: ".o_list_view, .o_view_nocontent",
        },
        {
            content: "Open KPI Targets",
            trigger: "[data-menu-xmlid='aic_okr_kpi.menu_aic_hrm_kpi_targets']",
            run: "click",
        },
        {
            content: "KPI Targets list renders",
            trigger: ".o_list_view, .o_view_nocontent",
        },
        {
            content: "Open Check-ins",
            trigger: "[data-menu-xmlid='aic_okr_kpi.menu_aic_hrm_checkins']",
            run: "click",
        },
        {
            content: "Check-ins list renders",
            trigger: ".o_list_view, .o_view_nocontent",
        },
        {
            content: "Open Scorecards",
            trigger: "[data-menu-xmlid='aic_okr_kpi.menu_aic_hrm_assignments']",
            run: "click",
        },
        {
            content: "Scorecards list renders",
            trigger: ".o_list_view, .o_view_nocontent",
        },
        {
            content: "Open the Alignment Tree",
            trigger: "[data-menu-xmlid='aic_okr_kpi.menu_aic_hrm_alignment_tree']",
            run: "click",
        },
        {
            content: "Alignment tree renders in the design shell",
            trigger: ".o_aic_hrm",
        },
    ],
});
