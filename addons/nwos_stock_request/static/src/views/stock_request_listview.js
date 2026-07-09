import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { StockRequestDashboard } from "./stock_request_dashboard";

export class StockRequestDashboardRenderer extends ListRenderer {
    static template = "nwos_stock_request.ListRenderer";
    static components = { ...ListRenderer.components, StockRequestDashboard };
}

export const StockRequestDashboardListView = {
    ...listView,
    Renderer: StockRequestDashboardRenderer,
};

registry.category("views").add("stock_request_dashboard_list", StockRequestDashboardListView);
