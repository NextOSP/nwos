import * as spreadsheet from "@nwos/o-spreadsheet";
import { NWOSChartCorePlugin } from "./plugins/nwos_chart_core_plugin";
import { ChartNWOSMenuPlugin } from "./plugins/chart_nwos_menu_plugin";
import { NWOSChartCoreViewPlugin } from "./plugins/nwos_chart_core_view_plugin";
import { _t } from "@web/core/l10n/translation";
import { chartNWOSMenuPlugin } from "./nwos_menu/nwos_menu_chartjs_plugin";
import { getNWOSChartTypeAliases, isNWOSChartTypeOf } from "./nwos_chart/chart_type";

const { chartComponentRegistry, chartSubtypeRegistry, chartJsExtensionRegistry } =
    spreadsheet.registries;
const { ChartJsComponent, ZoomableChartJsComponent } = spreadsheet.components;

function addChartComponent(chartType, component) {
    for (const type of getNWOSChartTypeAliases(chartType)) {
        chartComponentRegistry.add(type, component);
    }
}

addChartComponent("nwos_bar", ZoomableChartJsComponent);
addChartComponent("nwos_line", ZoomableChartJsComponent);
addChartComponent("nwos_pie", ChartJsComponent);
addChartComponent("nwos_radar", ChartJsComponent);
addChartComponent("nwos_sunburst", ChartJsComponent);
addChartComponent("nwos_treemap", ChartJsComponent);
addChartComponent("nwos_waterfall", ZoomableChartJsComponent);
addChartComponent("nwos_pyramid", ChartJsComponent);
addChartComponent("nwos_scatter", ChartJsComponent);
addChartComponent("nwos_combo", ZoomableChartJsComponent);
addChartComponent("nwos_geo", ChartJsComponent);
addChartComponent("nwos_funnel", ChartJsComponent);

