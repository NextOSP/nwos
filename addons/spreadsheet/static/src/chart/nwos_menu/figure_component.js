import { patch } from "@web/core/utils/patch";
import * as spreadsheet from "@nwos/o-spreadsheet";
import { useService } from "@web/core/utils/hooks";
import { navigateToNWOSMenu } from "../nwos_chart/nwos_chart_helpers";

patch(spreadsheet.components.FigureComponent.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.notificationService = useService("notification");
    },
    get chartId() {
        if (this.props.figureUI.tag !== "chart" && this.props.figureUI.tag !== "carousel") {
            return undefined;
        }
        return this.env.model.getters.getChartIdFromFigureId(this.props.figureUI.id);
    },
    async navigateToNWOSMenu(newWindow) {
        const menu = this.env.model.getters.getChartNWOSMenu(this.chartId);
        await navigateToNWOSMenu(menu, this.actionService, this.notificationService, newWindow);
    },
    get hasNWOSMenu() {
        return this.chartId && this.env.model.getters.getChartNWOSMenu(this.chartId) !== undefined;
    },
});

patch(spreadsheet.components.ScorecardChart.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.notificationService = useService("notification");
    },
    async navigateToNWOSMenu(newWindow) {
        const menu = this.env.model.getters.getChartNWOSMenu(this.props.chartId);
        await navigateToNWOSMenu(menu, this.actionService, this.notificationService, newWindow);
    },
    get hasNWOSMenu() {
        return this.env.model.getters.getChartNWOSMenu(this.props.chartId) !== undefined;
    },
    async onClick() {
        if (this.env.isDashboard() && this.hasNWOSMenu) {
            await this.navigateToNWOSMenu();
        }
    },
});

patch(spreadsheet.components.GaugeChartComponent.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.notificationService = useService("notification");
    },
    async navigateToNWOSMenu(newWindow) {
        const menu = this.env.model.getters.getChartNWOSMenu(this.props.chartId);
        await navigateToNWOSMenu(menu, this.actionService, this.notificationService, newWindow);
    },
    get hasNWOSMenu() {
        return this.env.model.getters.getChartNWOSMenu(this.props.chartId) !== undefined;
    },
    async onClick() {
        if (this.env.isDashboard() && this.hasNWOSMenu) {
            await this.navigateToNWOSMenu();
        }
    },
});
