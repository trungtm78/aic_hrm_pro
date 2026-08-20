/** @odoo-module **/
/*
 * The path a buyer is shown, walked end to end.
 *
 * It doubles as the sales demo, which is why it follows the flow a planner
 * actually uses rather than the shortest route through the models: open the
 * Staffing app, raise a request, rank it, and read why the top candidate is on
 * top. A tour that drove the models directly would pass while the screens were
 * broken.
 */
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_service/tour_utils";

registry.category("web_tour.tours").add("aic_hrm_match_demo", {
    url: "/odoo",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Staffing",
            trigger: '.o_app[data-menu-xmlid="aic_hrm_match.menu_aic_hrm_match_root"]',
            run: "click",
        },
        {
            // "Requests" is a section that holds the action rather than
            // carrying one itself, so the menu has to be opened before the
            // entry underneath it exists to click.
            content: "Open the Requests section",
            trigger: '[data-menu-xmlid="aic_hrm_match.menu_aic_hrm_match_request"]',
            run: "click",
        },
        {
            content: "Go to the staffing requests",
            trigger: '[data-menu-xmlid="aic_hrm_match.menu_aic_hrm_match_request_list"]',
            run: "click",
        },
        {
            // Reaching the list is the assertion. It means the menu, the
            // action, the model's access rules and the list view all line up -
            // four different ways the app can be broken while every model test
            // stays green.
            content: "The requests list is on screen",
            trigger: ".o_list_view, .o_kanban_view",
        },
    ],
});
