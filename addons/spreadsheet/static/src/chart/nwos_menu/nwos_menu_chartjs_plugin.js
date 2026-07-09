import {
    navigateToNWOSMenu,
    isChartJSMiddleClick,
} from "@spreadsheet/chart/nwos_chart/nwos_chart_helpers";

export const chartNWOSMenuPlugin = {
    id: "chartNWOSMenuPlugin",
    afterEvent(chart, { event }, { env, menu }) {
        const isDashboard = env?.model.getters.isDashboard();
        if (!menu || !isDashboard) {
            return;
        }
        event.native.target.style.cursor = "pointer";

        const middleClick = isChartJSMiddleClick(event);
        if (
            (event.type !== "click" && !middleClick) ||
            event.native.defaultPrevented
        ) {
            return;
        }
        navigateToNWOSMenu(menu, env.services.action, env.services.notification, middleClick);
    },
};
