import * as spreadsheet from "@nwos/o-spreadsheet";
import { NWOSUIPlugin } from "@spreadsheet/plugins";

const { constants } = spreadsheet;
const { PIVOT_TABLE_CONFIG } = constants;

/**
 * @typedef {import("./list_core_plugin").SpreadsheetList} SpreadsheetList
 */

export class ListUIPlugin extends NWOSUIPlugin {

    /**
     * Handle a spreadsheet command
     * @param {Object} cmd Command
     */
    handle(cmd) {
        switch (cmd.type) {
            case "INSERT_NWOS_LIST_WITH_TABLE": {
                this.dispatch("INSERT_NWOS_LIST", cmd);
                this._addTable(cmd);
                break;
            }
            case "RE_INSERT_NWOS_LIST_WITH_TABLE": {
                this.dispatch("RE_INSERT_NWOS_LIST", cmd);
                this._addTable(cmd);
                break;
            }
        }
    }

    // -------------------------------------------------------------------------
    // Handlers
    // -------------------------------------------------------------------------


    _addTable({ sheetId, col, row, linesNumber, columns }) {
        const zone = {
            left: col,
            right: col + columns.length - 1,
            top: row,
            bottom: row + linesNumber,
        };
        this.dispatch("CREATE_TABLE", {
            tableType: "static",
            sheetId,
            ranges: [this.getters.getRangeDataFromZone(sheetId, zone)],
            config: { ...PIVOT_TABLE_CONFIG, firstColumn: false },
        });
    }
}
