import { Component } from "@nwos/owl";
import { CarbonChart } from "../figures/carbon_chart";
import { CarbonKpiCard } from "../figures/carbon_kpi_card";
import { CarbonTable } from "../figures/carbon_table";
import { CarbonGantt } from "../figures/carbon_gantt";
import { CarbonPurchaseKpis } from "../figures/carbon_purchase_kpis";
import { CarbonSalesKpis } from "../figures/carbon_sales_kpis";
import { runtimeToCarbonChart, runtimeToRankedTable } from "../chart_adapter";

/**
 * Reads the active dashboard's o-spreadsheet Model (data engine only, never the
 * canvas) and lays out its figures as Carbon cards in a responsive 12-col grid.
 *
 * Card kinds:
 *  - kpi        : scorecard chart -> CarbonKpiCard
 *  - chart      : any chart with a clean @carbon/charts mapping -> CarbonChart
 *  - unsupported: charts we can't map yet (treemap/geo/...) -> placeholder
 */
export class CarbonDashboardCanvas extends Component {
    static template = "nwos_carbon_dashboard.CarbonDashboardCanvas";
    static components = {
        CarbonChart,
        CarbonKpiCard,
        CarbonTable,
        CarbonGantt,
        CarbonPurchaseKpis,
        CarbonSalesKpis,
    };
    static props = {
        model: Object, // o-spreadsheet Model of the active dashboard
    };

    get model() {
        return this.props.model;
    }

    /**
     * Ordered card descriptors for the active sheet (reading order).
     * @returns {Array<object>}
     */
    get cards() {
        const model = this.model;
        const sheetId = model.getters.getActiveSheetId();
        const figures = model.getters.getFigures(sheetId);
        const withUI = figures.map((figure) => ({
            figure,
            ui: this._safeFigureUI(sheetId, figure),
        }));
        withUI.sort((a, b) => a.ui.y - b.ui.y || a.ui.x - b.ui.x);
        const contentWidth = Math.max(1, ...withUI.map((w) => w.ui.x + w.ui.width));

        const cards = [];
        for (const { figure, ui } of withUI) {
            try {
                const card = this._describe(figure, ui, contentWidth);
                if (card) {
                    cards.push(card);
                }
            } catch {
                // A single bad figure must not blank the whole dashboard.
                cards.push({
                    id: figure.id,
                    kind: "unsupported",
                    span: 6,
                    title: "",
                    note: "Could not render this figure.",
                });
            }
        }
        // Lists & pivots (Top Invoices, Top Products, …) live in cells, not
        // figures — render each non-empty cell block as a Carbon table.
        try {
            cards.push(...this._cellTableCards(sheetId));
        } catch {
            // Cell extraction must never blank the dashboard.
        }
        // Model-specific extensions (Gantt for Manufacturing, KPI bands for
        // Purchase/Sales) prepended so they lead the report.
        let head = [];
        try {
            head = this._extensionCards(sheetId);
        } catch {
            head = [];
        }
        return [...head, ...cards];
    }

    /** Distinct res models referenced by the dashboard's charts. */
    _dashboardModels(sheetId) {
        const models = new Set();
        const collect = (chartId) => {
            try {
                const m = this.model.getters.getChartDefinition(chartId)?.metaData?.resModel;
                if (m) {
                    models.add(m);
                }
            } catch {
                // ignore
            }
        };
        try {
            for (const fig of this.model.getters.getFigures(sheetId)) {
                if (fig.tag === "chart") {
                    collect(this.model.getters.getChartIdFromFigureId(fig.id));
                } else if (fig.tag === "carousel") {
                    try {
                        for (const it of this.model.getters.getCarousel(fig.id).items || []) {
                            if (it.type === "chart" && it.chartId) {
                                collect(it.chartId);
                            }
                        }
                    } catch {
                        // ignore
                    }
                }
            }
        } catch {
            // ignore
        }
        return models;
    }

