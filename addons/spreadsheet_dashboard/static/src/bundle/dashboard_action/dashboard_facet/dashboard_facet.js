import { Component } from "@nwos/owl";

export class DashboardFacet extends Component {
    static template = "spreadsheet_dashboard.DashboardFacet";
    static components = {};
    static props = {
        facet: Object,
        clearFilter: Function,
        onClick: Function,
    };
}
