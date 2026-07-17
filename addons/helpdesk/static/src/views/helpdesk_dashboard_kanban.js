import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { HelpdeskDashboard } from "./helpdesk_dashboard";

export class HelpdeskDashboardKanbanRenderer extends KanbanRenderer {
    static template = "helpdesk.DashboardKanbanRenderer";
    static components = { ...KanbanRenderer.components, HelpdeskDashboard };
}

export const HelpdeskDashboardKanbanView = {
    ...kanbanView,
    Renderer: HelpdeskDashboardKanbanRenderer,
};

registry.category("views").add("helpdesk_dashboard_kanban", HelpdeskDashboardKanbanView);
