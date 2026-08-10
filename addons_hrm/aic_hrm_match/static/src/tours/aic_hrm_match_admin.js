/** @odoo-module **/
/*
 * The administrator's path: read the rules the rankings run under.
 *
 * The claim on the listing page is that the weights are somebody's to read and
 * change, so the screen that shows them has to open. Reaching the policy list
 * exercises the configuration menu, the action, the admin-only access rules and
 * the list view together - and those are all things every model test in the
 * suite passes without.
 */
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_service/tour_utils";

registry.category("web_tour.tours").add("aic_hrm_match_admin", {
    url: "/odoo",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Staffing",
            trigger: '.o_app[data-menu-xmlid="aic_hrm_match.menu_aic_hrm_match_root"]',
            run: "click",
        },
        {
            content: "Open the Configuration section",
            trigger: '[data-menu-xmlid="aic_hrm_match.menu_aic_hrm_match_configuration"]',
            run: "click",
        },
        {
            content: "Go to the scoring policies",
            trigger: '[data-menu-xmlid="aic_hrm_match.menu_aic_hrm_match_policy_list"]',
            run: "click",
        },
        {
            content: "The policies are on screen",
            trigger: ".o_list_view, .o_kanban_view",
        },
    ],
});
