import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { Status } from "@spreadsheet_dashboard/bundle/dashboard_action/dashboard_loader_service";
import { useSetupAction } from "@web/search/action_hook";
import { DashboardMobileSearchPanel } from "@spreadsheet_dashboard/bundle/dashboard_action/mobile_search_panel/mobile_search_panel";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { useSpreadsheetPrint } from "@spreadsheet/hooks";
import { router } from "@web/core/browser/router";
import { useSearchBarToggler } from "@web/search/search_bar/search_bar_toggler";

import { Component, onWillStart, useState, useEffect } from "@nwos/owl";
import { DashboardSearchBar } from "@spreadsheet_dashboard/bundle/dashboard_action/dashboard_search_bar/dashboard_search_bar";
import { CarbonDashboardCanvas } from "./canvas/carbon_dashboard_canvas";

/**
 * Drop-in replacement for SpreadsheetDashboardAction that renders every
 * published dashboard in IBM Carbon style. It reuses the
 * `spreadsheet_dashboard_loader` service (groups + o-spreadsheet Model) verbatim
 * and only swaps the rendering: instead of mounting SpreadsheetComponent (the
 * canvas), it feeds the Model's getters into Carbon components.
 */
export class CarbonDashboardAction extends Component {
    static template = "nwos_carbon_dashboard.CarbonDashboardAction";
    static path = "dashboards";
    static components = {
        ControlPanel,
        DashboardMobileSearchPanel,
        DashboardSearchBar,
        CarbonDashboardCanvas,
    };
    static props = { ...standardActionServiceProps };
    static displayName = _t("Dashboards");

    setup() {
        this.Status = Status;
        this.controlPanelDisplay = {};
        this.orm = useService("orm");
        this.actionService = useService("action");
        // useState connects the reactive loader to THIS component's render, so
        // the dashboard reliably re-renders when a dashboard's status flips
        // NotLoaded -> Loading -> Loaded (fixes the stuck "Loading…" blank).
        this.loader = useState(useService("spreadsheet_dashboard_loader"));

        onWillStart(async () => {
            if (this.props.state && this.props.state.dashboardLoader) {
                this.loader.restoreFromState(this.props.state.dashboardLoader);
            } else {
                await this.loader.load();
            }
            const activeDashboardId = this.getInitialActiveDashboard();
            if (activeDashboardId) {
                // Non-blocking: openDashboard triggers the load and re-renders
                // when it resolves. Do NOT await here — this is the initial
                // action, and awaiting the data RPC would block the whole
                // web client from mounting until the dashboard data arrives.
                this.openDashboard(activeDashboardId);
            }
        });

        useEffect(
            () => router.pushState({ dashboard_id: this.activeDashboardId }),
            () => [this.activeDashboardId]
        );
        // Re-render when the active dashboard's model updates (e.g. filter change).
        useEffect(
            () => {
                const dashboard = this.loader.getActiveDashboard();
                if (dashboard && dashboard.status === Status.Loaded) {
                    const render = () => this.render(true);
                    dashboard.model.on("update", this, render);
                    return () => dashboard.model.off("update", this, render);
                }
            },
            () => {
                const dashboard = this.loader.getActiveDashboard();
                return [dashboard?.model, dashboard?.status];
            }
        );

        useSetupAction({
            getLocalState: () => ({ dashboardLoader: this.loader.getState() }),
        });
        useSpreadsheetPrint(() => this.loader.getActiveDashboard()?.model);
        this.state = useState({ sidebarExpanded: true });
        this.searchBarToggler = useSearchBarToggler();
    }

    get activeDashboardId() {
        return this.loader.getActiveDashboard()
            ? this.loader.getActiveDashboard().data.id
            : undefined;
    }

    getInitialActiveDashboard() {
        const activeDashboardId = this.props.state?.dashboardLoader?.activeDashboardId;
        if (activeDashboardId) {
            return activeDashboardId;
        }
        const params = this.props.action.params;
        if (params && params.dashboard_id) {
            return params.dashboard_id;
        }
        const [firstSection] = this.getDashboardGroups();
        if (firstSection && firstSection.dashboards.length) {
            return firstSection.dashboards[0].data.id;
        }
    }

    getDashboardGroups() {
        return this.loader.getDashboardGroups();
    }

    openDashboard(dashboardId) {
        this.loader.activateDashboard(dashboardId);
        // Trigger the data load and force a re-render once it resolves, so
        // switching dashboards from the sidebar reliably leaves "Loading…".
        const dashboard = this.loader.getDashboard(dashboardId);
        if (dashboard && dashboard.promise) {
            dashboard.promise.then(() => this.render(true)).catch(() => {});
        }
    }

    async toggleFavorite() {
        if (!this.loader.getActiveDashboard()) {
            return;
        }
        const { id, is_favorite } = this.loader.getActiveDashboard().data;
        await this.orm.call("spreadsheet.dashboard", "action_toggle_favorite", [id]);
        this.loader.getActiveDashboard().data.is_favorite = !is_favorite;
    }

    toggleSidebar() {
        this.state.sidebarExpanded = !this.state.sidebarExpanded;
    }

    get activeDashboardGroupName() {
        return this.getDashboardGroups().find(
            (group) =>
                group.id !== "favorites" &&
                group.dashboards.some(({ data }) => data.id === this.activeDashboardId)
        )?.name;
    }
}

registry
    .category("actions")
    .add("action_spreadsheet_dashboard", CarbonDashboardAction, { force: true });
