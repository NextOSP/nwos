import { Component, onWillStart, useState } from "@nwos/owl";
import { useService } from "@web/core/utils/hooks";

const COUNT_ITEMS = [
    { key: "draft", label: "New" },
    { key: "sent", label: "RFQ Sent" },
    { key: "late", label: "Late RFQ", accent: "caution" },
    { key: "not_acknowledged", label: "Not Acknowledged" },
    { key: "late_receipt", label: "Late Receipt", accent: "error" },
];

/**
 * The Purchase order KPI band (New / RFQ Sent / Late RFQ / Not Acknowledged /
 * Late Receipt / OTD / Days to Order), rendered as Carbon mini KPI cards.
 * Data comes from purchase.order.retrieve_dashboard() — the same source as the
 * native Purchase list dashboard band.
 */
export class CarbonPurchaseKpis extends Component {
    static template = "nwos_carbon_dashboard.CarbonKpiBand";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: null, loading: true });
        onWillStart(async () => {
            try {
                this.state.data = await this.orm.call("purchase.order", "retrieve_dashboard", []);
            } catch {
                this.state.data = null;
            }
            this.state.loading = false;
        });
    }

    get cards() {
        const d = this.state.data;
        if (!d) {
            return [];
        }
        const g = d.global || {};
        const my = d.my || {};
        const cards = COUNT_ITEMS.map((it) => ({
            label: it.label,
            value: (g[it.key] && g[it.key].all) ?? 0,
            sub: `My: ${(my[it.key] && my[it.key].all) ?? 0}`,
            accent: it.accent || "",
        }));
        cards.push({ label: "OTD", value: g.otd ?? "—", sub: `My: ${my.otd ?? "—"}`, accent: "" });
        cards.push({
            label: "Days to Order",
            value: g.days_to_order ?? "—",
            sub: `My: ${my.days_to_order ?? "—"}`,
            accent: "",
        });
        return cards;
    }
}
