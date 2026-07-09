import { checkFilterFieldMatching } from "@spreadsheet/global_filters/helpers";
import { CommandResult } from "../../o_spreadsheet/cancelled_reason";
import { Domain } from "@web/core/domain";
import { NWOSCorePlugin } from "@spreadsheet/plugins";
import { _t } from "@web/core/l10n/translation";
import { isNWOSChartType, normalizeNWOSChartType } from "../nwos_chart/chart_type";

/**
 * @typedef {Object} Chart
 * @property {Object} fieldMatching
 *
 * @typedef {import("@spreadsheet").FieldMatching} FieldMatching
 */

const CHART_PLACEHOLDER_DISPLAY_NAME = {
    nwos_bar: _t("NWOS Bar Chart"),
    nwos_line: _t("NWOS Line Chart"),
    nwos_pie: _t("NWOS Pie Chart"),
    nwos_radar: _t("NWOS Radar Chart"),
    nwos_geo: _t("NWOS Geo Chart"),
    nwos_treemap: _t("NWOS Treemap Chart"),
    nwos_sunburst: _t("NWOS Sunburst Chart"),
    nwos_waterfall: _t("NWOS Waterfall Chart"),
    nwos_pyramid: _t("NWOS Pyramid Chart"),
    nwos_scatter: _t("NWOS Scatter Chart"),
    nwos_combo: _t("NWOS Combo Chart"),
    nwos_funnel: _t("NWOS Funnel Chart"),
};

export class NWOSChartCorePlugin extends NWOSCorePlugin {
    static getters = /** @type {const} */ ([
        "getNWOSChartIds",
        "getChartFieldMatch",
        "getNWOSChartDisplayName",
        "getNWOSChartFieldMatching",
        "getChartGranularity",
    ]);

    constructor(config) {
        super(config);

        /** @type {Object.<string, Chart>} */
        this.charts = {};
    }

    allowDispatch(cmd) {
        switch (cmd.type) {
            case "ADD_GLOBAL_FILTER":
            case "EDIT_GLOBAL_FILTER":
                if (cmd.chart) {
                    return checkFilterFieldMatching(cmd.chart);
                }
        }
        return CommandResult.Success;
    }

    /**
     * Handle a spreadsheet command
     *
     * @param {Object} cmd Command
     */
    handle(cmd) {
        switch (cmd.type) {
            case "CREATE_CHART": {
                if (isNWOSChartType(cmd.definition.type)) {
                    this._addNWOSChart(cmd.chartId);
                }
                break;
            }
            case "DELETE_CHART": {
                const charts = { ...this.charts };
                delete charts[cmd.chartId];
                this.history.update("charts", charts);
                break;
            }
            case "REMOVE_GLOBAL_FILTER":
                this._onFilterDeletion(cmd.id);
                break;
            case "ADD_GLOBAL_FILTER":
            case "EDIT_GLOBAL_FILTER":
                if (cmd.chart) {
                    this._setNWOSChartFieldMatching(cmd.filter.id, cmd.chart);
                }
                break;
        }
    }

    // -------------------------------------------------------------------------
    // Getters
    // -------------------------------------------------------------------------

    /**
     * Get all the nwos chart ids
     * @returns {Array<string>}
     */
    getNWOSChartIds() {
        return Object.keys(this.charts);
    }

    /**
     * @param {string} chartId
     * @returns {string}
     */
    getChartFieldMatch(chartId) {
        return this.charts[chartId].fieldMatching;
    }

    /**
     *
     * @param {string} chartId
     * @returns {string}
     */
    getNWOSChartDisplayName(chartId) {
        const { title, type } = this.getters.getChart(chartId);
        const name = title.text || CHART_PLACEHOLDER_DISPLAY_NAME[normalizeNWOSChartType(type)];
        return `(#${this.getNWOSChartIds().indexOf(chartId) + 1}) ${name}`;
    }

