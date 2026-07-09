import { SpreadsheetChildEnv as SSChildEnv } from "@nwos/o-spreadsheet";
import { Services } from "services";

declare module "@spreadsheet" {
    import { Model } from "@nwos/o-spreadsheet";

    export interface SpreadsheetChildEnv extends SSChildEnv {
        model: NWOSSpreadsheetModel;
        services: Services;
    }
}
