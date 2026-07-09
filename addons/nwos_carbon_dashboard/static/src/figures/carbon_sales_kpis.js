import { Component, onWillStart, useState } from "@nwos/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * A Sales KPI band (Quotations / Sales Orders / To Invoice / Total Sales / Avg
 * Order), rendered as Carbon mini KPI cards. sale.order has no built-in
 * dashboard method, so the figures are computed here via a few ORM aggregates.
 */
export class CarbonSalesKpis extends Component {
    static template = "nwos_carbon_dashboard.CarbonKpiBand";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({ cards: [], loading: true });
        onWillStart(async () => {
            try {
                const [quotations, orders, toInvoice, totals] = await Promise.all([
                    this.orm.searchCount("sale.order", [["state", "in", ["draft", "sent"]]]),
                    this.orm.searchCount("sale.order", [["state", "=", "sale"]]),
                    this.orm.searchCount("sale.order", [
                        ["state", "=", "sale"],
                        ["invoice_status", "=", "to invoice"],
                    ]),
                    this.orm.readGroup(
                        "sale.order",
                        [["state", "=", "sale"]],
                        ["amount_total:sum"],
                        []
                    ),
                ]);
                const total = (totals[0] && totals[0].amount_total) || 0;
                const avg = orders ? total / orders : 0;
                this.state.cards = [
                    { label: "Quotations", value: quotations, sub: "" },
                    { label: "Sales Orders", value: orders, sub: "" },
                    { label: "To Invoice", value: toInvoice, sub: "", accent: "caution" },
                    { label: "Total Sales", value: this._money(total), sub: "" },
                    { label: "Avg Order", value: this._money(avg), sub: "" },
                ];
            } catch {
                this.state.cards = [];
            }
            this.state.loading = false;
        });
    }

    get cards() {
        return this.state.cards;
    }

    _money(n) {
        const v = Number(n) || 0;
        return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
    }
}
