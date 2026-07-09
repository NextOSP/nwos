import { _t } from "@web/core/l10n/translation";
import { buildColorScale } from "./carbon_palette";

/**
 * Coerce a Chart.js datapoint (number, {y}, {value}, or parseable string) into a
 * finite number, or null when it isn't a value.
 */
function toNumber(v) {
    if (v === null || v === undefined) {
        return null;
    }
    if (typeof v === "object") {
        v = v.y ?? v.value ?? v.v ?? null;
    }
    const n = typeof v === "number" ? v : parseFloat(v);
    return Number.isFinite(n) ? n : null;
}

const IGNORED_CHART_TYPES = new Set(["scorecard"]);

function formatNumber(n) {
    if (!Number.isFinite(n)) {
        return "";
    }
    return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

/**
 * Turn a chart runtime (labels + one dataset of values) into a ranked Carbon
 * table: Name / Amount / Ratio, sorted descending by value. Used to render the
 * geo/treemap carousels (Top Countries / Top Categories) the way the original
 * dashboard shows them — as tables.
 *
 * @returns {{columns, rows} | null}
 */
export function runtimeToRankedTable(runtime, { nameLabel = "Name", valueLabel = "Amount" } = {}) {
    const cfg = runtime && runtime.chartJsConfig;
    if (!cfg || !cfg.data) {
        return null;
    }
    const labels = cfg.data.labels || [];
    const dataset = (cfg.data.datasets || [])[0];
    if (!dataset || !dataset.data || !labels.length) {
        return null;
    }
    const pairs = labels
        .map((label, i) => ({ name: String(label), value: toNumber(dataset.data[i]) ?? 0 }))
        .sort((a, b) => b.value - a.value);
    const total = pairs.reduce((s, p) => s + (p.value || 0), 0);
    const rows = pairs.map((p) => [
        p.name,
        formatNumber(p.value),
        total ? `${Math.round((p.value / total) * 100)}%` : "—",
    ]);
    return {
        columns: [
            { label: nameLabel },
            { label: valueLabel, numeric: true },
            { label: "Ratio", numeric: true },
        ],
        rows,
    };
}

/**
 * Chart.js config `type` -> @carbon/charts class name for the types that map
 * cleanly. Types absent here (treemap, choropleth, radar, ...) are returned as
 * `null` so the caller can fall back.
 */
function carbonClassFor(type, { datasetCount, stacked, area }) {
    switch (type) {
        case "line":
            return area ? "AreaChart" : "LineChart";
        case "bar":
            if (stacked) {
                return "StackedBarChart";
            }
            return datasetCount > 1 ? "GroupedBarChart" : "SimpleBarChart";
        case "pie":
            return "PieChart";
        case "doughnut":
            return "DonutChart";
        default:
            return null;
    }
}

/**
 * Convert an o-spreadsheet chart runtime (`getChartRuntime(chartId)`, which
 * carries a `chartJsConfig`) into everything a @carbon/charts chart needs.
 *
 * @param {{chartJsConfig: {type, data, options}}} runtime
 * @param {string} [title]
 * @param {number|string} [height]
 * @returns {{className: string, data: object[], options: object} | null}
 *          null when the chart type has no clean Carbon mapping (caller falls back)
 */
// Generic measure labels that the odoo chart runtime emits for a single series
// ("Count", "Sum", …) — unhelpful in a tooltip, so we swap them for the card title.
const GENERIC_SERIES_LABELS = new Set(["count", "sum", "__count", "", "value"]);

export function runtimeToCarbonChart(runtime, { title = "", height = "100%", seriesLabel = "" } = {}) {
    const cfg = runtime && runtime.chartJsConfig;
    if (!cfg || !cfg.data) {
        return null;
    }
    const type = cfg.type;
    if (IGNORED_CHART_TYPES.has(type)) {
        return null;
    }
    const labels = cfg.data.labels || [];
    const datasets = (cfg.data.datasets || []).filter((ds) => ds && ds.data);
    if (!datasets.length) {
        return null;
    }

    const scales = (cfg.options && cfg.options.scales) || {};
    const stacked = Boolean(
        (scales.x && scales.x.stacked) || (scales.y && scales.y.stacked)
    );
    const area = datasets.length === 1 && Boolean(datasets[0].fill);

    const className = carbonClassFor(type, {
        datasetCount: datasets.length,
        stacked,
        area,
    });
    if (!className) {
        return null;
    }

    const isCircular = className === "PieChart" || className === "DonutChart";
    let data;
    let groups;

    if (isCircular) {
        // One slice per label; a single implicit group.
        data = labels
            .map((label, i) => ({
                group: String(label),
                value: toNumber(datasets[0].data[i]) ?? 0,
            }))
            .filter((d) => d.group);
        groups = data.map((d) => d.group);
    } else {
        // One point per (dataset, label): group = series, key = x, value = y.
        groups = datasets.map((ds, i) => {
            const label = ds.label || "";
            // Single-series charts often carry a meaningless "Count"/"Sum" label —
            // use the chart title so the legend/tooltip reads clearly.
            if (datasets.length === 1 && (GENERIC_SERIES_LABELS.has(label.toLowerCase()) || !label)) {
                return seriesLabel || label || _t("Value");
            }
            return label || _t("Series %s", i + 1);
        });
        data = [];
        labels.forEach((label, i) => {
            datasets.forEach((ds, di) => {
                const value = toNumber(ds.data[i]);
                if (value !== null) {
                    data.push({ group: groups[di], key: String(label), value });
                }
            });
        });
    }

    if (!data.length) {
        return null;
    }

    const options = {
        title: title || undefined,
        height: typeof height === "number" ? `${height}px` : height,
        resizable: true,
        toolbar: { enabled: false },
        color: { scale: buildColorScale(groups) },
        legend: { enabled: groups.length > 1 },
    };
    if (!isCircular) {
        options.axes = {
            bottom: { mapsTo: "key", scaleType: "labels" },
            left: { mapsTo: "value", scaleType: "linear" },
        };
        if (stacked) {
            options.axes.left.stacked = true;
        }
    }
    if (className === "AreaChart" || className === "LineChart") {
        options.points = { enabled: labels.length <= 24 };
    }

    return { className, data, options };
}
