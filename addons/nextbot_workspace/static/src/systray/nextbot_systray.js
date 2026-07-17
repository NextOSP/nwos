import { Component } from "@nwos/owl";

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Systray launcher for the NextBot workspace. This replaces the old floating
 * Discuss chat bubble: NextBot is now reachable from anywhere through a single
 * icon that opens the dedicated full-page workspace.
 */
export class NextBotSystray extends Component {
    static template = "nextbot_workspace.NextBotSystray";
    static props = {};

    setup() {
        this.action = useService("action");
        this.title = _t("NextBot");
    }

    onClick() {
        this.action.doAction("nextbot_workspace.action_nextbot_workspace");
    }
}

registry
    .category("systray")
    .add("nextbot_workspace.launcher", { Component: NextBotSystray }, { sequence: 27 });
