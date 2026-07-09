import { components } from "@nwos/o-spreadsheet";
import { patch } from "@web/core/utils/patch";

patch(components.ChartJsComponent.prototype, {
    createChart(chartData) {
        if (this.env.model.getters.isDashboard()) {
            chartData = this.addNWOSMenuPluginToChartData(chartData);
        }
        super.createChart(chartData);
    },
    updateChartJs(chartData) {
        if (this.env.model.getters.isDashboard()) {
            chartData = this.addNWOSMenuPluginToChartData(chartData);
        }
        super.updateChartJs(chartData);
    },
    addNWOSMenuPluginToChartData(chartData) {
        chartData.chartJsConfig.options.plugins.chartNWOSMenuPlugin = {
            env: this.env,
            menu: this.env.model.getters.getChartNWOSMenu(this.props.chartId),
        };
        return chartData;
    },
});
