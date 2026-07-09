import { registries, chartHelpers } from "@nwos/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import { NWOSChart } from "./nwos_chart";
import { isNWOSChartTypeOf } from "./chart_type";
import { onNWOSChartItemClick, onNWOSChartItemHover } from "./nwos_chart_helpers";

const { chartRegistry } = registries;

const {
    getBarChartDatasets,
    CHART_COMMON_OPTIONS,
    getChartLayout,
    getBarChartScales,
    getBarChartTooltip,
    getChartTitle,
    getBarChartLegend,
    getChartShowValues,
    getTrendDatasetForBarChart,
    getTopPaddingForDashboard,
} = chartHelpers;

export class NWOSBarChart extends NWOSChart {
    constructor(definition, sheetId, getters) {
        super(definition, sheetId, getters);
        this.verticalAxisPosition = definition.verticalAxisPosition;
        this.stacked = definition.stacked;
        this.axesDesign = definition.axesDesign;
        this.horizontal = definition.horizontal;
        this.zoomable = definition.zoomable;
    }

    getDefinition() {
        return {
            ...super.getDefinition(),
            verticalAxisPosition: this.verticalAxisPosition,
            stacked: this.stacked,
            axesDesign: this.axesDesign,
            trend: this.trend,
            horizontal: this.horizontal,
            zoomable: this.zoomable,
        };
    }
}

chartRegistry.add("nwos_bar", {
    match: (type) => isNWOSChartTypeOf(type, "nwos_bar"),
    createChart: (definition, sheetId, getters) => new NWOSBarChart(definition, sheetId, getters),
    getChartRuntime: createNWOSChartRuntime,
    validateChartDefinition: (validator, definition) =>
        NWOSBarChart.validateChartDefinition(validator, definition),
    transformDefinition: (definition) => NWOSBarChart.transformDefinition(definition),
    getChartDefinitionFromContextCreation: () => NWOSBarChart.getDefinitionFromContextCreation(),
    name: _t("Bar"),
});

function createNWOSChartRuntime(chart, getters) {
    const background = chart.background || "#FFFFFF";
    const { datasets, labels } = chart.dataSource.getData();
    const definition = chart.getDefinition();

    const trendDataSetsValues = datasets.map((dataset, index) => {
        const trend = definition.dataSets[index]?.trend;
        return !trend?.display || chart.horizontal
            ? undefined
            : getTrendDatasetForBarChart(trend, dataset.data);
    });

    const chartData = {
        labels,
        dataSetsValues: datasets.map((ds) => ({ data: ds.data, label: ds.label })),
        locale: getters.getLocale(),
        trendDataSetsValues,
        topPadding: getTopPaddingForDashboard(definition, getters),
    };

    const config = {
        type: "bar",
        data: {
            labels: chartData.labels,
            datasets: getBarChartDatasets(definition, chartData),
        },
        options: {
            ...CHART_COMMON_OPTIONS,
            indexAxis: chart.horizontal ? "y" : "x",
            layout: getChartLayout(definition, chartData),
            scales: getBarChartScales(definition, chartData),
            plugins: {
                title: getChartTitle(definition, getters),
                legend: getBarChartLegend(definition, chartData),
                tooltip: getBarChartTooltip(definition, chartData),
                chartShowValuesPlugin: getChartShowValues(definition, chartData),
            },
            onHover: onNWOSChartItemHover(),
            onClick: onNWOSChartItemClick(getters, chart),
        },
    };

    return { background, chartJsConfig: config };
}