chartSubtypeRegistry.add("nwos_line", {
    matcher: (definition) =>
        isNWOSChartTypeOf(definition.type, "nwos_line") &&
        !definition.stacked &&
        !definition.fillArea,
    subtypeDefinition: { stacked: false, fillArea: false },
    displayName: _t("Line"),
    chartSubtype: "nwos_line",
    chartType: "nwos_line",
    category: "line",
    preview: "o-spreadsheet-ChartPreview.LINE_CHART",
});
chartSubtypeRegistry.add("nwos_stacked_line", {
    matcher: (definition) =>
        isNWOSChartTypeOf(definition.type, "nwos_line") &&
        definition.stacked &&
        !definition.fillArea,
    subtypeDefinition: { stacked: true, fillArea: false },
    displayName: _t("Stacked Line"),
    chartSubtype: "nwos_stacked_line",
    chartType: "nwos_line",
    category: "line",
    preview: "o-spreadsheet-ChartPreview.STACKED_LINE_CHART",
});
chartSubtypeRegistry.add("nwos_area", {
    matcher: (definition) =>
        isNWOSChartTypeOf(definition.type, "nwos_line") &&
        !definition.stacked &&
        definition.fillArea,
    subtypeDefinition: { stacked: false, fillArea: true },
    displayName: _t("Area"),
    chartSubtype: "nwos_area",
    chartType: "nwos_line",
    category: "area",
    preview: "o-spreadsheet-ChartPreview.AREA_CHART",
});
chartSubtypeRegistry.add("nwos_stacked_area", {
    matcher: (definition) =>
        isNWOSChartTypeOf(definition.type, "nwos_line") &&
        definition.stacked &&
        definition.fillArea,
    subtypeDefinition: { stacked: true, fillArea: true },
    displayName: _t("Stacked Area"),
    chartSubtype: "nwos_stacked_area",
    chartType: "nwos_line",
    category: "area",
    preview: "o-spreadsheet-ChartPreview.STACKED_AREA_CHART",
});
chartSubtypeRegistry.add("nwos_bar", {
    matcher: (definition) =>
        isNWOSChartTypeOf(definition.type, "nwos_bar") &&
        !definition.stacked &&
        !definition.horizontal,
    subtypeDefinition: { stacked: false, horizontal: false },
    displayName: _t("Column"),
    chartSubtype: "nwos_bar",
    chartType: "nwos_bar",
    category: "column",
    preview: "o-spreadsheet-ChartPreview.COLUMN_CHART",
});
chartSubtypeRegistry.add("nwos_stacked_bar", {
    matcher: (definition) =>
        isNWOSChartTypeOf(definition.type, "nwos_bar") &&
        definition.stacked &&
        !definition.horizontal,
    subtypeDefinition: { stacked: true, horizontal: false },
    displayName: _t("Stacked Column"),
    chartSubtype: "nwos_stacked_bar",
    chartType: "nwos_bar",
    category: "column",
    preview: "o-spreadsheet-ChartPreview.STACKED_COLUMN_CHART",
});
chartSubtypeRegistry.add("nwos_horizontal_bar", {
    matcher: (definition) =>
        isNWOSChartTypeOf(definition.type, "nwos_bar") &&
        !definition.stacked &&
        definition.horizontal,
    subtypeDefinition: { stacked: false, horizontal: true },
    displayName: _t("Bar"),
    chartSubtype: "nwos_horizontal_bar",
    chartType: "nwos_bar",
    category: "bar",
    preview: "o-spreadsheet-ChartPreview.BAR_CHART",
});
chartSubtypeRegistry.add("nwos_horizontal_stacked_bar", {
    matcher: (definition) =>
        isNWOSChartTypeOf(definition.type, "nwos_bar") &&
        definition.stacked &&
        definition.horizontal,
    subtypeDefinition: { stacked: true, horizontal: true },
    displayName: _t("Stacked Bar"),
    chartSubtype: "nwos_horizontal_stacked_bar",
    chartType: "nwos_bar",
    category: "bar",
    preview: "o-spreadsheet-ChartPreview.STACKED_BAR_CHART",
});
chartSubtypeRegistry.add("nwos_combo", {
    displayName: _t("Combo"),
    chartSubtype: "nwos_combo",
    chartType: "nwos_combo",
    category: "line",
    preview: "o-spreadsheet-ChartPreview.COMBO_CHART",
});
chartSubtypeRegistry.add("nwos_pie", {
    displayName: _t("Pie"),
    matcher: (definition) =>
        isNWOSChartTypeOf(definition.type, "nwos_pie") && !definition.isDoughnut,
    subtypeDefinition: { isDoughnut: false },
    chartSubtype: "nwos_pie",
    chartType: "nwos_pie",
    category: "pie",
    preview: "o-spreadsheet-ChartPreview.PIE_CHART",
});
chartSubtypeRegistry.add("nwos_doughnut", {
    matcher: (definition) =>
        isNWOSChartTypeOf(definition.type, "nwos_pie") && definition.isDoughnut,
    subtypeDefinition: { isDoughnut: true },
    displayName: _t("Doughnut"),
    chartSubtype: "nwos_doughnut",
    chartType: "nwos_pie",
    category: "pie",
    preview: "o-spreadsheet-ChartPreview.DOUGHNUT_CHART",
});
chartSubtypeRegistry.add("nwos_scatter", {
    displayName: _t("Scatter"),
    chartType: "nwos_scatter",
    chartSubtype: "nwos_scatter",
    category: "misc",
    preview: "o-spreadsheet-ChartPreview.SCATTER_CHART",
});
chartSubtypeRegistry.add("nwos_waterfall", {
    displayName: _t("Waterfall"),
    chartSubtype: "nwos_waterfall",
    chartType: "nwos_waterfall",
    category: "misc",
    preview: "o-spreadsheet-ChartPreview.WATERFALL_CHART",
});
chartSubtypeRegistry.add("nwos_pyramid", {
    displayName: _t("Population Pyramid"),
    chartSubtype: "nwos_pyramid",
    chartType: "nwos_pyramid",
    category: "misc",
    preview: "o-spreadsheet-ChartPreview.POPULATION_PYRAMID_CHART",
});
chartSubtypeRegistry.add("nwos_radar", {
    matcher: (definition) =>
        isNWOSChartTypeOf(definition.type, "nwos_radar") && !definition.fillArea,
    displayName: _t("Radar"),
    chartSubtype: "nwos_radar",
    chartType: "nwos_radar",
    subtypeDefinition: { fillArea: false },
    category: "misc",
    preview: "o-spreadsheet-ChartPreview.RADAR_CHART",
});
chartSubtypeRegistry.add("nwos_filled_radar", {
    matcher: (definition) =>
        isNWOSChartTypeOf(definition.type, "nwos_radar") && !!definition.fillArea,
    displayName: _t("Filled Radar"),
    chartType: "nwos_radar",
    chartSubtype: "nwos_filled_radar",
    subtypeDefinition: { fillArea: true },
    category: "misc",
    preview: "o-spreadsheet-ChartPreview.FILLED_RADAR_CHART",
});
chartSubtypeRegistry.add("nwos_geo", {
    displayName: _t("Geo chart"),
    chartType: "nwos_geo",
    chartSubtype: "nwos_geo",
    category: "misc",
    preview: "o-spreadsheet-ChartPreview.GEO_CHART",
});
chartSubtypeRegistry.add("nwos_funnel", {
    matcher: (definition) => isNWOSChartTypeOf(definition.type, "nwos_funnel"),
    displayName: _t("Funnel"),
    chartType: "nwos_funnel",
    chartSubtype: "nwos_funnel",
    subtypeDefinition: { cumulative: true },
    category: "misc",
    preview: "o-spreadsheet-ChartPreview.FUNNEL_CHART",
});
chartSubtypeRegistry.add("nwos_treemap", {
    displayName: _t("Treemap"),
    chartType: "nwos_treemap",
    chartSubtype: "nwos_treemap",
    category: "hierarchical",
    preview: "o-spreadsheet-ChartPreview.TREE_MAP_CHART",
});
chartSubtypeRegistry.add("nwos_sunburst", {
    displayName: _t("Sunburst"),
    chartType: "nwos_sunburst",
    chartSubtype: "nwos_sunburst",
    category: "hierarchical",
    preview: "o-spreadsheet-ChartPreview.SUNBURST_CHART",
});

chartJsExtensionRegistry.add("chartNWOSMenuPlugin", {
    register: (Chart) => Chart.register(chartNWOSMenuPlugin),
    unregister: (Chart) => Chart.unregister(chartNWOSMenuPlugin),
});

export { NWOSChartCorePlugin, ChartNWOSMenuPlugin, NWOSChartCoreViewPlugin };
