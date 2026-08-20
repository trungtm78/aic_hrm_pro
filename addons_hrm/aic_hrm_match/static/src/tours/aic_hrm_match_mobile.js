/** @odoo-module **/
/*
 * The same screens at 375px, checking the one thing a screenshot cannot.
 *
 * "Mobile responsive" is a claim about behaviour, and the failure it hides is
 * always the same: a table wider than the viewport, so the whole page scrolls
 * sideways and the first column goes with it. That is measured here rather than
 * eyeballed, because it is the difference between a layout somebody can use on
 * a phone and one they can only look at.
 */
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("aic_hrm_match_mobile", {
    // Straight to the screen rather than through the app menu. At 375px the
    // menu is a different component with different markup, and clicking
    // through it would be testing Odoo's mobile navigation rather than whether
    // this module's list fits on a phone - which is the question here.
    url: "/odoo/action-aic_hrm_match.action_aic_hrm_match_request",
    steps: () => [
        {
            content: "The list is on screen",
            trigger: ".o_list_view, .o_kanban_view",
        },
        {
            content: "The page does not scroll sideways",
            trigger: "body",
            run() {
                const overflow =
                    document.body.scrollWidth - document.documentElement.clientWidth;
                // A pixel or two is rounding on a scrollbar; a column hanging
                // off the edge is tens of pixels, which is what this catches.
                if (overflow > 4) {
                    throw new Error(
                        `the page is ${overflow}px wider than the viewport, so the ` +
                        `first column scrolls away on a phone`
                    );
                }
            },
        },
    ],
});
