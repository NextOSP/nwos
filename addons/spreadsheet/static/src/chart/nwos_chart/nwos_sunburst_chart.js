import { registries, chartHelpers } from "@nwos/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import { NWOSChart } from "./nwos_chart";
import { isNWOSChartTypeOf } from "./chart_type";
import { onNWOSChartItemHover, onSunburstNWOSChartItemClick } from "./nwos_chart_helpers";

const { chartRegistry } = registries;

const {
    getSunburstChartDatasets,
    CHART_COMMON_OPTIONS,
    getChartLayout,
    getChartTitle,
    getSunburstShowValues,
    getSunburstChartLegend,
    getSunburstChartTooltip,
} = chartHelpers;

export class NWOSSunburstChart extends NWOSChart {
    constructor(definition, sheetId, getters) {
        super(definition, sheetId, getters);
        this.showLabels = definition.showLabels;
        this.valuesDesign = definition.valuesDesign;
        this.groupColors = definition.groupColors;
        this.pieHolePercentage = definition.pieHolePercentage;
    }

    getDefinition() {
        return {
            ...super.getDefinition(),
            pieHolePercentage: this.pieHolePercentage,
            showLabels: this.showLabels,
            valuesDesign: this.valuesDesign,
            groupColors: this.groupColors,
        };
    }
}

chartRegistry.add("nwos_sunburst", {
    match: (type) => isNWOSChartTypeOf(type, "nwos_sunburst"),
    createChart: (definition, sheetId, getters) =>
        new NWOSSunburstChart(definition, sheetId, getters),
    getChartRuntime: createNWOSChartRuntime,
    validateChartDefinition: (validator, definition) =>
        NWOSSunburstChart.validateChartDefinition(validator, definition),
    transformDefinition: (definition) => NWOSSunburstChart.transformDefinition(definition),
    getChartDefinitionFromContextCreation: () =>
        NWOSSunburstChart.getDefinitionFromContextCreation(),
    name: _t("Sunburst"),
});

function createNWOSChartRuntime(chart, getters) {
    const background = chart.background || "#FFFFFF";
    const { datasets, labels } = chart.dataSource.getHierarchicalData();

    const definition = chart.getDefinition();
    const locale = getters.getLocale();

    const chartData = {
        labels,
        dataSetsValues: datasets.map((ds) => ({ data: ds.data, label: ds.label })),
        locale,
    };

    const config = {
        type: "doughnut",
        data: {
            labels: chartData.labels,
            datasets: getSunburstChartDatasets(definition, chartData),
        },
        options: {
            ...CHART_COMMON_OPTIONS,
            cutout: chart.pieHolePercentage === undefined ? "25%" : `${chart.pieHolePercentage}%`,
            layout: getChartLayout(definition, chartData),
            plugins: {
                title: getChartTitle(definition, getters),
                legend: getSunburstChartLegend(definition, chartData),
                tooltip: getSunburstChartTooltip(definition, chartData),
                sunburstLabelsPlugin: getSunburstShowValues(definition, chartData),
                sunburstHoverPlugin: { enabled: true },
            },
            onHover: onNWOSChartItemHover(),
            onClick: onSunburstNWOSChartItemClick(getters, chart),
        },
    };

    return { background, chartJsConfig: config };
}
