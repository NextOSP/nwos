/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Remove the "My NWOS.com account" entry from the top-right user menu.
 *
 * Core registers it as `nwos_account` in the `user_menuitems` registry
 * (web/.../user_menu/user_menu_items.js). It links to accounts.nwos.com, which
 * isn't relevant here, so we drop it without touching the core file.
 */
registry.category("user_menuitems").remove("nwos_account");
