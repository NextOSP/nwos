import { registries, chartHelpers } from "@nwos/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import { NWOSChart } from "./nwos_chart";
import { isNWOSChartTypeOf } from "./chart_type";
import { onGeoNWOSChartItemHover, onGeoNWOSChartItemClick } from "./nwos_chart_helpers";

const { chartRegistry } = registries;

const {
    getGeoChartDatasets,
    CHART_COMMON_OPTIONS,
    getChartLayout,
    getChartTitle,
    getGeoChartScales,
    getGeoChartTooltip,
} = chartHelpers;

export class NWOSGeoChart extends NWOSChart {
    constructor(definition, sheetId, getters) {
        super(definition, sheetId, getters);
        this.colorScale = definition.colorScale;
        this.missingValueColor = definition.missingValueColor;
        this.region = definition.region;
    }

    getDefinition() {
        return {
            ...super.getDefinition(),
            colorScale: this.colorScale,
            missingValueColor: this.missingValueColor,
            region: this.region,
        };
    }
}

chartRegistry.add("nwos_geo", {
    match: (type) => isNWOSChartTypeOf(type, "nwos_geo"),
    createChart: (definition, sheetId, getters) => new NWOSGeoChart(definition, sheetId, getters),
    getChartRuntime: createNWOSChartRuntime,
    validateChartDefinition: (validator, definition) =>
        NWOSGeoChart.validateChartDefinition(validator, definition),
    transformDefinition: (definition) => NWOSGeoChart.transformDefinition(definition),
    getChartDefinitionFromContextCreation: () => NWOSGeoChart.getDefinitionFromContextCreation(),
    name: _t("Geo"),
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
        availableRegions: getters.getGeoChartAvailableRegions(),
        geoFeatureNameToId: getters.geoFeatureNameToId,
        getGeoJsonFeatures: getters.getGeoJsonFeatures,
    };

    const config = {
        type: "choropleth",
        data: {
            datasets: getGeoChartDatasets(definition, chartData),
        },
        options: {
            ...CHART_COMMON_OPTIONS,
            layout: getChartLayout(definition, chartData),
            scales: getGeoChartScales(definition, chartData),
            plugins: {
                title: getChartTitle(definition, getters),
                tooltip: getGeoChartTooltip(definition, chartData),
                legend: { display: false },
            },
            onHover: onGeoNWOSChartItemHover(),
            onClick: onGeoNWOSChartItemClick(getters, chart),
        },
    };

    return { background, chartJsConfig: config };
}