    getChartGranularity(chartId) {
        const definition = this.getters.getChartDefinition(chartId);
        if (isNWOSChartType(definition.type) && definition.metaData.groupBy.length) {
            const horizontalAxis = definition.metaData.groupBy[0];
            const [fieldName, granularity] = horizontalAxis.split(":");
            return { fieldName, granularity };
        }
        return null;
    }

    /**
     * Import the charts
     *
     * @param {Object} data
     */
    import(data) {
        for (const sheet of data.sheets) {
            if (sheet.figures) {
                for (const figure of sheet.figures) {
                    if (figure.tag === "chart" && isNWOSChartType(figure.data.type)) {
                        figure.data.type = normalizeNWOSChartType(figure.data.type);
                        this._addNWOSChart(figure.data.chartId, figure.data.fieldMatching ?? {});
                    } else if (figure.tag === "carousel") {
                        for (const chartId in figure.data.chartDefinitions) {
                            const fieldMatching = figure.data.fieldMatching ?? {};
                            const chartDefinition = figure.data.chartDefinitions[chartId];
                            if (isNWOSChartType(chartDefinition.type)) {
                                chartDefinition.type = normalizeNWOSChartType(chartDefinition.type);
                                this._addNWOSChart(chartId, fieldMatching[chartId]);
                            }
                        }
                    }
                }
            }
        }
    }
    /**
     * Export the chart
     *
     * @param {Object} data
     */
    export(data) {
        for (const sheet of data.sheets) {
            if (sheet.figures) {
                for (const figure of sheet.figures) {
                    if (figure.tag === "chart" && isNWOSChartType(figure.data.type)) {
                        figure.data.type = normalizeNWOSChartType(figure.data.type);
                        figure.data.fieldMatching = this.getChartFieldMatch(figure.data.chartId);
                        figure.data.searchParams.domain = new Domain(
                            figure.data.searchParams.domain
                        ).toJson();
                    } else if (figure.tag === "carousel") {
                        figure.data.fieldMatching = {};
                        for (const chartId in figure.data.chartDefinitions) {
                            const chartDefinition = figure.data.chartDefinitions[chartId];
                            if (isNWOSChartType(chartDefinition.type)) {
                                chartDefinition.type = normalizeNWOSChartType(chartDefinition.type);
                                figure.data.fieldMatching[chartId] =
                                    this.getChartFieldMatch(chartId);
                                chartDefinition.searchParams.domain = new Domain(
                                    chartDefinition.searchParams.domain
                                ).toJson();
                            }
                        }
                    }
                }
            }
        }
    }
    // -------------------------------------------------------------------------
    // Private
    // -------------------------------------------------------------------------

    /**
     * Get the current nwosChartFieldMatching of a chart
     *
     * @param {string} chartId
     * @param {string} filterId
     */
    getNWOSChartFieldMatching(chartId, filterId) {
        return this.charts[chartId].fieldMatching[filterId];
    }

    /**
     * Sets the current nwosChartFieldMatching of a chart
     *
     * @param {string} filterId
     * @param {Record<string,FieldMatching>} chartFieldMatches
     */
    _setNWOSChartFieldMatching(filterId, chartFieldMatches) {
        const charts = { ...this.charts };
        for (const [chartId, fieldMatch] of Object.entries(chartFieldMatches)) {
            charts[chartId].fieldMatching[filterId] = fieldMatch;
        }
        this.history.update("charts", charts);
    }

    _onFilterDeletion(filterId) {
        const charts = { ...this.charts };
        for (const chartId in charts) {
            this.history.update("charts", chartId, "fieldMatching", filterId, undefined);
        }
    }

    /**
     * @param {string} chartId
     * @param {Object} fieldMatching
     */
    _addNWOSChart(chartId, fieldMatching = undefined) {
        const model = this.getters.getChartDefinition(chartId).metaData.resModel;
        this.history.update("charts", chartId, {
            chartId,
            fieldMatching: fieldMatching || this.getters.getFieldMatchingForModel(model),
        });
    }
}