    /** Custom widgets injected by dashboard type. */
    _extensionCards(sheetId) {
        const models = this._dashboardModels(sheetId);
        const list = [...models];
        const cards = [];
        if (models.has("mrp.production")) {
            cards.push({ id: "ext-gantt", kind: "gantt", span: 12, title: "Manufacturing Schedule" });
        }
        if (list.some((m) => m.startsWith("purchase."))) {
            cards.push({ id: "ext-purchase", kind: "purchase_kpis", span: 12, title: "Purchase Overview" });
        }
        if (list.some((m) => m.startsWith("sale.") || m.startsWith("account."))) {
            cards.push({ id: "ext-sales", kind: "sales_kpis", span: 12, title: "Sales Overview" });
        }
        return cards;
    }

    /**
     * Read the sheet's evaluated cells and turn each non-empty block (separated
     * by blank rows) into a Carbon table. Captures the ODOO.LIST / PIVOT sections
     * (Top Invoices, Top Products, Top Salespeople) that aren't figures.
     */
    _cellTableCards(sheetId) {
        const g = this.model.getters;
        const numCols = Math.min(g.getNumberCols(sheetId) || 0, 15);
        const numRows = Math.min(g.getNumberRows(sheetId) || 0, 120);
        if (!numCols || !numRows) {
            return [];
        }
        const read = (col, row) => {
            try {
                const c = g.getEvaluatedCell({ sheetId, col, row });
                if (c && (c.type === "error" || c.isError)) {
                    return "";
                }
                const v = c && (c.formattedValue ?? c.value);
                if (v === null || v === undefined || typeof v === "object") {
                    return "";
                }
                const s = String(v);
                // Spreadsheet error tokens (#NAME?, #ERROR, #REF!, Loading…) are
                // noise from data sources that failed/aren't loaded — hide them.
                if (s.startsWith("#") || s === "Loading..." || s === "Loading…") {
                    return "";
                }
                return s;
            } catch {
                return "";
            }
        };
        const grid = [];
        for (let r = 0; r < numRows; r++) {
            const rowCells = [];
            for (let c = 0; c < numCols; c++) {
                rowCells.push(read(c, r));
            }
            grid.push(rowCells);
        }
        const rowHas = (r) => grid[r].some((v) => v !== "");

        // Split into row bands separated by blank rows.
        const bands = [];
        let start = -1;
        for (let r = 0; r < numRows; r++) {
            if (rowHas(r)) {
                if (start < 0) {
                    start = r;
                }
            } else if (start >= 0) {
                bands.push([start, r - 1]);
                start = -1;
            }
        }
        if (start >= 0) {
            bands.push([start, numRows - 1]);
        }

        const nz = (arr) => arr.filter((v) => v !== "").length;
        const outCards = [];
        for (const [r0, r1] of bands) {
            // Keep only columns that have content somewhere in this band.
            const usedCols = [];
            for (let c = 0; c < numCols; c++) {
                let has = false;
                for (let r = r0; r <= r1; r++) {
                    if (grid[r][c] !== "") {
                        has = true;
                        break;
                    }
                }
                if (has) {
                    usedCols.push(c);
                }
            }
            let block = [];
            for (let r = r0; r <= r1; r++) {
                block.push(usedCols.map((c) => grid[r][c]));
            }
            // A lone first row with a single value is the section title.
            let title = "";
            if (block.length && nz(block[0]) === 1) {
                title = block[0].find((v) => v !== "") || "";
                block = block.slice(1);
            }
            if (!block.length) {
                continue; // title-only label (e.g. a chart caption) — skip
            }
            const header = block[0];
            const body = block.slice(1).filter((r) => nz(r) > 0);
            if (!body.length && !title) {
                continue;
            }
            outCards.push({
                id: `cells-${r0}`,
                kind: "table",
                span: usedCols.length >= 5 ? 12 : 6,
                title,
                table: { columns: header.map((h) => ({ label: h || "" })), rows: body },
            });
        }
        return outCards;
    }

