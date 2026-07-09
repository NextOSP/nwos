import { CorePlugin, Model, UID } from "@nwos/o-spreadsheet";
import { ChartNWOSMenuPlugin, NWOSChartCorePlugin, NWOSChartCoreViewPlugin } from "@spreadsheet/chart";
import { CurrencyPlugin } from "@spreadsheet/currency/plugins/currency";
import { AccountingPlugin } from "addons/spreadsheet_account/static/src/plugins/accounting_plugin";
import { GlobalFiltersCorePlugin, GlobalFiltersCoreViewPlugin } from "@spreadsheet/global_filters";
import { ListCorePlugin, ListCoreViewPlugin } from "@spreadsheet/list";
import { IrMenuPlugin } from "@spreadsheet/ir_ui_menu/ir_ui_menu_plugin";
import { PivotNWOSCorePlugin } from "@spreadsheet/pivot";
import { PivotCoreGlobalFilterPlugin } from "@spreadsheet/pivot/plugins/pivot_core_global_filter_plugin";

type Getters = Model["getters"];
type CoreGetters = CorePlugin["getters"];

/**
 * Union of all getter names of a plugin.
 *
 * e.g. With the following plugin
 * @example
 * class MyPlugin {
 *   static getters = [
 *     "getCell",
 *     "getCellValue",
 *   ] as const;
 *   getCell() { ... }
 *   getCellValue() { ... }
 * }
 * type Names = GetterNames<typeof MyPlugin>
 * // is equivalent to "getCell" | "getCellValue"
 */
type GetterNames<Plugin extends { getters: readonly string[] }> = Plugin["getters"][number];

/**
 * Extract getter methods from a plugin, based on its `getters` static array.
 * @example
 * class MyPlugin {
 *   static getters = [
 *     "getCell",
 *     "getCellValue",
 *   ] as const;
 *   getCell() { ... }
 *   getCellValue() { ... }
 * }
 * type MyPluginGetters = PluginGetters<typeof MyPlugin>;
 * // MyPluginGetters is equivalent to:
 * // {
 * //   getCell: () => ...,
 * //   getCellValue: () => ...,
 * // }
 */
type PluginGetters<Plugin extends { new (...args: unknown[]): any; getters: readonly string[] }> =
    Pick<InstanceType<Plugin>, GetterNames<Plugin>>;

declare module "@spreadsheet" {
    /**
     * Add getters from custom plugins defined in nwos
     */

    interface NWOSCoreGetters extends CoreGetters {}
    interface NWOSCoreGetters extends PluginGetters<typeof GlobalFiltersCorePlugin> {}
    interface NWOSCoreGetters extends PluginGetters<typeof ListCorePlugin> {}
    interface NWOSCoreGetters extends PluginGetters<typeof NWOSChartCorePlugin> {}
    interface NWOSCoreGetters extends PluginGetters<typeof ChartNWOSMenuPlugin> {}
    interface NWOSCoreGetters extends PluginGetters<typeof IrMenuPlugin> {}
    interface NWOSCoreGetters extends PluginGetters<typeof PivotNWOSCorePlugin> {}
    interface NWOSCoreGetters extends PluginGetters<typeof PivotCoreGlobalFilterPlugin> {}

    interface NWOSGetters extends Getters {}
    interface NWOSGetters extends NWOSCoreGetters {}
    interface NWOSGetters extends PluginGetters<typeof GlobalFiltersCoreViewPlugin> {}
    interface NWOSGetters extends PluginGetters<typeof ListCoreViewPlugin> {}
    interface NWOSGetters extends PluginGetters<typeof NWOSChartCoreViewPlugin> {}
    interface NWOSGetters extends PluginGetters<typeof CurrencyPlugin> {}
    interface NWOSGetters extends PluginGetters<typeof AccountingPlugin> {}
}
