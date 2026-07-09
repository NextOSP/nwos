import { NWOSCorePlugin } from "@spreadsheet/plugins";
import { coreTypes, constants } from "@nwos/o-spreadsheet";
const { FIGURE_ID_SPLITTER } = constants;

/** Plugin that link charts with NWOS menus. It can contain either the Id of the nwos menu, or its xml id. */
export class ChartNWOSMenuPlugin extends NWOSCorePlugin {
    static getters = /** @type {const} */ (["getChartNWOSMenu"]);
    constructor(config) {
        super(config);
        this.nwosMenuReference = {};
    }

    /**
     * Handle a spreadsheet command
     * @param {Object} cmd Command
     */
    handle(cmd) {
        switch (cmd.type) {
            case "LINK_NWOS_MENU_TO_CHART":
                this.history.update("nwosMenuReference", cmd.chartId, cmd.nwosMenuId);
                break;
            case "DELETE_CHART":
                this.history.update("nwosMenuReference", cmd.chartId, undefined);
                break;
            case "DUPLICATE_SHEET":
                this.updateOnDuplicateSheet(cmd.sheetId, cmd.sheetIdTo);
                break;
        }
    }

    updateOnDuplicateSheet(sheetIdFrom, sheetIdTo) {
        for (const oldChartId of this.getters.getChartIds(sheetIdFrom)) {
            const menu = this.nwosMenuReference[oldChartId];
            if (!menu) {
                continue;
            }
            const chartIdBase = oldChartId.split(FIGURE_ID_SPLITTER).pop();
            const newChartId = `${sheetIdTo}${FIGURE_ID_SPLITTER}${chartIdBase}`;
            this.history.update("nwosMenuReference", newChartId, menu);
        }
    }

    /**
     * Get nwos menu linked to the chart
     *
     * @param {string} chartId
     * @returns {object | undefined}
     */
    getChartNWOSMenu(chartId) {
        const menuId = this.nwosMenuReference[chartId];
        return menuId ? this.getters.getIrMenu(menuId) : undefined;
    }

    import(data) {
        if (data.chartNWOSMenusReferences) {
            this.nwosMenuReference = data.chartNWOSMenusReferences;
        }
    }

    export(data) {
        data.chartNWOSMenusReferences = this.nwosMenuReference;
    }
}

coreTypes.add("LINK_NWOS_MENU_TO_CHART");