    _safeFigureUI(sheetId, figure) {
        try {
            const ui = this.model.getters.getFigureUI(sheetId, figure);
            return {
                x: ui.x ?? 0,
                y: ui.y ?? 0,
                width: ui.width ?? figure.width ?? 0,
                height: ui.height ?? figure.height ?? 0,
            };
        } catch {
            return { x: 0, y: 0, width: figure.width ?? 0, height: figure.height ?? 0 };
        }
    }

    /** Build a card descriptor for one figure. */
    _describe(figure, ui, contentWidth) {
        const ratio = contentWidth ? ui.width / contentWidth : 0.5;
        if (figure.tag === "chart") {
            const chartId = this.model.getters.getChartIdFromFigureId(figure.id);
            return this._describeChart(figure.id, chartId, ratio);
        }
        if (figure.tag === "carousel") {
            return this._describeCarousel(figure.id, ratio);
        }
        // image and anything else -> placeholder for now (Phase 2).
        return {
            id: figure.id,
            kind: "unsupported",
            span: this._span(ratio, "chart"),
            title: "",
            note: null,
        };
    }

    _describeChart(cardId, chartId, ratio) {
        const definition = this.model.getters.getChartDefinition(chartId);
        const title = definition.title?.text || "";
        const runtime = this.model.getters.getChartRuntime(chartId);
        if (definition.type === "scorecard") {
            return { id: cardId, kind: "kpi", span: 3, title: "", runtime };
        }
        const span = this._span(ratio, "chart");
        const spec = runtimeToCarbonChart(runtime, {
            title: "",
            seriesLabel: title,
            height: span >= 12 ? 360 : 320,
        });
        if (spec) {
            return { id: cardId, kind: "chart", span, title, spec };
        }
        // Types without a clean Carbon chart (treemap/geo/…) → ranked table.
        const table = runtimeToRankedTable(runtime);
        if (table) {
            return { id: cardId, kind: "table", span, title, table };
        }
        return { id: cardId, kind: "unsupported", span, title, note: definition.type };
    }

    _describeCarousel(cardId, ratio) {
        const carousel = this.model.getters.getCarousel(cardId);
        const items = (carousel && carousel.items) || [];
        const chartItem =
            items.find((it) => it.type === "chart" && it.chartId) || null;
        const span = this._span(ratio, "carousel");
        if (chartItem) {
            const runtime = this.model.getters.getChartRuntime(chartItem.chartId);
            const definition = this.model.getters.getChartDefinition(chartItem.chartId);
            // Read the title straight from the definition — do NOT use the
            // carousel "selected item" getters here: they lazily initialise
            // carousel state via a dispatch, which fires model "update" and, since
            // this runs inside render, would loop forever.
            const title = definition.title?.text || this._carouselTitleFromDef(definition);
            // A carousel wraps a "Top N" chart (treemap/geo) whose runtime is a
            // set of labelled values — render it the way the original does: a
            // ranked Carbon table.
            const table = runtimeToRankedTable(runtime);
            if (table) {
                return { id: cardId, kind: "table", span, title, table };
            }
            const spec = runtimeToCarbonChart(runtime, { title: "", seriesLabel: title, height: span >= 12 ? 360 : 320 });
            if (spec) {
                return { id: cardId, kind: "chart", span, title, spec };
            }
            return { id: cardId, kind: "unsupported", span, title, note: definition.type };
        }
        return { id: cardId, kind: "unsupported", span, title: "", note: null };
    }

    /** Best-effort title for a "Top N" chart from its group-by metadata. */
    _carouselTitleFromDef(definition) {
        const groupBy = definition.metaData?.groupBy?.[0] || "";
        if (groupBy.includes("country")) {
            return "Top Countries";
        }
        if (groupBy.includes("categ")) {
            return "Top Categories";
        }
        return "";
    }

    /** Column span (out of 12) from the authored width ratio and card kind. */
    _span(ratio, kind) {
        if (kind === "chart") {
            if (ratio >= 0.6) {
                return 12;
            }
            if (ratio >= 0.33) {
                return 6;
            }
            return 4;
        }
        // carousels (tables/geo/treemap) sit two-up unless very wide.
        return ratio >= 0.6 ? 12 : 6;
    }
}
