odoo.define('aic_hrm_match.tour.demo', function(require) {
    var { registry } = require("@web/core/registry");
    registry.category("web_tour.tours").add("aic_hrm_match_demo", {
        test: true,
        steps: [{
            content: "Staffing Match demo tour",
            trigger: "body",
            run: "click",
        }],
    });
});
