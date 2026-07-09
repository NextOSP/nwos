import { registries, chartHelpers } from "@nwos/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import { NWOSChart } from "./nwos_chart";
import { isNWOSChartTypeOf } from "./chart_type";
import { onNWOSChartItemHover, onNWOSChartItemClick } from "./nwos_chart_helpers";

const { chartRegistry } = registries;

const {
    getScatterChartDatasets,
    CHART_COMMON_OPTIONS,
    getChartLayout,
    getScatterChartScales,
    getLineChartTooltip,
    getChartTitle,
    getScatterChartLegend,
    getChartShowValues,
    getTrendDatasetForLineChart,
} = chartHelpers;

export class NWOSScatterChart extends NWOSChart {
    constructor(definition, sheetId, getters) {
        super(definition, sheetId, getters);
        this.verticalAxisPosition = definition.verticalAxisPosition;
        this.axesDesign = definition.axesDesign;
    }

    getDefinition() {
        return {
            ...super.getDefinition(),
            verticalAxisPosition: this.verticalAxisPosition,
            axesDesign: this.axesDesign,
        };
    }
}

chartRegistry.add("nwos_scatter", {
    match: (type) => isNWOSChartTypeOf(type, "nwos_scatter"),
    createChart: (definition, sheetId, getters) =>
        new NWOSScatterChart(definition, sheetId, getters),
    getChartRuntime: createNWOSChartRuntime,
    validateChartDefinition: (validator, definition) =>
        NWOSScatterChart.validateChartDefinition(validator, definition),
    transformDefinition: (definition) => NWOSScatterChart.transformDefinition(definition),
    getChartDefinitionFromContextCreation: () =>
        NWOSScatterChart.getDefinitionFromContextCreation(),
    name: _t("Scatter"),
});

function createNWOSChartRuntime(chart, getters) {
    const background = chart.background || "#FFFFFF";
    const { datasets, labels } = chart.dataSource.getData();

    const definition = chart.getDefinition();
    const locale = getters.getLocale();

    const trendDataSetsValues = datasets.map((dataset, index) => {
        const trend = definition.dataSets[index]?.trend;
        return !trend?.display
            ? undefined
            : getTrendDatasetForLineChart(trend, dataset.data, labels, "category", locale);
    });

    const chartData = {
        labels,
        dataSetsValues: datasets.map((ds) => ({ data: ds.data, label: ds.label })),
        locale,
        trendDataSetsValues,
        axisType: definition.axisType || "category",
    };

    const config = {
        type: "line",
        data: {
            labels: chartData.labels,
            datasets: getScatterChartDatasets(definition, chartData),
        },
        options: {
            ...CHART_COMMON_OPTIONS,
            layout: getChartLayout(definition, chartData),
            scales: getScatterChartScales(definition, chartData),
            plugins: {
                title: getChartTitle(definition, getters),
                legend: getScatterChartLegend(definition, chartData),
                tooltip: getLineChartTooltip(definition, chartData),
                chartShowValuesPlugin: getChartShowValues(definition, chartData),
            },
            onHover: onNWOSChartItemHover(),
            onClick: onNWOSChartItemClick(getters, chart),
        },
    };

    return { background, chartJsConfig: config };
}
