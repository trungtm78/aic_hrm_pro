/** @odoo-module **/
// Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

/**
 * The menu bar groups the app into stages of the operating loop, so a menu
 * item is not on screen until its stage is open. These helpers say that once
 * instead of every tour learning it the hard way - which is how both tours
 * here broke when the menu was regrouped: they clicked items that had moved
 * inside a dropdown and timed out looking for them.
 */
const openStage = (stage, label) => ({
    content: `Open the ${label} stage`,
    trigger: `[data-menu-xmlid='aic_hrm_base.menu_aic_hrm_${stage}']`,
    run: "click",
});

const openItem = (xmlid, label) => ({
    content: `Open ${label}`,
    trigger: `[data-menu-xmlid='${xmlid}']`,
    run: "click",
});

const PLAN = () => openStage("plan", "Plan");
const EXECUTE = () => openStage("do", "Execute");

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
        PLAN(),
        openItem("aic_okr_kpi.menu_aic_hrm_objectives", "the Objectives menu"),
        {
            content: "Objective list renders",
            trigger: ".o_list_view, .o_view_nocontent",
        },
        // Cockpit hangs off the app root, not off a stage: it is the one
        // screen you reach without choosing where you are in the loop.
        openItem("aic_okr_kpi.menu_aic_hrm_cockpit", "the Cockpit"),
        {
            content: "Cockpit renders with the Muc & Thep shell",
            trigger: ".o_aic_hrm",
        },
        {
            // The shell renders even when the data call fails - the error
            // arrives as a dialog over it - so the tour waits for a figure
            // that only exists once the cycle has actually been read.
            content: "Cockpit shows the health strip it just computed",
            trigger: ".o_aic_health_strip .o_aic_stat_value",
        },
        {
            content: "and no error dialog covers it",
            trigger: ".o_aic_hrm:not(:has(.o_dialog))",
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
        PLAN(),
        openItem("aic_okr_kpi.menu_aic_hrm_key_results", "Key Results"),
        {
            content: "Key Results list renders",
            trigger: ".o_list_view, .o_view_nocontent",
        },
        PLAN(),
        openItem("aic_okr_kpi.menu_aic_hrm_kpi_targets", "KPI Targets"),
        {
            content: "KPI Targets list renders",
            trigger: ".o_list_view, .o_view_nocontent",
        },
        EXECUTE(),
        openItem("aic_okr_kpi.menu_aic_hrm_checkins", "Check-ins"),
        {
            content: "Check-ins list renders",
            trigger: ".o_list_view, .o_view_nocontent",
        },
        PLAN(),
        openItem("aic_okr_kpi.menu_aic_hrm_assignments", "Scorecards"),
        {
            content: "Scorecards list renders",
            trigger: ".o_list_view, .o_view_nocontent",
        },
        PLAN(),
        openItem("aic_okr_kpi.menu_aic_hrm_alignment_tree", "the Alignment Tree"),
        {
            content: "Alignment tree renders in the design shell",
            trigger: ".o_aic_hrm",
        },
    ],
});
