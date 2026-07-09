import { registries, chartHelpers } from "@nwos/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import { NWOSChart } from "./nwos_chart";
import { isNWOSChartTypeOf } from "./chart_type";
import { onNWOSChartItemHover, onWaterfallNWOSChartItemClick } from "./nwos_chart_helpers";

const { chartRegistry } = registries;

const {
    CHART_COMMON_OPTIONS,
    getChartLayout,
    getChartTitle,
    getWaterfallChartShowValues,
    getWaterfallChartScales,
    getWaterfallChartLegend,
    getWaterfallChartTooltip,
    getWaterfallDatasetAndLabels,
} = chartHelpers;

export class NWOSWaterfallChart extends NWOSChart {
    constructor(definition, sheetId, getters) {
        super(definition, sheetId, getters);
        this.verticalAxisPosition = definition.verticalAxisPosition ?? "left";
        this.showConnectorLines = definition.showConnectorLines ?? true;
        this.positiveValuesColor = definition.positiveValuesColor;
        this.negativeValuesColor = definition.negativeValuesColor;
        this.subTotalValuesColor = definition.subTotalValuesColor;
        this.firstValueAsSubtotal = definition.firstValueAsSubtotal ?? false;
        this.showSubTotals = definition.showSubTotals ?? false;
        this.axesDesign = definition.axesDesign;
        this.zoomable = definition.zoomable ?? false;
    }

    getDefinition() {
        return {
            ...super.getDefinition(),
            verticalAxisPosition: this.verticalAxisPosition,
            showConnectorLines: this.showConnectorLines,
            firstValueAsSubtotal: this.firstValueAsSubtotal,
            showSubTotals: this.showSubTotals,
            positiveValuesColor: this.positiveValuesColor,
            negativeValuesColor: this.negativeValuesColor,
            subTotalValuesColor: this.subTotalValuesColor,
            axesDesign: this.axesDesign,
            zoomable: this.zoomable,
        };
    }
}

chartRegistry.add("nwos_waterfall", {
    match: (type) => isNWOSChartTypeOf(type, "nwos_waterfall"),
    createChart: (definition, sheetId, getters) =>
        new NWOSWaterfallChart(definition, sheetId, getters),
    getChartRuntime: createNWOSChartRuntime,
    validateChartDefinition: (validator, definition) =>
        NWOSWaterfallChart.validateChartDefinition(validator, definition),
    transformDefinition: (definition) => NWOSWaterfallChart.transformDefinition(definition),
    getChartDefinitionFromContextCreation: () =>
        NWOSWaterfallChart.getDefinitionFromContextCreation(),
    name: _t("Waterfall"),
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

    const chartJSData = getWaterfallDatasetAndLabels(definition, chartData);

    const config = {
        type: "bar",
        data: { labels: chartJSData.labels, datasets: chartJSData.datasets },
        options: {
            ...CHART_COMMON_OPTIONS,
            layout: getChartLayout(definition, chartData),
            scales: getWaterfallChartScales(definition, chartData),
            plugins: {
                title: getChartTitle(definition, getters),
                legend: getWaterfallChartLegend(definition, chartData),
                tooltip: getWaterfallChartTooltip(definition, chartData),
                chartShowValuesPlugin: getWaterfallChartShowValues(definition, chartData),
                waterfallLinesPlugin: { showConnectorLines: definition.showConnectorLines },
            },
            onHover: onNWOSChartItemHover(),
            onClick: onWaterfallNWOSChartItemClick(getters, chart),
        },
    };

    return { background, chartJsConfig: config };
}
