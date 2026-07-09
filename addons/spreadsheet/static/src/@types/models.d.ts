declare module "@spreadsheet" {
    import { Model } from "@nwos/o-spreadsheet";

    export interface NWOSSpreadsheetModel extends Model {
        getters: NWOSGetters;
        dispatch: NWOSDispatch;
    }

    export interface NWOSSpreadsheetModelConstructor {
        new (
            data: object,
            config: Partial<Model["config"]>,
            revisions: object[]
        ): NWOSSpreadsheetModel;
    }
}
