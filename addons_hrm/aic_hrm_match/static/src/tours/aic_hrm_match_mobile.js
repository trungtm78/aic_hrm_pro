odoo.define('aic_hrm_match.tour.mobile', function(require) {
    var { registry } = require("@web/core/registry");
    registry.category("web_tour.tours").add("aic_hrm_match_mobile", {
        test: true,
        steps: [{
            content: "Mobile responsive check",
            trigger: "body",
            run: "click",
        }],
    });
});
