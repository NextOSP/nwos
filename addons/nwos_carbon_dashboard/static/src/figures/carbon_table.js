import { Component } from "@nwos/owl";

/**
 * A Carbon-styled data table. Renders `{ columns: [{label, numeric}], rows:
 * [[cell, ...]] }`. Used for carousel data views (Top Countries / Top
 * Categories) and other ranked lists.
 */
export class CarbonTable extends Component {
    static template = "nwos_carbon_dashboard.CarbonTable";
    static props = {
        columns: Array, // [{ label, numeric? }]
        rows: Array,    // [[cell, cell, ...], ...]
    };
}
