import { registries, chartHelpers } from "@nwos/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import { NWOSChart } from "./nwos_chart";
import { isNWOSChartTypeOf } from "./chart_type";
import { onNWOSChartItemHover, onNWOSChartItemClick } from "./nwos_chart_helpers";

const { chartRegistry } = registries;

const {
    getFunnelChartDatasets,
    CHART_COMMON_OPTIONS,
    getChartLayout,
    getChartTitle,
    getChartShowValues,
    getFunnelChartScales,
    getFunnelChartTooltip,
    makeDatasetsCumulative,
} = chartHelpers;

export class NWOSFunnelChart extends NWOSChart {
    constructor(definition, sheetId, getters) {
        super(definition, sheetId, getters);
        this.cumulative = definition.cumulative;
        this.funnelColors = definition.funnelColors;
    }

    getDefinition() {
        return {
            ...super.getDefinition(),
            cumulative: this.cumulative,
            funnelColors: this.funnelColors,
        };
    }
}

chartRegistry.add("nwos_funnel", {
    match: (type) => isNWOSChartTypeOf(type, "nwos_funnel"),
    createChart: (definition, sheetId, getters) =>
        new NWOSFunnelChart(definition, sheetId, getters),
    getChartRuntime: createNWOSChartRuntime,
    validateChartDefinition: (validator, definition) =>
        NWOSFunnelChart.validateChartDefinition(validator, definition),
    transformDefinition: (definition) => NWOSFunnelChart.transformDefinition(definition),
    getChartDefinitionFromContextCreation: () => NWOSFunnelChart.getDefinitionFromContextCreation(),
    name: _t("Funnel"),
});

function createNWOSChartRuntime(chart, getters) {
    const definition = chart.getDefinition();
    const background = chart.background || "#FFFFFF";
    let { datasets, labels } = chart.dataSource.getData();
    if (definition.cumulative) {
        datasets = makeDatasetsCumulative(datasets, "desc");
    }

    const locale = getters.getLocale();

    const chartData = {
        labels,
        dataSetsValues: datasets.map((ds) => ({ data: ds.data, label: ds.label })),
        locale,
    };

    const config = {
        type: "funnel",
        data: {
            labels: chartData.labels,
            datasets: getFunnelChartDatasets(definition, chartData),
        },
        options: {
            ...CHART_COMMON_OPTIONS,
            indexAxis: "y",
            layout: getChartLayout(definition, chartData),
            scales: getFunnelChartScales(definition, chartData),
            plugins: {
                title: getChartTitle(definition, getters),
                legend: { display: false },
                tooltip: getFunnelChartTooltip(definition, chartData),
                chartShowValuesPlugin: getChartShowValues(definition, chartData),
            },
            onHover: onNWOSChartItemHover(),
            onClick: onNWOSChartItemClick(getters, chart),
        },
    };

    return { background, chartJsConfig: config };
}
