odoo.define('aic_hrm_match.tour.admin', function(require) {
    var { registry } = require("@web/core/registry");
    registry.category("web_tour.tours").add("aic_hrm_match_admin", {
        test: true,
        steps: [{
            content: "Policy configuration tour",
            trigger: "body",
            run: "click",
        }],
    });
});
