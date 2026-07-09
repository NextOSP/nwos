import { registries, chartHelpers } from "@nwos/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import { NWOSChart } from "./nwos_chart";
import { isNWOSChartTypeOf } from "./chart_type";
import { onNWOSChartItemHover, onNWOSChartItemClick } from "./nwos_chart_helpers";

const { chartRegistry } = registries;

const {
    getRadarChartDatasets,
    CHART_COMMON_OPTIONS,
    getChartLayout,
    getChartTitle,
    getChartShowValues,
    getRadarChartScales,
    getRadarChartLegend,
    getRadarChartTooltip,
} = chartHelpers;

export class NWOSRadarChart extends NWOSChart {
    constructor(definition, sheetId, getters) {
        super(definition, sheetId, getters);
        this.fillArea = definition.fillArea;
        this.hideDataMarkers = definition.hideDataMarkers;
    }

    getDefinition() {
        return {
            ...super.getDefinition(),
            fillArea: this.fillArea,
            hideDataMarkers: this.hideDataMarkers,
        };
    }
}

chartRegistry.add("nwos_radar", {
    match: (type) => isNWOSChartTypeOf(type, "nwos_radar"),
    createChart: (definition, sheetId, getters) => new NWOSRadarChart(definition, sheetId, getters),
    getChartRuntime: createNWOSChartRuntime,
    validateChartDefinition: (validator, definition) =>
        NWOSRadarChart.validateChartDefinition(validator, definition),
    transformDefinition: (definition) => NWOSRadarChart.transformDefinition(definition),
    getChartDefinitionFromContextCreation: () => NWOSRadarChart.getDefinitionFromContextCreation(),
    name: _t("Radar"),
});

function createNWOSChartRuntime(chart, getters) {
    const background = chart.background || "#FFFFFF";
    const { datasets, labels } = chart.dataSource.getData();

    const definition = chart.getDefinition();
    const locale = getters.getLocale();

    const chartData = {
        labels,
        dataSetsValues: datasets.map((ds) => ({ data: ds.data, label: ds.label })),
        locale,
    };

    const config = {
        type: "radar",
        data: {
            labels: chartData.labels,
            datasets: getRadarChartDatasets(definition, chartData),
        },
        options: {
            ...CHART_COMMON_OPTIONS,
            layout: getChartLayout(definition, chartData),
            scales: getRadarChartScales(definition, chartData),
            plugins: {
                title: getChartTitle(definition, getters),
                legend: getRadarChartLegend(definition, chartData),
                tooltip: getRadarChartTooltip(definition, chartData),
                chartShowValuesPlugin: getChartShowValues(definition, chartData),
            },
            onHover: onNWOSChartItemHover(),
            onClick: onNWOSChartItemClick(getters, chart),
        },
    };

    return { background, chartJsConfig: config };
}
