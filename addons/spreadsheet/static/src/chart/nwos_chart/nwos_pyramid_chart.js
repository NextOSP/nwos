import { registries, chartHelpers } from "@nwos/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import { NWOSChart } from "./nwos_chart";
import { isNWOSChartTypeOf } from "./chart_type";
import { onNWOSChartItemHover, onNWOSChartItemClick } from "./nwos_chart_helpers";

const { chartRegistry } = registries;

const {
    CHART_COMMON_OPTIONS,
    getBarChartDatasets,
    getChartLayout,
    getChartTitle,
    getPyramidChartShowValues,
    getPyramidChartScales,
    getBarChartLegend,
    getPyramidChartTooltip,
} = chartHelpers;

export class NWOSPyramidChart extends NWOSChart {
    constructor(definition, sheetId, getters) {
        super(definition, sheetId, getters);
        this.axesDesign = definition.axesDesign;
    }

    getDefinition() {
        return {
            ...super.getDefinition(),
            axesDesign: this.axesDesign,
            horizontal: true,
            stacked: true,
        };
    }
}

chartRegistry.add("nwos_pyramid", {
    match: (type) => isNWOSChartTypeOf(type, "nwos_pyramid"),
    createChart: (definition, sheetId, getters) =>
        new NWOSPyramidChart(definition, sheetId, getters),
    getChartRuntime: createNWOSChartRuntime,
    validateChartDefinition: (validator, definition) =>
        NWOSPyramidChart.validateChartDefinition(validator, definition),
    transformDefinition: (definition) => NWOSPyramidChart.transformDefinition(definition),
    getChartDefinitionFromContextCreation: () =>
        NWOSPyramidChart.getDefinitionFromContextCreation(),
    name: _t("Pyramid"),
});

function createNWOSChartRuntime(chart, getters) {
    const background = chart.background || "#FFFFFF";
    const { datasets, labels } = chart.dataSource.getData();

    const pyramidDatasets = [];
    if (datasets[0]) {
        const pyramidData = datasets[0].data.map((value) => (value > 0 ? value : 0));
        pyramidDatasets.push({ ...datasets[0], data: pyramidData });
    }
    if (datasets[1]) {
        const pyramidData = datasets[1].data.map((value) => (value > 0 ? -value : 0));
        pyramidDatasets.push({ ...datasets[1], data: pyramidData });
    }

    const definition = chart.getDefinition();
    const locale = getters.getLocale();

    const chartData = {
        labels,
        dataSetsValues: pyramidDatasets.map((ds) => ({ data: ds.data, label: ds.label })),
        locale,
    };

    const config = {
        type: "bar",
        data: {
            labels: chartData.labels,
            datasets: getBarChartDatasets(definition, chartData),
        },
        options: {
            ...CHART_COMMON_OPTIONS,
            indexAxis: "y",
            layout: getChartLayout(definition, chartData),
            scales: getPyramidChartScales(definition, chartData),
            plugins: {
                title: getChartTitle(definition, getters),
                legend: getBarChartLegend(definition, chartData),
                tooltip: getPyramidChartTooltip(definition, chartData),
                chartShowValuesPlugin: getPyramidChartShowValues(definition, chartData),
            },
            onHover: onNWOSChartItemHover(),
            onClick: onNWOSChartItemClick(getters, chart),
        },
    };

    return { background, chartJsConfig: config };
}
