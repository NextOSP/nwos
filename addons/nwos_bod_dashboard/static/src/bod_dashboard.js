import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart, useState, useRef, useEffect } from "@nwos/owl";
import { loadBundle } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { BodAiPanel } from "./ai_panel";

const PERIODS = [
    { id: "month", label: _t("This month") },
    { id: "quarter", label: _t("This quarter") },
    { id: "last90", label: _t("Last 90 days") },
    { id: "year", label: _t("This year") },
];

export class BodDashboard extends Component {
    static template = "nwos_bod_dashboard.BodDashboard";
    static components = { BodAiPanel };
    static props = { ...standardActionServiceProps };

    setup() {
        this.actionService = useService("action");
        this.periods = PERIODS;
        this.state = useState({
            loading: true,
            data: null,
            period: "last90",
            tab: (this.props.action.context || {}).default_bod_tab || "overview",
            aiOpen: false,
        });
        this.trendCanvas = useRef("trendCanvas");
        this._chart = null;

        onWillStart(async () => {
            this._loadCarbonFont();
            try {
                await loadBundle("web.chartjs_lib");
            } catch {
                // Chart.js optional: the dashboard still renders without the trend graph.
            }
            await this.load();
        });

        // Redraw the trend chart whenever the data set is replaced.
        useEffect(
            () => {
                this.renderChart();
            },
            () => [this.state.data, this.state.tab]
        );
    }

    /** Load the IBM Plex Sans typeface (Carbon Design System) if available. */
    _loadCarbonFont() {
        if (document.getElementById("bod_carbon_font")) {
            return;
        }
        const link = document.createElement("link");
        link.id = "bod_carbon_font";
        link.rel = "stylesheet";
        link.href =
            "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap";
        document.head.appendChild(link);
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await rpc("/nwos_bod/data", { period: this.state.period });
        } finally {
            this.state.loading = false;
        }
    }

    async setPeriod(period) {
        if (period === this.state.period) {
            return;
        }
        this.state.period = period;
        await this.load();
    }

    get currentPeriodLabel() {
        return (PERIODS.find((p) => p.id === this.state.period) || PERIODS[0]).label;
    }

    /** Compact snapshot of the loaded KPIs, sent to the AI as grounding context. */
    aiContext() {
        return this.state.data || {};
    }

    hasSection(key) {
        return Boolean(this.state.data && (this.state.data.sections || []).includes(key));
    }

    renderChart() {
        const canvas = this.trendCanvas.el;
        if (this._chart) {
            this._chart.destroy();
            this._chart = null;
        }
        const trend = this.state.data && this.state.data.sales && this.state.data.sales.trend;
        if (!canvas || !window.Chart || !trend || !trend.length) {
            return;
        }
        this._chart = new window.Chart(canvas, {
            type: "bar",
            data: {
                labels: trend.map((p) => p.label),
                datasets: [
                    {
                        label: _t("Revenue"),
                        data: trend.map((p) => p.value),
                        backgroundColor: "#0f62fe",
                        borderRadius: 0,
                        maxBarThickness: 48,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, ticks: { maxTicksLimit: 5 } },
                    x: { grid: { display: false } },
                },
            },
        });
    }

    deltaClass(delta) {
        if (delta === null || delta === undefined) {
            return "text-muted";
        }
        return delta >= 0 ? "text-success" : "text-danger";
    }

    deltaLabel(delta) {
        if (delta === null || delta === undefined) {
            return "—";
        }
        return `${delta >= 0 ? "▲" : "▼"} ${Math.abs(delta)}%`;
    }

    // ---- Drill-down: clicking a tile opens the underlying list view ----
    get dateBounds() {
        const d = this.state.data || {};
        return { from: d.date_from, to: d.date_to ? `${d.date_to} 23:59:59` : false };
    }

    openList(model, domain, name) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            domain,
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: "current",
        });
    }

    openSales(extraDomain = []) {
        const { from, to } = this.dateBounds;
        this.openList(
            "sale.order",
            [["state", "=", "sale"], ["date_order", ">=", from], ["date_order", "<=", to], ...extraDomain],
            _t("Sales Orders")
        );
    }
    openCustomer(customer) {
        this.openSales([["partner_id", "=", customer.id]]);
    }
    openProduct(product) {
        this.openSales([["order_line.product_id", "=", product.id]]);
    }
    openSalesman(salesman) {
        this.openSales([["user_id", "=", salesman.id || false]]);
    }

    openInvoicing(kind) {
        const d = this.state.data;
        const base = [["move_type", "=", "out_invoice"], ["state", "=", "posted"]];
        let domain = base;
        let name = _t("Invoices");
        if (kind === "invoiced") {
            domain = [...base, ["invoice_date", ">=", d.date_from], ["invoice_date", "<=", d.date_to]];
        } else if (kind === "overdue") {
            domain = [
                ...base,
                ["payment_state", "in", ["not_paid", "partial"]],
                ["invoice_date_due", "<", d.date_to],
            ];
            name = _t("Overdue Invoices");
        } else if (kind === "unpaid") {
            domain = [...base, ["payment_state", "in", ["not_paid", "partial"]]];
            name = _t("Unpaid Invoices");
        }
        this.openList("account.move", domain, name);
    }

    openPipeline() {
        this.openList(
            "crm.lead",
            [["type", "=", "opportunity"], ["probability", "<", 100], ["probability", ">", 0]],
            _t("Opportunities")
        );
    }
    openPurchase() {
        const { from, to } = this.dateBounds;
        this.openList(
            "purchase.order",
            [["state", "in", ["purchase", "done"]], ["date_order", ">=", from], ["date_order", "<=", to]],
            _t("Purchase Orders")
        );
    }
    openOutOfStock() {
        this.openList(
            "product.product",
            [["type", "=", "consu"], ["is_storable", "=", true], ["qty_available", "<=", 0]],
            _t("Products Out of Stock")
        );
    }
    openPos() {
        const { from, to } = this.dateBounds;
        this.openList(
            "pos.order",
            [["state", "in", ["paid", "done"]], ["date_order", ">=", from], ["date_order", "<=", to]],
            _t("POS Orders")
        );
    }
    openFunnel(bar, seg) {
        this.openList(
            bar.model,
            [...bar.domain, [bar.groupby.split(":")[0], "=", seg.value]],
            `${bar.label} · ${seg.label}`
        );
    }
}

registry.category("actions").add("nwos_bod_dashboard", BodDashboard);
