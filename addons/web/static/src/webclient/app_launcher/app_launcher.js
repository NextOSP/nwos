import { Component, onMounted, useRef, useState } from "@nwos/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { getAppSections } from "@web/webclient/menus/app_sections";

export class AppLauncher extends Component {
    static template = "web.AppLauncher";
    static props = { ...standardActionServiceProps };
    static displayName = _t("All Apps");
    static path = "apps";

    setup() {
        this.menuService = useService("menu");
        this.searchInput = useRef("searchInput");
        this.state = useState({ query: "" });

        onMounted(() => {
            this.searchInput.el?.focus();
        });
    }

    get apps() {
        const query = this.state.query.trim().toLowerCase();
        const apps = this.menuService.getApps();
        if (!query) {
            return apps;
        }
        return apps.filter((app) => app.name.toLowerCase().includes(query));
    }

    get appSections() {
        return getAppSections(this.apps);
    }

    get hasQuery() {
        return Boolean(this.state.query.trim());
    }

    onSearch(ev) {
        this.state.query = ev.target.value;
    }

    getAppHref(app) {
        return `/nwos/${app.actionPath || "action-" + app.actionID}`;
    }

    async openApp(app) {
        await this.menuService.selectMenu(app);
    }
}

registry.category("actions").add("apps_menu", AppLauncher);
