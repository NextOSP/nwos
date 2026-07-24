import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { BodDashboard } from "@nwos_bod_dashboard/bod_dashboard";

patch(BodDashboard.prototype, {
    printRfidBod() {
        this.actionService.doAction({
            type: "ir.actions.report",
            report_type: "qweb-pdf",
            report_name: "nwos_rfid_bod.report_rfid_bod_monthly",
            report_file: "nwos_rfid_bod.report_rfid_bod_monthly",
            name: _t("Nextwaves Kit Monthly Report"),
            context: {
                active_model: "res.company",
                active_id: this.state.data.company_id,
                active_ids: [this.state.data.company_id],
            },
        });
    },
    openRfidSites(state = null) {
        const domain = state ? [["state", "=", state]] : [];
        this.openList("rfid.service.site", domain, _t("Nextwaves Kit Sites"));
    },
    openRfidSubscriptions(overdue = false) {
        const domain = [["state", "=", "active"]];
        if (overdue) {
            domain.push(["collection_state", "=", "overdue"]);
        }
        this.openList("rfid.subscription", domain, _t("Nextwaves Kit Subscriptions"));
    },
    openRfidTickets(slaFailed = false) {
        const domain = [["rfid_site_id", "!=", false], ["is_closed", "=", false]];
        if (slaFailed) {
            domain.push(["sla_fail", "=", true]);
        }
        this.openList("helpdesk.ticket", domain, _t("Nextwaves Kit Support Tickets"));
    },
    openRfidTasks() {
        this.openList(
            "project.task",
            [["rfid_site_id", "!=", false], ["state", "not in", ["1_done", "1_canceled"]]],
            _t("Nextwaves Kit Implementation Tasks")
        );
    },
});
