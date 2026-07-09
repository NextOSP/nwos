export const LEGACY_NWOS_CHART_TYPE_ALIASES = {
    flectra_bar: "nwos_bar",
    flectra_line: "nwos_line",
    flectra_pie: "nwos_pie",
    flectra_radar: "nwos_radar",
    flectra_sunburst: "nwos_sunburst",
    flectra_treemap: "nwos_treemap",
    flectra_waterfall: "nwos_waterfall",
    flectra_pyramid: "nwos_pyramid",
    flectra_scatter: "nwos_scatter",
    flectra_combo: "nwos_combo",
    flectra_geo: "nwos_geo",
    flectra_funnel: "nwos_funnel",
    odoo_bar: "nwos_bar",
    odoo_line: "nwos_line",
    odoo_pie: "nwos_pie",
    odoo_radar: "nwos_radar",
    odoo_sunburst: "nwos_sunburst",
    odoo_treemap: "nwos_treemap",
    odoo_waterfall: "nwos_waterfall",
    odoo_pyramid: "nwos_pyramid",
    odoo_scatter: "nwos_scatter",
    odoo_combo: "nwos_combo",
    odoo_geo: "nwos_geo",
    odoo_funnel: "nwos_funnel",
};

export function normalizeNWOSChartType(type) {
    return LEGACY_NWOS_CHART_TYPE_ALIASES[type] || type;
}

export function isNWOSChartType(type) {
    return normalizeNWOSChartType(type)?.startsWith("nwos_");
}

export function isNWOSChartTypeOf(type, chartType) {
    return normalizeNWOSChartType(type) === chartType;
}

export function getNWOSChartTypeAliases(chartType) {
    const aliases = Object.entries(LEGACY_NWOS_CHART_TYPE_ALIASES)
        .filter(([, normalizedType]) => normalizedType === chartType)
        .map(([legacyType]) => legacyType);
    return [chartType, ...aliases];
}
