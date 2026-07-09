import { _t } from "@web/core/l10n/translation";
import { markup } from "@nwos/owl";
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("point_of_sale_tour", {
    url: "/nwos",
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            isActive: ["community"],
            trigger: '.o_app[data-menu-xmlid="point_of_sale.menu_point_root"]',
            content: markup(_t("Ready to launch your <b>point of sale</b>?")),
            tooltipPosition: "right",
            run: "click",
        },
        {
            isActive: ["enterprise"],
            trigger: '.o_app[data-menu-xmlid="point_of_sale.menu_point_root"]',
            content: markup(_t("Ready to launch your <b>point of sale</b>?")),
            tooltipPosition: "bottom",
            run: "click",
        },
    ],
});
