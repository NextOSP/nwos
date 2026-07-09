import { CorePlugin, CoreViewPlugin, UIPlugin } from "@nwos/o-spreadsheet";

/**
 * An o-spreadsheet core plugin with access to all custom NWOS plugins
 * @type {import("@spreadsheet").NWOSCorePluginConstructor}
 **/
export const NWOSCorePlugin = CorePlugin;

/**
 * An o-spreadsheet CoreView plugin with access to all custom NWOS plugins
 * @type {import("@spreadsheet").NWOSUIPluginConstructor}
 **/
export const NWOSCoreViewPlugin = CoreViewPlugin;

/**
 * An o-spreadsheet UI plugin with access to all custom NWOS plugins
 * @type {import("@spreadsheet").NWOSUIPluginConstructor}
 **/
export const NWOSUIPlugin = UIPlugin;
