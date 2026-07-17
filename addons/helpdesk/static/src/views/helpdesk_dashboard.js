import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart } from "@nwos/owl";

export class HelpdeskDashboard extends Component {
    static template = "helpdesk.Dashboard";
    static props = { list: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        onWillStart(async () => {
            this.data = await this.orm.call("helpdesk.team", "retrieve_dashboard");
        });
    }

    fmtHours(value) {
        const hours = Math.floor(value);
        const minutes = Math.round((value - hours) * 60);
        return `${hours}:${String(minutes).padStart(2, "0")}`;
    }

    fmtPercent(value) {
        return value === null ? "-" : `${value.toFixed(1)} %`;
    }

    fmtRating(value) {
        return value === null ? "-" : `${value.toFixed(1)} / 5`;
    }

    openTickets(title, domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: "helpdesk.ticket",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            domain,
        });
    }
}
