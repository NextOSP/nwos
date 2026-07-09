declare module "@spreadsheet" {
    import { CommandResult, CorePlugin, UIPlugin } from "@nwos/o-spreadsheet";
    import { CommandResult as CR } from "@spreadsheet/o_spreadsheet/cancelled_reason";
    type NWOSCommandResult = CommandResult | typeof CR;

    export interface NWOSCorePlugin extends CorePlugin {
        getters: NWOSCoreGetters;
        dispatch: NWOSCoreDispatch;
        allowDispatch(command: AllCoreCommand): string | string[];
        beforeHandle(command: AllCoreCommand): void;
        handle(command: AllCoreCommand): void;
    }

    export interface NWOSCorePluginConstructor {
        new (config: unknown): NWOSCorePlugin;
    }

    export interface NWOSUIPlugin extends UIPlugin {
        getters: NWOSGetters;
        dispatch: NWOSDispatch;
        allowDispatch(command: AllCommand): string | string[];
        beforeHandle(command: AllCommand): void;
        handle(command: AllCommand): void;
    }

    export interface NWOSUIPluginConstructor {
        new (config: unknown): NWOSUIPlugin;
    }
}
