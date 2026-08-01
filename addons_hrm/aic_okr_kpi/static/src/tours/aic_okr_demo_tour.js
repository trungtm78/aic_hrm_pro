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
