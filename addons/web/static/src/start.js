import { mountComponent } from "./env";
import { localization } from "@web/core/l10n/localization";
import { session } from "@web/session";
import { hasTouch } from "@web/core/browser/feature_detection";
import { user } from "@web/core/user";
import { Component, whenReady } from "@nwos/owl";
import { rpc } from "./core/network/rpc";
import { RPCCache } from "./core/network/rpc_cache";

const FALLBACK_SERVER_VERSION_INFO = [0, 0, 0, "final", 0, ""];
const FALLBACK_VIEW_INFO = {
    list: { icon: "oi oi-view-list", display_name: "List", multi_record: true },
    form: { icon: "fa fa-address-card", display_name: "Form", multi_record: false },
    graph: { icon: "fa fa-area-chart", display_name: "Graph", multi_record: true },
    pivot: { icon: "oi oi-view-pivot", display_name: "Pivot", multi_record: true },
    kanban: { icon: "oi oi-view-kanban", display_name: "Kanban", multi_record: true },
    calendar: { icon: "fa fa-calendar", display_name: "Calendar", multi_record: true },
    search: { icon: "oi oi-search", display_name: "Search", multi_record: true },
};

// Chrome iOS wraps some text nodes (like measures, email...)
// with a `<chrome_annotation>` tag, which breaks OWL rendering.
// This meta tag allows to disable this behavior.
const chromeMetaTag = document.createElement("meta");
chromeMetaTag.setAttribute("name", "chrome");
chromeMetaTag.setAttribute("content", "nointentdetection");
document.head.appendChild(chromeMetaTag);

function hasViewInfo() {
    return (
        session.view_info &&
        typeof session.view_info === "object" &&
        Object.keys(session.view_info).length > 0
    );
}

async function refreshSessionInfo() {
    try {
        const sessionInfo = await rpc("/web/session/get_session_info", {}, { silent: true });
        Object.assign(session, sessionInfo);
        if (sessionInfo.user_context) {
            user.updateContext(sessionInfo.user_context);
        }
    } catch {
        // Keep boot resilient when the browser has a stale or expired session.
    }
}

async function ensureSessionInfo() {
    if (!Array.isArray(session.server_version_info) || !hasViewInfo() || !user.context.lang) {
        await refreshSessionInfo();
    }
    if (Array.isArray(session.server_version_info) && hasViewInfo()) {
        return;
    }
    try {
        Object.assign(session, await rpc("/web/webclient/version_info", {}));
    } catch {
        // Keep the webclient bootable even if the version endpoint is not reachable.
    }
    if (!Array.isArray(session.server_version_info)) {
        session.server_version_info = FALLBACK_SERVER_VERSION_INFO;
        session.server_version ||= "0.0";
    }
    if (!hasViewInfo()) {
        session.view_info = { ...FALLBACK_VIEW_INFO };
    }
}

/**
 * Function to start a webclient.
 * It is used both in community and enterprise in main.js.
 * It's meant to be webclient flexible so we can have a subclass of
 * webclient in enterprise with added features.
 *
 * @param {Component} Webclient
 */
export async function startWebClient(Webclient) {
    await ensureSessionInfo();
    const serverVersionInfo = session.server_version_info;
    nwos.debug ||= "";
    nwos.info = {
        db: session.db,
        server_version: session.server_version,
        server_version_info: serverVersionInfo,
        isEnterprise: serverVersionInfo.slice(-1)[0] === "e",
    };
    nwos.isReady = false;

    if (window.isSecureContext && session.browser_cache_secret) {
        rpc.setCache(new RPCCache("rpc", session.registry_hash, session.browser_cache_secret));
    }

    await whenReady();
    const app = await mountComponent(Webclient, document.body, { name: "NWOS Web Client" });
    const { env } = app;
    Component.env = env;

    const classList = document.body.classList;
    if (localization.direction === "rtl") {
        classList.add("o_rtl");
    }
    if (user.userId === 1) {
        classList.add("o_is_superuser");
    }
    if (env.debug) {
        classList.add("o_debug");
    }
    if (hasTouch()) {
        classList.add("o_touch_device");
    }
    // delete nwos.debug; // FIXME: some legacy code rely on this
    nwos.isReady = true;
}
